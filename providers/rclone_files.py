"""Rclone file transport behind FCA's existing OAuth, inventory and durable queue.

Only authenticated Unix IPC; encrypted, separately locked account configuration.
No browser flow, public RC port, provider mutation, or investigator tokens.
REST preserves original IDs/metadata; Google copies by ID. OneDrive resolves
paths and checks IDs before copying; ambiguities never acquire the wrong object.
"""
from datetime import datetime, timezone
import json
import re
import time
from pathlib import Path

from backend import cloud_auth, oauth
from providers.apple.adapter import AccountContext, ProviderError
from providers.acquisition import AppleDownload, WebProvider, Retryable, AccessDenied, AuthenticationRequired
from providers.integrity import verify_source


def transfer_error(provider, message):
    """Classify upstream errors without exposing text, URLs or signed links."""
    message=message.lower()
    def status(code):
        return bool(re.search(r'\b(?:error\s+|http(?: error)?[: ]+|status(?: code)?[: =]+)'+str(code)+r'\b',message)
                    or re.search(r'\b'+str(code)+r'\s+(?:unauthorized|forbidden|not found|too many|bad gateway|service unavailable|gateway timeout|internal server)\b',message))
    if status(401) or any(code in message for code in ('invalid_grant','invalidauthenticationtoken','token has expired')):
        raise AuthenticationRequired('Cloud-Anmeldung ist abgelaufen. Bitte erneut anmelden.')
    throttled=(status(429) or (provider=='google' and any(code in message for code in ('ratelimitexceeded','userratelimitexceeded'))))
    if throttled: raise Retryable(30,True)
    if status(403) or status(404) or any(code in message for code in ('accessdenied','permission denied','insufficientpermissions','object not found','file not found','directory not found')):
        raise AccessDenied('Cloud-Datei ist nicht zugänglich oder nicht freigegeben.')
    if any(status(code) for code in (500,502,503,504)) or any(code in message for code in ('timeout','timed out','connection reset','unexpected eof','temporarily unavailable')):
        raise Retryable()
    raise ProviderError('Rclone konnte die Datei nicht sicher übertragen. Umfang und Anmeldung prüfen.')


class RcloneFiles(AppleDownload):
    _ENDPOINTS=AppleDownload._ENDPOINTS | frozenset(('config/get','backend/command'))

    def __init__(self, provider, case_id, account_id, binary='/usr/local/bin/rclone'):
        self.provider=provider
        self.web=WebProvider(provider,case_id,account_id)
        directory=cloud_auth._directory(case_id,account_id)
        super().__init__(directory/'files-rclone.conf',cloud_auth._key(case_id,account_id),AccountContext(case_id,account_id),binary=binary,timeout=60)
        self.limits=self.web.limits
        self._ready=False

    def __enter__(self):
        super().__enter__()
        try:
            config=oauth.configuration(self.provider)
            if not config: raise ProviderError('Anbieteranwendung zuerst in den Einstellungen einrichten.')
            existing=self._rpc('config/get',{'name':self.remote}) if self._rpc('config/listremotes',{}).get('remotes') else {}
            value=oauth.load(self.scope.case_id,self.scope.account_id)
            # A persisted Rclone token wins after a worker crash, unless FCA has
            # explicitly authorized a new connection since that configuration.
            generation=str(value.get('authorized_at',0))
            if value.get('oauth_client_id',config['client_id'])!=config['client_id']:
                raise AuthenticationRequired('Anbieteranwendung wurde geändert. Bitte Cloud-Konto erneut anmelden.')
            if existing.get('fca_authorized_at')==generation and existing.get('client_id',config['client_id'])!=config['client_id']:
                raise AuthenticationRequired('Anbieteranwendung wurde geändert. Bitte Cloud-Konto erneut anmelden.')
            if existing.get('fca_authorized_at')!=generation or not existing.get('token'):
                oauth.token(self.provider,self.scope.case_id,self.scope.account_id)
                value=oauth.load(self.scope.case_id,self.scope.account_id)
                expiry=datetime.fromtimestamp(value['expires_at'],timezone.utc).isoformat()
                token={key:value[key] for key in ('access_token','refresh_token','token_type') if value.get(key)}
                token['expiry']=expiry
                parameters={'client_id':config['client_id'],'client_secret':config['client_secret'],
                            'token':json.dumps(token),'fca_authorized_at':generation,
                            'config_refresh_token':'false'}
                if self.provider=='google':
                    parameters.update(scope='drive.readonly',export_formats='docx,xlsx,pptx,pdf',skip_shortcuts='true')
                    kind='drive'
                else:
                    drive=self.web.json(self.web.base+'/me/drive?$select=id,driveType')
                    if drive.get('driveType') not in ('personal','business','documentLibrary') or not re.fullmatch(r'[A-Za-z0-9!._,-]{1,512}',drive.get('id','')):
                        raise ProviderError('OneDrive-Laufwerk konnte nicht sicher bestimmt werden.')
                    parameters.update(drive_id=drive['id'],drive_type=drive['driveType'],access_scopes='Files.Read offline_access')
                    kind='onedrive'
                # The provided token avoids all interactive OAuth/drive setup.
                # Any pending config prompt is not exposed or followed.
                self._rpc('config/create',{'name':self.remote,'type':kind,'parameters':parameters,'opt':{'nonInteractive':True,'obscure':True}})
                self._check_encrypted()
            else:
                # Client-secret rotation is an administrator action, never a
                # reason to fall back to a shared application or write scopes.
                self._rpc('config/update',{'name':self.remote,'parameters':{'client_secret':config['client_secret']},'opt':{'nonInteractive':True,'obscure':True}})
            self._ready=True
            self.web.access_token=self.current_token
            self.current_token()
            return self
        except BaseException:
            self.close()
            raise

    def current_token(self,refresh=True):
        config=self._rpc('config/get',{'name':self.remote})
        try:
            token=json.loads(config['token'])
            expires=datetime.fromisoformat(token['expiry'].replace('Z','+00:00')).timestamp()
            if refresh and expires<=time.time()+30:
                # Rclone is the sole refresh owner during this locked session.
                self._rpc('operations/stat',{'fs':self.remote+':','remote':''})
                token=json.loads(self._rpc('config/get',{'name':self.remote})['token'])
                expires=datetime.fromisoformat(token['expiry'].replace('Z','+00:00')).timestamp()
            if not token.get('access_token') or (refresh and expires<=time.time()): raise ValueError()
        except (KeyError,ValueError,TypeError):
            raise AuthenticationRequired('Cloud-Anmeldung ist nicht mehr gültig. Bitte erneut anmelden.') from None
        with oauth.LOCK:
            value=oauth.load(self.scope.case_id,self.scope.account_id)
            if value.get('access_token')!=token['access_token'] or value.get('refresh_token')!=token.get('refresh_token',value.get('refresh_token')):
                value.update({k:token[k] for k in ('access_token','refresh_token','token_type') if token.get(k)})
                value['expires_at']=expires
                oauth.save(self.scope.case_id,self.scope.account_id,value)
        return token['access_token']

    def identity(self):
        return self.web.identity()

    @property
    def throttled_until(self):
        return self.web.throttled_until

    def _request_failed(self,result):
        transfer_error(self.provider,str(result.get('error','')) if isinstance(result,dict) else '')

    def _rpc(self,endpoint,payload):
        if endpoint=='backend/command':
            args=payload.get('arg',[])
            if (self.provider!='google' or payload.get('command')!='copyid' or payload.get('fs')!=self.remote+':'
                    or len(args)!=2 or not re.fullmatch(r'[A-Za-z0-9_-]{1,512}',str(args[0]))):
                raise ProviderError('Backend-Befehl ist nicht freigegeben.')
            target=Path(args[1])
            if not target.is_absolute() or target.parent.resolve()!=target.parent or target.is_symlink() or not target.name.endswith('.part'):
                raise ProviderError('Nur ein lokales temporäres Übertragungsziel ist erlaubt.')
            if set(payload)-{'command','fs','arg','_async','_config'}:
                raise ProviderError('Zusätzliche Backend-Optionen sind nicht freigegeben.')
        return super()._rpc(endpoint,payload)

    def inventory(self,category,scope=''):
        yield from self.web.inventory(category,scope)

    @property
    def coverage(self): return self.web.coverage

    def download(self,record,target,reserve,progress):
        # Calendar payloads continue through the existing REST adapter.
        if 'payload' in record['metadata']:
            return self.web.download(record,target,reserve,progress)
        meta=record['metadata'];remote=meta.get('_rclone_path','');fs=self.remote+':'
        source_id=record['source_id']
        if self.provider=='google':
            # Pinned copyid obtains an object by ID, then copies to the LOCAL
            # destination. Never copy/move between provider paths. Handles equal
            # Google names without resolving the wrong sibling by path.
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,512}',source_id): raise ProviderError('Ungültige Cloud-Quellkennung.')
            result=self._rpc('backend/command',{'command':'copyid','fs':fs,'arg':[source_id,str(target)],'_async':True,
                             '_config':{'Transfers':1,'MultiThreadStreams':0,'BufferSize':262144,'LowLevelRetries':3,'Retries':1}})
            self._receive_copy(result['jobid'],target,reserve,progress)
            before={}
        else:
            if (not remote or remote.startswith('/') or any(part in ('','.','..') for part in remote.split('/'))
                    or '\\' in remote or ':' in remote or any(ord(c)<32 for c in remote)):
                raise ProviderError('Cloud-Pfad lässt sich nicht sicher mit Rclone abbilden.')
            before=self._rpc('operations/stat',{'fs':fs,'remote':remote,'opt':{'showHash':True,'showOrigIDs':True}}).get('item',{})
            found=before.get('OrigID') or before.get('ID','')
            if found!=source_id and not found.endswith('#'+source_id):
                raise ProviderError('Cloud-Pfad ist mehrdeutig oder geändert. Keine falsche Datei gesichert.')
            self._copy_from(fs,remote,{**record,'metadata':{**before}},target,reserve,progress)
        combined={**meta,'Hashes':before.get('Hashes',{})}
        try: meta['_fca_source_verification']=verify_source(target,combined)
        except ValueError: raise Retryable() from None
        from urllib.parse import quote
        identifier=quote(source_id,safe='')
        check=self.web.json(self.web.base+('/drive/v3/files/'+identifier+'?fields=id,version,size,modifiedTime' if self.provider=='google' else '/me/drive/items/'+identifier+'?$select=id,eTag,size,lastModifiedDateTime'))
        key='version' if self.provider=='google' else 'eTag'
        if not meta.get(key) or str(meta[key])!=str(check.get(key)):
            raise ProviderError('Quelldatei wurde während der Sicherung verändert. Neuen Lauf starten.')

    def _copy_error(self,message):
        transfer_error(self.provider,message)

    def close(self):
        try:
            if self._ready and self._process is not None and self._process.poll() is None:
                self.current_token(refresh=False)
        finally:
            self._ready=False
            super().close()
