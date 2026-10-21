"""Official delegated authorization-code + PKCE; encrypted tokens outside the DB."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlencode
import urllib.request
from cryptography.fernet import Fernet, InvalidToken
from backend import cloud_auth
from providers.apple.adapter import ProviderError

LOCK = threading.RLock()
GOOGLE_SCOPES = 'https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/calendar.readonly'
MICROSOFT_SCOPES = 'offline_access Files.Read Calendars.Read User.Read'

def configuration(provider):
    try:
        value = json.loads(Path(os.environ.get('FCA_OAUTH_CONFIG_FILE','/etc/fca/oauth-apps.json')).read_text())[provider]
        if not value['client_id'] or not value.get('client_secret') or not value.get('redirect_uri','').startswith('https://'): return None
        return value
    except (OSError, ValueError, KeyError, TypeError):
        from uuid import UUID
        try:
            value=load(UUID(int=0),UUID(int=0)).get(provider)
            return value if value and value.get('client_id') and value.get('client_secret') and value.get('redirect_uri','').startswith('https://') else None
        except (OSError,ProviderError,KeyError): return None

def available(provider):
    return provider in ('google','microsoft') and configuration(provider) is not None and Path(os.environ.get('FCA_CLOUD_MASTER_KEY_FILE','/missing')).is_file()

def vault(case_id, account_id):
    key = base64.urlsafe_b64encode(bytes.fromhex(cloud_auth._key(case_id, account_id)))
    return cloud_auth._directory(case_id, account_id) / 'oauth.enc', Fernet(key)

def load(case_id, account_id):
    path, cipher = vault(case_id, account_id)
    if not path.exists(): return {}
    if path.is_symlink(): raise ProviderError('Ungültiger Anmeldedatenspeicher.')
    try: return json.loads(cipher.decrypt(path.read_bytes()))
    except (InvalidToken, ValueError): raise ProviderError('Anmeldedaten sind nicht lesbar.') from None

def save(case_id, account_id, value):
    path, cipher = vault(case_id, account_id)
    temp = path.with_name('oauth-' + secrets.token_hex(8) + '.tmp')
    fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd,'wb') as handle:
        handle.write(cipher.encrypt(json.dumps(value).encode())); handle.flush(); os.fsync(handle.fileno())
    os.replace(temp, path)

def endpoints(provider):
    if provider == 'google': return 'https://accounts.google.com/o/oauth2/v2/auth', 'https://oauth2.googleapis.com/token', GOOGLE_SCOPES
    return 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize', 'https://login.microsoftonline.com/common/oauth2/v2.0/token', MICROSOFT_SCOPES

def begin(provider, case_id, account_id, user_id, session_id=None):
    config = configuration(provider)
    if not available(provider): raise ProviderError('Anbieteranwendung muss zuerst in den Einstellungen eingerichtet werden.')
    verifier, nonce = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    with LOCK:
        value = load(case_id,account_id)
        value['pending'] = {'verifier':verifier,'state':nonce,'user_id':str(user_id),
                            'session_id':session_id, 'provider':provider,
                            'client_id':config['client_id'],'redirect_uri':config['redirect_uri'],
                            'expires':time.time()+600}
        save(case_id,account_id,value)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    authorize, _, scope = endpoints(provider)
    query = dict(client_id=config['client_id'],redirect_uri=config['redirect_uri'],response_type='code',scope=scope,state=nonce,code_challenge=challenge,code_challenge_method='S256',prompt='consent')
    if provider == 'google': query['access_type'] = 'offline'
    return {'url':authorize+'?'+urlencode(query)}

def exchange(provider, params):
    config = configuration(provider)
    _, url, _ = endpoints(provider)
    params.update(client_id=config['client_id'])
    if config.get('client_secret'): params['client_secret'] = config['client_secret']
    req = urllib.request.Request(url, data=urlencode(params).encode(), headers={'Content-Type':'application/x-www-form-urlencoded'})
    try:
        with urllib.request.urlopen(req,timeout=30) as response: value = json.loads(response.read(1024*1024))
        if not value.get('access_token'): raise ValueError()
        return value
    except Exception: raise ProviderError('Anbieteranmeldung fehlgeschlagen oder abgelaufen. Bitte erneut verbinden.') from None

def complete(provider, case_id, account_id, user_id, state, code, session_id=None):
    with LOCK:
        value = load(case_id,account_id); pending = value.pop('pending',{})
        config=configuration(provider)
        if (not config or pending.get('user_id') != str(user_id) or pending.get('expires',0)<time.time()
                or not secrets.compare_digest(pending.get('state',''),state)
                or pending.get('session_id') != session_id
                or (pending.get('provider') is not None and pending['provider'] != provider)
                or (pending.get('client_id') is not None and pending['client_id'] != config['client_id'])
                or (pending.get('redirect_uri') is not None and pending['redirect_uri'] != config['redirect_uri'])):
            raise ProviderError('Anmeldung abgelaufen oder nicht dieser Sitzung zugeordnet.')
        save(case_id,account_id,value) # one-use before network
        token = exchange(provider,dict(grant_type='authorization_code',code=code,redirect_uri=configuration(provider)['redirect_uri'],code_verifier=pending['verifier']))
        token['authorized_at'] = time.time()
        token['requested_scopes'] = endpoints(provider)[2].split()
        token['oauth_client_id'] = config['client_id']
        token['expires_at'] = time.time()+int(token.get('expires_in',3600))-60
        save(case_id,account_id,token)
    return {'status':'connected'}

def token(provider, case_id, account_id):
    with LOCK:
        value = load(case_id,account_id)
        if value.get('expires_at',0)<=time.time():
            if not value.get('refresh_token'): raise ProviderError('Bitte Cloud-Konto erneut anmelden.')
            refreshed = exchange(provider,dict(grant_type='refresh_token',refresh_token=value['refresh_token']))
            value.update(refreshed); value['expires_at'] = time.time()+int(value.get('expires_in',3600))-60
            save(case_id,account_id,value)
        if not value.get('access_token'): raise ProviderError('Bitte Cloud-Konto zuerst anmelden.')
        return value['access_token']

def status(provider, case_id, account_id):
    ready = available(provider)
    value = load(case_id,account_id) if ready else {}
    connected = bool(value.get('refresh_token') or (value.get('access_token') and value.get('expires_at',0)>time.time()))
    return {'connection_status':'connected' if connected else ('disconnected' if ready else 'unavailable'), 'can_authenticate':ready,'can_browse':False, 'can_acquire':connected}


def save_configuration(provider, client_id, client_secret, redirect_uri):
    """Admin-managed application registration, encrypted with the external master key."""
    from uuid import UUID
    case_id=account_id=UUID(int=0)
    with LOCK:
        values=load(case_id,account_id)
        values[provider]={'client_id':client_id,'client_secret':client_secret,'redirect_uri':redirect_uri}
        save(case_id,account_id,values)
