"""Read-only provider inventory and streaming downloads. No remote mutation API."""
from contextlib import contextmanager
import hashlib
import http.client
import json
import os
from pathlib import Path
import threading
import time
from urllib.parse import quote, urlencode, urlsplit
import urllib.error
import urllib.request

from backend import cloud_auth, evidence, oauth
from providers.apple.adapter import AccountContext, ICloudSession, ProviderError

class Retryable(ProviderError):
    def __init__(self, delay=5, throttled=False):
        super().__init__('Anbieter vorübergehend nicht erreichbar. Übertragung wird wiederholt.')
        self.delay = max(1,delay); self.throttled=throttled

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None

OPENER = urllib.request.build_opener(NoRedirect())

def check_url(url, provider):
    parsed = urlsplit(url)
    expected = 'www.googleapis.com' if provider == 'google' else 'graph.microsoft.com'
    if parsed.scheme != 'https' or parsed.hostname != expected or parsed.port not in (None,443) or parsed.username or parsed.password or parsed.fragment:
        raise ProviderError('Ungültige Anbieteradresse.')
    return url

def clean_metadata(value):
    if isinstance(value,dict): return {k:clean_metadata(v) for k,v in value.items() if k not in ('@microsoft.graph.downloadUrl','@odata.nextLink','nextPageToken','nextSyncToken')}
    if isinstance(value,list): return [clean_metadata(v) for v in value]
    return value

class WebProvider:
    def __init__(self, provider, case_id, account_id):
        self.provider,self.case_id,self.account_id=provider,case_id,account_id
        self.base = 'https://www.googleapis.com' if provider=='google' else 'https://graph.microsoft.com/v1.0'
        self.limits=[]; self.throttled=False
    def identity(self):
        if self.provider=='google':
            return self.json(self.base+'/drive/v3/about?fields=user')['user']
        return self.json(self.base+'/me?$select=id,userPrincipalName,mail,displayName')
    def request(self,url,download=False):
        check_url(url,self.provider)
        req=urllib.request.Request(url,headers={'Authorization':'Bearer '+oauth.token(self.provider,self.case_id,self.account_id)})
        try: return OPENER.open(req,timeout=60)
        except urllib.error.HTTPError as exc:
            if exc.code in (301,302,303,307,308) and download and self.provider=='microsoft':
                # Graph supplies a short-lived preauthenticated content URL. Never forward Bearer.
                target=exc.headers.get('Location',''); parsed=urlsplit(target)
                if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in (None,443): raise ProviderError('Ungültige Downloadadresse.') from None
                # Documented Microsoft storage/CDN hosts only; never arbitrary internal URLs.
                if not any(parsed.hostname and (parsed.hostname==host or parsed.hostname.endswith('.'+host)) for host in ('sharepoint.com','1drv.com','onedrive.com','live.com','microsoftpersonalcontent.com')):
                    raise ProviderError('Downloadhost ist noch nicht geprüft und freigegeben.') from None
                try: return OPENER.open(urllib.request.Request(target),timeout=60)
                except urllib.error.HTTPError as error: self.error(error)
            self.error(exc)
        except (OSError,TimeoutError): raise Retryable() from None
    def error(self,error):
        if error.code==429 or error.code>=500 or error.code in (408,403):
            try: delay=int(error.headers.get('Retry-After','10'))
            except ValueError:
                from email.utils import parsedate_to_datetime
                try: delay=max(1,int(parsedate_to_datetime(error.headers['Retry-After']).timestamp()-time.time()))
                except (ValueError,TypeError,KeyError): delay=30
            self.throttled=True
            raise Retryable(delay, error.code in (429,403)) from None
        raise ProviderError('Inhalt nicht zugänglich oder Anmeldung abgelaufen (HTTP '+str(error.code)+').') from None
    def json(self,url):
        for attempt in range(5):
            try:
                with self.request(url) as response:
                    raw=response.read(16*1024*1024+1)
                break
            except (OSError,http.client.IncompleteRead):
                if attempt==4: raise Retryable() from None
                time.sleep(min(30,2**attempt))
            except Retryable as error:
                if attempt==4: raise
                time.sleep(max(error.delay,2**attempt))
        if len(raw)>16*1024*1024: raise ProviderError('Anbieterantwort überschreitet Sicherheitsgrenze.')
        try: return json.loads(raw)
        except ValueError: raise ProviderError('Ungültige Anbieterantwort.') from None
    def pages(self,url,key):
        seen=set()
        while url:
            if url in seen: raise ProviderError('Wiederholte Anbieterseite; Inventarisierung abgebrochen.')
            seen.add(url); data=self.json(url)
            if data.get('incompleteSearch'): self.limits.append('Google meldet eine unvollständige Inventarsuche.')
            if not isinstance(data.get(key),list): raise ProviderError('Anbieterinventar ist unvollständig.')
            yield data[key]
            if self.provider=='google':
                next_token=data.get('nextPageToken')
                # caller base URL never contains pageToken initially
                initial=url.split('&pageToken=')[0]
                url=initial+('&pageToken='+quote(next_token,safe='') if next_token else '') if next_token else None
            else: url=data.get('@odata.nextLink')
    def inventory(self,category,scope=''):
        if category=='calendar':
            yield from self.calendars(scope); return
        if scope: raise ProviderError('Ordnerauswahl wird für diesen Anbieter noch nicht unterstützt.')
        queue=[('root','')]; seen=set()
        while queue:
            identifier,prefix=queue.pop(0)
            if identifier in seen: raise ProviderError('Mehrdeutige Ordnerstruktur; keine vollständige Sicherung möglich.')
            seen.add(identifier)
            if self.provider=='google':
                query={'q':"'"+identifier.replace("'","\\'")+"' in parents and trashed = false",'pageSize':1000,'fields':'nextPageToken,incompleteSearch,files(id,name,mimeType,size,md5Checksum,modifiedTime,createdTime,parents,capabilities,version,description)','supportsAllDrives':'true','includeItemsFromAllDrives':'true'}
                url=self.base+'/drive/v3/files?'+urlencode(query); key='files'
            else: url=self.base+'/me/drive/'+('root' if identifier=='root' else 'items/'+quote(identifier,safe=''))+'/children?$top=200'; key='value'
            for rows in self.pages(url,key):
                for item in rows:
                    item_id=item.get('id'); name=item.get('name')
                    if not isinstance(item_id,str) or not isinstance(name,str): raise ProviderError('Unvollständige Dateimetadaten.')
                    rel=prefix+evidence.source_name(name,item_id)
                    folder=item.get('mimeType')=='application/vnd.google-apps.folder' if self.provider=='google' else 'folder' in item
                    metadata=clean_metadata(item)
                    if 'remoteItem' in item or 'package' in item:
                        self.limits.append('Verknüpftes oder Paketobjekt nicht gesichert: '+item_id); continue
                    if folder:
                        queue.append((item_id,rel+'/'))
                        yield {'id':item_id,'path':rel,'size':0,'directory':True,'metadata':metadata}
                        continue
                    mime=item.get('mimeType',''); export=None
                    if mime.startswith('application/vnd.google-apps.'):
                        formats={'application/vnd.google-apps.document':('application/vnd.openxmlformats-officedocument.wordprocessingml.document','.docx'),
                                 'application/vnd.google-apps.spreadsheet':('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','.xlsx'),
                                 'application/vnd.google-apps.presentation':('application/vnd.openxmlformats-officedocument.presentationml.presentation','.pptx'),
                                 'application/vnd.google-apps.drawing':('application/pdf','.pdf')}
                        if mime not in formats:
                            self.limits.append('Nicht exportierbares Google-Objekt: '+item_id); continue
                        export,extension=formats[mime]; rel+=extension
                    metadata['export_mime']=export
                    yield {'id':item_id,'path':rel,'size':int(item.get('size',-1)) if not export else -1,'metadata':metadata}
    def calendars(self,scope=""):
        if self.provider=="microsoft" and not scope: raise ProviderError("Bitte einen Kalenderzeitraum auswählen.")
        google=self.provider=='google'
        url=self.base+('/calendar/v3/users/me/calendarList?maxResults=250' if google else '/me/calendars?$top=100')
        for rows in self.pages(url,'items' if google else 'value'):
            for calendar in rows:
                cid=calendar['id']; prefix=evidence.source_name(calendar.get('summary',calendar.get('name','Kalender')),cid)+'/'
                raw=json.dumps(clean_metadata(calendar),ensure_ascii=False).encode()
                yield {'id':cid+':calendar','path':prefix+'Kalender.json','size':len(raw),'payload':raw.decode(),'metadata':{'calendar_id':cid,'format':'provider-json'}}
                events=self.base+('/calendar/v3/calendars/'+quote(cid,safe='')+'/events?maxResults=2500&singleEvents=false&showDeleted=true' if google else '/me/calendars/'+quote(cid,safe='')+'/events?$top=100')
                if not google:
                    start,end=scope.split('/')
                    from datetime import date,timedelta
                    try: exclusive_end=(date.fromisoformat(end)+timedelta(days=1)).isoformat()
                    except (ValueError,OverflowError): raise ProviderError('Ungültiges Ende des Kalenderzeitraums.') from None
                    events=self.base+'/me/calendars/'+quote(cid,safe='')+'/calendarView?'+urlencode({'startDateTime':start+'T00:00:00Z','endDateTime':exclusive_end+'T00:00:00Z','$top':100})
                for page_no,items in enumerate(self.pages(events,'items' if google else 'value')):
                    raw=json.dumps(clean_metadata(items),ensure_ascii=False).encode()
                    yield {'id':cid+':page:'+str(page_no),'path':prefix+'Termine-'+str(page_no+1)+'.json','size':len(raw),'payload':raw.decode(),'metadata':{'calendar_id':cid,'format':'provider-json','page':page_no+1}}
    def download(self,record,target,reserve,progress):
        meta=record['metadata']
        if 'payload' in meta:
            content=meta['payload'].encode(); evidence.space(reserve,len(content)); target.write_bytes(content); progress(len(content)); return
        file_id=quote(record['source_id'],safe='')
        if self.provider=='google':
            url=self.base+'/drive/v3/files/'+file_id
            url+=('/export?'+urlencode({'mimeType':meta['export_mime']})) if meta.get('export_mime') else '?alt=media&supportsAllDrives=true'
        else: url=self.base+'/me/drive/items/'+file_id+'/content'
        try:
            with self.request(url,download=True) as response, open(target,'wb') as output:
                count=0
                while chunk:=response.read(256*1024):
                    evidence.space(reserve,len(chunk)); output.write(chunk); count+=len(chunk); progress(count)
                if getattr(response,'length',None) not in (0,None): raise Retryable()
                output.flush(); os.fsync(output.fileno())
        except (OSError,TimeoutError,http.client.IncompleteRead,http.client.RemoteDisconnected) as error:
            if isinstance(error,OSError) and error.errno==28: raise evidence.StorageError('Sicherungsdatenträger voll.') from None
            raise Retryable() from None
        if meta.get('md5Checksum'):
            value=hashlib.md5(usedforsecurity=False)
            with open(target,'rb') as handle:
                while chunk:=handle.read(1024*1024): value.update(chunk)
            if value.hexdigest()!=meta['md5Checksum']: raise Retryable()
        # Detect source changes during transfer. Exported Workspace files have no binary size/hash.
        check=self.json(self.base+('/drive/v3/files/'+file_id+'?fields=id,version,size,modifiedTime' if self.provider=='google' else '/me/drive/items/'+file_id+'?$select=id,eTag,size,lastModifiedDateTime'))
        version_key='version' if self.provider=='google' else 'eTag'
        if not check.get(version_key) or not meta.get(version_key) or str(check.get(version_key))!=str(meta.get(version_key)):
            raise ProviderError('Quelldatei wurde während der Sicherung verändert. Neuen Sicherungslauf starten.')

class AppleDownload(ICloudSession):
    _ENDPOINTS=ICloudSession._ENDPOINTS | frozenset(('operations/copyfile','operations/stat','job/status','job/stop'))
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs); self.limits=[]
    def identity(self):
        value=oauth.load(self.scope.case_id,self.scope.account_id)
        if not value.get('account_identifier'):
            raise ProviderError('Für eine nachvollziehbare Kontozuordnung bitte einmal erneut bei iCloud anmelden.')
        return {'apple_id':value['account_identifier']}
    def inventory(self,category,scope=''):
        queue=[(scope,'')]
        while queue:
            path,prefix=queue.pop(0)
            result=self._rpc('operations/list',{'fs':self.remote+',service='+category+':','remote':path,'opt':{'recurse':False,'metadata':True}})
            if not isinstance(result.get('list'),list): raise ProviderError('iCloud-Dateiliste ist unvollständig.')
            for row in result['list']:
                name=row.get('Name','')
                if not name or name in ('.','..') or any(ord(c)<32 or c in '/\\:' for c in name):
                    self.limits.append('Nicht sicher abbildbarer iCloud-Dateiname ausgelassen.'); continue
                remote=(path+'/' if path else '')+name
                relative=prefix+evidence.source_name(name,remote)
                if row.get('IsDir'):
                    queue.append((remote,relative+'/'))
                    yield {'id':remote,'path':relative,'size':0,'directory':True,'metadata':row}
                else: yield {'id':remote,'path':relative,'size':int(row.get('Size',-1)),'metadata':row}
    def download(self,record,target,reserve,progress):
        fs=self.remote+',service='+record['category']+':'
        # Only a verified local temporary directory can ever be the destination.
        if target.parent.resolve()!=target.parent or not target.name.endswith('.part'): raise ProviderError('Unsicheres Übertragungsziel.')
        result=self._rpc('operations/copyfile',{'srcFs':fs,'srcRemote':record['source_id'],'dstFs':str(target.parent),'dstRemote':target.name,'_async':True,
                         '_config':{'Transfers':1,'MultiThreadStreams':0,'BufferSize':262144,'LowLevelRetries':3,'Retries':1}})
        job=result['jobid']
        try:
            while True:
                evidence.space(reserve)
                progress(target.stat().st_size if target.exists() else 0)
                state=self._rpc('job/status',{'jobid':job})
                if state.get('finished'):
                    if not state.get('success'): raise Retryable(30,True)
                    break
                time.sleep(.5)
            after=self._rpc('operations/stat',{'fs':fs,'remote':record['source_id']}).get('item',{})
            before=record['metadata']
            if any(after.get(k)!=before.get(k) for k in ('Size','ModTime')): raise ProviderError('iCloud-Datei wurde während der Sicherung verändert.')
            if not target.is_file(): raise Retryable()
            progress(target.stat().st_size)
        except BaseException:
            try: self._rpc('job/stop',{'jobid':job})
            except Exception: pass
            raise

@contextmanager
def open_provider(provider,case_id,account_id):
    if provider=='apple':
        status=cloud_auth.status(case_id,account_id)
        if not status['can_browse']: raise ProviderError('Bitte iCloud-Konto erneut anmelden.')
        directory=cloud_auth._directory(case_id,account_id)
        with AppleDownload(directory/'rclone.conf',cloud_auth._key(case_id,account_id),AccountContext(case_id,account_id),timeout=60) as adapter: yield adapter
    else: yield WebProvider(provider,case_id,account_id)
