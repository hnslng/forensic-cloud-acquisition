import hashlib
import hmac
import os
from pathlib import Path
import secrets
import shutil
from typing import Literal
from datetime import date
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from psycopg.errors import UniqueViolation

from backend.db import connect, audit
from backend.identity import identity_provider, verify_password, hash_password, BusyAuthentication

app = FastAPI(title='FORENSIC CLOUD ACQUISITION', version='0.5.0', docs_url=None, redoc_url=None, openapi_url=None)
COOKIE = '__Host-fca_session'
CSRF_COOKIE = '__Host-fca_csrf'
USER_FIELDS = 'id,username,initials,role,active,identity_provider,created_at'


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def connection():
    with connect() as conn:
        yield conn


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')

    @field_validator('*', mode='before')
    @classmethod
    def trim_labels(cls, value, info):
        # Password whitespace is significant and must never be silently changed.
        return value.strip() if isinstance(value, str) and 'password' not in info.field_name and info.field_name != 'path' else value


class Login(Input):
    username: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9._-]+$')
    password: str = Field(min_length=1, max_length=256, repr=False)


class NewUser(Input):
    username: str = Field(min_length=3, max_length=64, pattern=r'^[a-z0-9._-]+$')
    initials: str = Field(min_length=1, max_length=12)
    password: str = Field(min_length=14, max_length=256, repr=False)
    role: Literal['admin', 'operator'] = 'operator'


class PasswordChange(Input):
    current_password: str = Field(min_length=1, max_length=256, repr=False)
    new_password: str = Field(min_length=14, max_length=256, repr=False)


class CaseInput(Input):
    business_number: str = Field(min_length=1, max_length=120)
    name: str = Field(default='', max_length=160)
    operator_initials: str = Field(min_length=1, max_length=12)


class CaseUpdate(Input):
    version: int = Field(ge=1)
    name: str = Field(max_length=160)
    status: Literal['active', 'completed', 'archived']
    operator_initials: str = Field(min_length=1, max_length=12)


class Membership(Input):
    user_id: UUID
    access: Literal['editor', 'viewer']


class UserActivity(Input):
    active: bool


class CloudAccountInput(Input):
    provider: Literal['apple', 'google', 'microsoft']
    label: str = Field(min_length=1, max_length=160)


class CloudAccountRename(Input):
    label: str = Field(min_length=1, max_length=160)
    version: int = Field(ge=1)


@app.exception_handler(RequestValidationError)
async def bad_input(request, exc):
    # FastAPI's default error includes the submitted input, potentially passwords.
    return JSONResponse(status_code=422, content={'detail': 'Ungültige Eingaben. Bitte Felder und Längen prüfen.'})


@app.exception_handler(BusyAuthentication)
async def auth_busy(request, exc):
    return JSONResponse(status_code=429, content={'detail': 'Anmeldung ausgelastet. Bitte erneut versuchen.'})


@app.middleware('http')
async def headers_and_origin(request, call_next):
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if request.headers.get('origin') != os.environ['FCA_PUBLIC_ORIGIN']:
            return JSONResponse(status_code=403, content={'detail': 'Unzulässiger Ursprung.'})
        try:
            if int(request.headers.get('content-length', 0)) > 16384:
                return JSONResponse(status_code=413, content={'detail': 'Anfrage zu groß.'})
        except ValueError:
            return JSONResponse(status_code=400, content={'detail': 'Ungültige Anfrage.'})
    result = await call_next(request)
    result.headers['Cache-Control'] = 'no-store'
    result.headers['X-Content-Type-Options'] = 'nosniff'
    result.headers['Referrer-Policy'] = 'no-referrer'
    return result


def identity(request: Request, conn=Depends(connection, scope='function')):
    token = request.cookies.get(COOKIE, '')
    if not token or len(token) > 128:
        raise HTTPException(401, 'Bitte anmelden.')
    row = conn.execute('SELECT u.*, s.csrf_hash FROM sessions s JOIN users u ON u.id=s.user_id '
                       'WHERE s.token_hash=%s AND s.expires_at>now() AND u.active', (digest(token),)).fetchone()
    if not row:
        raise HTTPException(401, 'Sitzung abgelaufen. Bitte erneut anmelden.')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        csrf = request.headers.get('x-csrf-token', '')
        if not csrf or not hmac.compare_digest(row['csrf_hash'], digest(csrf)):
            raise HTTPException(403, 'Sicherheitsprüfung fehlgeschlagen. Bitte neu anmelden.')
    return row


def admin(user=Depends(identity)):
    if user['role'] != 'admin':
        raise HTTPException(403, 'Administratorberechtigung erforderlich.')
    return user


def case_access(conn, user, case_id, write=False):
    case = conn.execute('SELECT * FROM cases WHERE id=%s', (case_id,)).fetchone()
    if not case:
        raise HTTPException(404, 'Fall nicht gefunden.')
    access = conn.execute('SELECT access FROM case_members WHERE case_id=%s AND user_id=%s', (case_id, user['id'])).fetchone()
    if user['role'] != 'admin' and (not access or (write and access['access'] != 'editor')):
        raise HTTPException(404, 'Fall nicht gefunden.')
    return {**case, 'can_edit': user['role'] == 'admin' or bool(access and access['access'] == 'editor')}


@app.get('/api/health')
def health(conn=Depends(connection, scope='function')):
    conn.execute('SELECT 1')
    return {'status': 'ok'}


@app.post('/api/auth/login')
def login(body: Login, response: Response, conn=Depends(connection, scope='function')):
    username = body.username.lower()
    key = digest('login:' + username)
    conn.execute('INSERT INTO login_limits(key_hash) VALUES (%s) ON CONFLICT DO NOTHING', (key,))
    limit = conn.execute('SELECT *, window_start > now()-interval \'10 minutes\' AS recent FROM login_limits WHERE key_hash=%s FOR UPDATE', (key,)).fetchone()
    if limit['recent'] and limit['attempts'] >= 5:
        return JSONResponse(status_code=429, content={'detail': 'Zu viele Anmeldeversuche. In zehn Minuten erneut versuchen.'})
    if not limit['recent']:
        conn.execute('UPDATE login_limits SET attempts=0,window_start=now() WHERE key_hash=%s', (key,))
    user = identity_provider.authenticate(conn, username, body.password)
    if not user:
        conn.execute('UPDATE login_limits SET attempts=attempts+1 WHERE key_hash=%s', (key,))
        audit(conn, None, 'login_failed', details={'subject_hash': key})
        return JSONResponse(status_code=401, content={'detail': 'Anmeldung fehlgeschlagen.'})
    conn.execute('DELETE FROM sessions WHERE expires_at<=now()')
    conn.execute('UPDATE login_limits SET attempts=0 WHERE key_hash=%s', (key,))
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    conn.execute('INSERT INTO sessions(token_hash,csrf_hash,user_id) VALUES (%s,%s,%s)', (digest(token), digest(csrf), user['id']))
    for name, value, http_only in [(COOKIE, token, True), (CSRF_COOKIE, csrf, False)]:
        response.set_cookie(name, value, max_age=28800, secure=True, httponly=http_only, samesite='strict', path='/')
    audit(conn, user, 'login_succeeded')
    return {key: user[key] for key in ('id', 'username', 'initials', 'role')}


@app.get('/api/auth/me')
def me(user=Depends(identity)):
    return {key: user[key] for key in ('id', 'username', 'initials', 'role')}


@app.post('/api/auth/logout')
def logout(request: Request, response: Response, user=Depends(identity), conn=Depends(connection, scope='function')):
    conn.execute('DELETE FROM sessions WHERE token_hash=%s', (digest(request.cookies[COOKIE]),))
    for name in (COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, secure=True, httponly=name == COOKIE, samesite='strict', path='/')
    audit(conn, user, 'logout')
    return {'ok': True}


@app.post('/api/auth/password')
def change_password(body: PasswordChange, user=Depends(identity), conn=Depends(connection, scope='function')):
    if not verify_password(user['password_hash'], body.current_password):
        raise HTTPException(403, 'Aktuelles Passwort stimmt nicht.')
    conn.execute('UPDATE users SET password_hash=%s WHERE id=%s', (hash_password(body.new_password), user['id']))
    conn.execute('DELETE FROM sessions WHERE user_id=%s', (user['id'],))
    audit(conn, user, 'password_changed')
    return {'ok': True, 'reauthentication_required': True}


@app.get('/api/cases')
def cases(user=Depends(identity), conn=Depends(connection, scope='function')):
    return conn.execute("SELECT c.* FROM cases c WHERE %s='admin' OR EXISTS (SELECT 1 FROM case_members m WHERE m.case_id=c.id AND m.user_id=%s) ORDER BY c.created_at DESC LIMIT 500", (user['role'], user['id'])).fetchall()


@app.post('/api/cases', status_code=201)
def create_case(body: CaseInput, user=Depends(identity), conn=Depends(connection, scope='function')):
    try:
        with conn.transaction():
            case = conn.execute('INSERT INTO cases(business_number,name,created_by,operator_initials) VALUES (%s,%s,%s,%s) RETURNING *',
                                (body.business_number, body.name, user['id'], body.operator_initials.upper())).fetchone()
            conn.execute("INSERT INTO case_members(case_id,user_id,access) VALUES (%s,%s,'editor')", (case['id'], user['id']))
            evidence.ensure_case(conn, case)
            audit(conn, user, 'case_created', case['id'], body.operator_initials.upper())
    except UniqueViolation:
        raise HTTPException(409, 'Fallnummer bereits vorhanden.')
    return case


@app.get('/api/cases/{case_id}')
def get_case(case_id: UUID, user=Depends(identity), conn=Depends(connection, scope='function')):
    return case_access(conn, user, case_id)


@app.patch('/api/cases/{case_id}')
def update_case(case_id: UUID, body: CaseUpdate, user=Depends(identity), conn=Depends(connection, scope='function')):
    case_access(conn, user, case_id, write=True)
    row = conn.execute('UPDATE cases SET name=%s,status=%s,version=version+1 WHERE id=%s AND version=%s RETURNING *', (body.name, body.status, case_id, body.version)).fetchone()
    if not row:
        raise HTTPException(409, 'Fall wurde zwischenzeitlich geändert. Bitte neu öffnen.')
    audit(conn, user, 'case_updated', case_id, body.operator_initials.upper(), {'status': body.status, 'name': body.name})
    return row


@app.get('/api/cases/{case_id}/audit')
def case_audit(case_id: UUID, user=Depends(identity), conn=Depends(connection, scope='function')):
    case_access(conn, user, case_id)
    return conn.execute('SELECT a.id,a.occurred_at,a.event_type,a.operator_initials,u.username AS actor,a.details FROM audit_events a LEFT JOIN users u ON u.id=a.actor_id WHERE a.case_id=%s ORDER BY a.id DESC LIMIT 500', (case_id,)).fetchall()


@app.put('/api/cases/{case_id}/members')
def grant_member(case_id: UUID, body: Membership, user=Depends(admin), conn=Depends(connection, scope='function')):
    case_access(conn, user, case_id)
    if not conn.execute('SELECT id FROM users WHERE id=%s AND active', (body.user_id,)).fetchone():
        raise HTTPException(404, 'Benutzer nicht gefunden.')
    conn.execute('INSERT INTO case_members(case_id,user_id,access) VALUES (%s,%s,%s) ON CONFLICT (case_id,user_id) DO UPDATE SET access=excluded.access', (case_id, body.user_id, body.access))
    audit(conn, user, 'case_member_granted', case_id, details={'user_id': str(body.user_id), 'access': body.access})
    return {'ok': True}


@app.get('/api/admin/users')
def list_users(user=Depends(admin), conn=Depends(connection, scope='function')):
    return conn.execute(f'SELECT {USER_FIELDS} FROM users ORDER BY username').fetchall()


@app.get('/api/cases/{case_id}/members')
def list_members(case_id: UUID, user=Depends(admin), conn=Depends(connection, scope='function')):
    case_access(conn, user, case_id)
    return conn.execute('SELECT u.id,u.username,m.access FROM case_members m JOIN users u ON u.id=m.user_id WHERE m.case_id=%s ORDER BY u.username', (case_id,)).fetchall()


@app.delete('/api/cases/{case_id}/members/{user_id}')
def revoke_member(case_id: UUID, user_id: UUID, user=Depends(admin), conn=Depends(connection, scope='function')):
    case_access(conn, user, case_id)
    conn.execute('DELETE FROM case_members WHERE case_id=%s AND user_id=%s', (case_id, user_id))
    audit(conn, user, 'case_member_revoked', case_id, details={'user_id': str(user_id)})
    return {'ok': True}


@app.post('/api/admin/users', status_code=201)
def add_user(body: NewUser, user=Depends(admin), conn=Depends(connection, scope='function')):
    try:
        with conn.transaction():
            new = conn.execute(f'INSERT INTO users(username,initials,password_hash,role) VALUES (%s,%s,%s,%s) RETURNING {USER_FIELDS}', (body.username, body.initials.upper(), hash_password(body.password), body.role)).fetchone()
            audit(conn, user, 'user_created', details={'user_id': str(new['id']), 'role': new['role']})
    except UniqueViolation:
        raise HTTPException(409, 'Benutzername bereits vorhanden.')
    return new


@app.patch('/api/admin/users/{user_id}')
def set_active(user_id: UUID, body: UserActivity, user=Depends(admin), conn=Depends(connection, scope='function')):
    if user_id == user['id']:
        raise HTTPException(409, 'Eigenes Konto kann hier nicht deaktiviert werden.')
    if not conn.execute('UPDATE users SET active=%s WHERE id=%s RETURNING id', (body.active, user_id)).fetchone():
        raise HTTPException(404, 'Benutzer nicht gefunden.')
    if not body.active:
        conn.execute('DELETE FROM sessions WHERE user_id=%s', (user_id,))
    audit(conn, user, 'user_activity_changed', details={'user_id': str(user_id), 'active': body.active})
    return {'ok': True}


@app.get('/api/status')
def status(user=Depends(identity)):
    path = Path(os.environ.get('FCA_EVIDENCE_ROOT', '/evidence'))
    ready = (path / '.fca-volume-id').is_file()
    disk = shutil.disk_usage(path) if path.exists() else None
    return {'phase': 3, 'acquisition_available': ready, 'evidence_mounted': ready,
            'free_bytes': disk.free if disk else None, 'total_bytes': disk.total if disk else None,
            'note': 'Sicherung über den gewählten Datenbereich. Nur Testlabor.'}


@app.get('/api/cases/{case_id}/cloud-accounts')
def cloud_accounts(case_id: UUID, user=Depends(identity), conn=Depends(connection, scope='function')):
    case_access(conn, user, case_id)
    rows = conn.execute('SELECT * FROM cloud_accounts WHERE case_id=%s ORDER BY created_at,id', (case_id,)).fetchall()
    for row in rows:
        row.update(cloud_auth.status(case_id, row['id']) if row['provider'] == 'apple' else oauth.status(row['provider'], case_id, row['id']))
        row['can_acquire'] = row['connection_status'] == 'connected'
        row['acquisition'] = conn.execute('SELECT '+acquisitions.PUBLIC+' FROM acquisitions WHERE account_id=%s ORDER BY created_at DESC LIMIT 1', (row['id'],)).fetchone()
    return rows


@app.post('/api/cases/{case_id}/cloud-accounts', status_code=201)
def add_cloud_account(case_id: UUID, body: CloudAccountInput, user=Depends(identity), conn=Depends(connection, scope='function')):
    case_access(conn, user, case_id, write=True)
    account = conn.execute('INSERT INTO cloud_accounts(case_id,provider,label,created_by) VALUES (%s,%s,%s,%s) RETURNING *',
                           (case_id, body.provider, body.label, user['id'])).fetchone()
    case = case_access(conn,user,case_id,write=True)
    for category in acquisitions.CATEGORIES[body.provider]:
        evidence.ensure_account(conn,case,account,category)
    audit(conn, user, 'cloud_account_added', case_id,
          details={'account_id': str(account['id']), 'provider': body.provider, 'label': body.label})
    return account


@app.patch('/api/cases/{case_id}/cloud-accounts/{account_id}')
def rename_cloud_account(case_id: UUID, account_id: UUID, body: CloudAccountRename, user=Depends(identity), conn=Depends(connection, scope='function')):
    case_access(conn, user, case_id, write=True)
    existing = conn.execute('SELECT id FROM cloud_accounts WHERE id=%s AND case_id=%s', (account_id, case_id)).fetchone()
    if not existing:
        raise HTTPException(404, 'Cloud-Konto nicht gefunden.')
    account = conn.execute('UPDATE cloud_accounts SET label=%s,version=version+1 WHERE id=%s AND case_id=%s AND version=%s RETURNING *',
                           (body.label, account_id, case_id, body.version)).fetchone()
    if not account:
        raise HTTPException(409, 'Cloud-Konto wurde zwischenzeitlich geändert. Bitte aktualisieren.')
    audit(conn, user, 'cloud_account_renamed', case_id, details={'account_id': str(account_id), 'label': body.label})
    return account


# Phase 2: real iCloud authentication and explicitly requested directory reads.
from backend import cloud_auth, evidence, acquisitions, oauth
from providers.apple.adapter import ProviderError


class ICloudLogin(Input):
    apple_id: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024, repr=False)


class ICloudAnswer(Input):
    challenge_id: str = Field(min_length=16, max_length=64, repr=False)
    answer: str = Field(min_length=1, max_length=64, repr=False)


class ICloudBrowse(Input):
    service: Literal['drive', 'photos']
    path: str = Field(default='', max_length=1024)

    @field_validator('path')
    @classmethod
    def relative_directory(cls, value):
        if value and (any(part in ('', '.', '..') for part in value.split('/'))
                      or any(ord(c) < 32 or ord(c) == 127 or c in ':\\' for c in value)):
            raise ValueError('Invalid relative iCloud directory')
        return value


def cloud_access(conn, user, case_id, account_id, write=True):
    case_access(conn, user, case_id, write=write)
    account = conn.execute('SELECT * FROM cloud_accounts WHERE id=%s AND case_id=%s', (account_id, case_id)).fetchone()
    if not account:
        raise HTTPException(404, 'Cloud-Konto nicht gefunden.')
    if account['provider'] != 'apple':
        raise HTTPException(409, 'Diese Anbieteranbindung ist noch nicht verfügbar.')
    return account


@app.get('/api/providers/status')
def providers_status(user=Depends(identity)):
    return {'apple': {'authentication_available': cloud_auth.available(), 'downloads_available': cloud_auth.available()},
            'google': {'authentication_available': oauth.available('google'), 'downloads_available': oauth.available('google')},
            'microsoft': {'authentication_available': oauth.available('microsoft'), 'downloads_available': oauth.available('microsoft')}}


@app.post('/api/cases/{case_id}/cloud-accounts/{account_id}/icloud/{action}')
def icloud_action(case_id: UUID, account_id: UUID, action: Literal['login', 'confirm', 'browse', 'forget'],
                  request: Request, body: dict, user=Depends(identity), conn=Depends(connection, scope='function')):
    cloud_access(conn, user, case_id, account_id)
    if not cloud_auth.available():
        raise HTTPException(503, 'iCloud-Anbindung ist noch nicht eingerichtet.')
    if action in ('login','confirm','forget'):
        idle_account(conn,account_id)
    # Validate BEFORE any provider operation. Generic error never echoes secrets.
    try:
        model = {'login': ICloudLogin, 'confirm': ICloudAnswer, 'browse': ICloudBrowse}.get(action)
        data = model.model_validate(body).model_dump() if model else {}
        if action == 'forget' and body:
            raise ValueError()
        if any('\n' in str(value) or '\r' in str(value) for value in data.values()):
            raise ValueError()
    except ValueError:
        raise HTTPException(422, 'Ungültige Eingaben. Bitte Felder prüfen.') from None
    if action in ('login', 'confirm'):
        conn.execute('INSERT INTO cloud_auth_limits(account_id) VALUES (%s) ON CONFLICT DO NOTHING', (account_id,))
        limit = conn.execute("SELECT *,window_start > now()-interval '10 minutes' AS recent FROM cloud_auth_limits WHERE account_id=%s FOR UPDATE", (account_id,)).fetchone()
        if limit['recent'] and limit['attempts'] >= 8:
            raise HTTPException(429, 'Zu viele iCloud-Anmeldeversuche. In zehn Minuten erneut versuchen.')
        conn.execute("UPDATE cloud_auth_limits SET attempts=CASE WHEN %s THEN attempts+1 ELSE 1 END,window_start=CASE WHEN %s THEN window_start ELSE now() END WHERE account_id=%s", (limit['recent'], limit['recent'], account_id))
    audit(conn, user, 'cloud_' + action + '_requested', case_id, details={'account_id': str(account_id)})
    # Never keep a DB transaction open during external SRP/2FA/network operations.
    conn.commit()
    try:
        result = cloud_auth.perform(case_id, account_id, user['id'], {'login': 'begin', 'confirm': 'answer'}.get(action, action), **data)
    except (cloud_auth.ProviderError, OSError, ValueError) as error:
        # Revalidate identity and permissions after the network call.
        user = identity(request, conn)
        cloud_access(conn, user, case_id, account_id)
        audit(conn, user, 'cloud_' + action + '_failed', case_id, details={'account_id': str(account_id)})
        conn.commit()
        detail = str(error) if isinstance(error, cloud_auth.ProviderError) else 'iCloud-Anfrage fehlgeschlagen.'
        raise HTTPException(409, detail) from None
    user = identity(request, conn)
    cloud_access(conn, user, case_id, account_id)
    audit(conn, user, 'cloud_' + action + '_completed', case_id,
          details={'account_id': str(account_id), 'status': result.get('status', 'read_completed')})
    return result


@app.exception_handler(evidence.StorageError)
async def storage_problem(request, exc):
    return JSONResponse(status_code=409, content={'detail':str(exc)})


def idle_account(conn,account_id):
    if conn.execute("SELECT id FROM acquisitions WHERE account_id=%s AND status IN ('queued','running','pausing')",(account_id,)).fetchone():
        raise HTTPException(409,'Bitte die laufende Sicherung zuerst pausieren.')


def any_cloud_access(conn,user,case_id,account_id):
    case=case_access(conn,user,case_id,write=True)
    row=conn.execute('SELECT * FROM cloud_accounts WHERE case_id=%s AND id=%s',(case_id,account_id)).fetchone()
    if not row: raise HTTPException(404,'Cloud-Konto nicht gefunden.')
    return case,row


class AcquisitionInput(ICloudBrowse):
    service: Literal['drive','photos','calendar']
    calendar_start: date | None = None
    calendar_end: date | None = None


@app.post('/api/cases/{case_id}/cloud-accounts/{account_id}/acquisitions',status_code=201)
def start_acquisition(case_id:UUID,account_id:UUID,body:AcquisitionInput,user=Depends(identity),conn=Depends(connection,scope='function')):
    case,account=any_cloud_access(conn,user,case_id,account_id)
    idle_account(conn,account_id)
    state=cloud_auth.status(case_id,account_id) if account['provider']=='apple' else oauth.status(account['provider'],case_id,account_id)
    if state['connection_status']!='connected': raise HTTPException(409,'Bitte Cloud-Konto zuerst anmelden.')
    scope=body.path
    if account['provider']=='microsoft' and body.service=='calendar':
        if not body.calendar_start or not body.calendar_end or not 0 <= (body.calendar_end-body.calendar_start).days <= 3660:
            raise HTTPException(422,'Kalenderzeitraum angeben (höchstens zehn Jahre je Sicherungslauf).')
        scope=body.calendar_start.isoformat()+'/'+body.calendar_end.isoformat()
    elif body.calendar_start or body.calendar_end:
        raise HTTPException(422,'Kalenderzeitraum ist nur für Outlook vorgesehen.')
    try:
        with conn.transaction(): return acquisitions.enqueue(conn,case,account,user,body.service,scope)
    except UniqueViolation: raise HTTPException(409,'Für dieses Konto ist bereits eine Sicherung vorgemerkt.') from None
    except ProviderError as error: raise HTTPException(409,str(error)) from None


@app.get('/api/cases/{case_id}/acquisitions')
def list_acquisitions(case_id:UUID,user=Depends(identity),conn=Depends(connection,scope='function')):
    case_access(conn,user,case_id)
    return conn.execute('SELECT '+acquisitions.PUBLIC+' FROM acquisitions WHERE case_id=%s ORDER BY created_at DESC LIMIT 500',(case_id,)).fetchall()


@app.post('/api/cases/{case_id}/acquisitions/{job_id}/{action}')
def control_acquisition(case_id:UUID,job_id:UUID,action:Literal['pause','resume'],body:dict,user=Depends(identity),conn=Depends(connection,scope='function')):
    case_access(conn,user,case_id,write=True)
    if body: raise HTTPException(422,'Ungültige Eingaben.')
    row=conn.execute('SELECT * FROM acquisitions WHERE case_id=%s AND id=%s FOR UPDATE',(case_id,job_id)).fetchone()
    if not row: raise HTTPException(404,'Sicherung nicht gefunden.')
    if row['status']=='completed': raise HTTPException(409,'Abgeschlossene Sicherung bleibt unverändert.')
    # Wait for the worker to finish a pause before allowing a second consumer.
    if action=='pause' and row['status'] not in ('queued','running','pausing'): raise HTTPException(409,'Nur wartende oder laufende Sicherungen können pausiert werden.')
    if action=='resume' and row['status'] not in ('paused','failed','incomplete'): raise HTTPException(409,'Sicherung wird noch verarbeitet.')
    if action=='resume':
        evidence.space(acquisitions.settings(conn)['reserve_bytes'])
        if row['status']=='incomplete':
            raise HTTPException(409,'Unvollständigen Umfang über einen neuen Sicherungslauf erneut erfassen.')
    new='pausing' if action=='pause' and row['status']=='running' else ('paused' if action=='pause' else 'queued')
    try:
        with conn.transaction():
            conn.execute('UPDATE acquisitions SET status=%s,reason=%s WHERE id=%s',(new,'Pause angefordert.' if action=='pause' else None,job_id))
    except UniqueViolation: raise HTTPException(409,'Für dieses Konto existiert bereits ein anderer aktiver Sicherungslauf.') from None
    audit(conn,user,'acquisition_'+action,case_id,details={'acquisition_id':str(job_id)})
    return {'status':new}


@app.get('/api/admin/acquisition-settings')
def acquisition_settings(user=Depends(admin),conn=Depends(connection,scope='function')):
    return {**acquisitions.settings(conn),'providers':{p:oauth.available(p) for p in ('google','microsoft')},'resources':acquisitions.resources()}


class AcquisitionSettings(Input):
    file_parallelism:int=Field(ge=1,le=4)
    account_parallelism:int=Field(ge=1,le=2)
    reserve_bytes:int=Field(ge=1073741824,le=107374182400)


@app.put('/api/admin/acquisition-settings')
def save_acquisition_settings(body:AcquisitionSettings,user=Depends(admin),conn=Depends(connection,scope='function')):
    conn.execute('UPDATE acquisition_settings SET file_parallelism=%s,account_parallelism=%s,reserve_bytes=%s WHERE singleton',(body.file_parallelism,body.account_parallelism,body.reserve_bytes))
    audit(conn,user,'acquisition_settings_updated',details=body.model_dump())
    return {'ok':True}


@app.post('/api/cases/{case_id}/cloud-accounts/{account_id}/oauth/begin')
def oauth_begin(case_id:UUID,account_id:UUID,body:dict,user=Depends(identity),conn=Depends(connection,scope='function')):
    _,account=any_cloud_access(conn,user,case_id,account_id)
    idle_account(conn,account_id)
    if body or account['provider'] not in ('google','microsoft'): raise HTTPException(422,'Ungültiger Anbieter.')
    audit(conn,user,'cloud_login_requested',case_id,details={'account_id':str(account_id)}); conn.commit()
    try: return oauth.begin(account['provider'],case_id,account_id,user['id'])
    except ProviderError as error: raise HTTPException(409,str(error)) from None


class OAuthComplete(Input):
    case_id:UUID
    account_id:UUID
    state:str=Field(min_length=16,max_length=512,repr=False)
    code:str=Field(min_length=1,max_length=8192,repr=False)


@app.get('/api/oauth/callback')
def oauth_callback():
    from fastapi.responses import HTMLResponse
    return HTMLResponse('<!doctype html><html lang="de"><meta charset="utf-8"><title>FCA Anmeldung</title><p id="result">Anmeldung wird abgeschlossen …</p><script src="/oauth-callback.js" defer></script></html>')


@app.post('/api/oauth/complete')
def oauth_complete(body:OAuthComplete,user=Depends(identity),conn=Depends(connection,scope='function')):
    _,account=any_cloud_access(conn,user,body.case_id,body.account_id)
    idle_account(conn,body.account_id)
    if account['provider'] not in ('google','microsoft'): raise HTTPException(422,'Ungültiger Anbieter.')
    conn.commit()
    try: result=oauth.complete(account['provider'],body.case_id,body.account_id,user['id'],body.state,body.code)
    except ProviderError as error: raise HTTPException(409,str(error)) from None
    any_cloud_access(conn,user,body.case_id,body.account_id)
    audit(conn,user,'cloud_login_completed',body.case_id,details={'account_id':str(body.account_id)})
    return result


class OAuthConfiguration(Input):
    provider:Literal['google','microsoft']
    client_id:str=Field(min_length=1,max_length=512)
    client_secret:str=Field(min_length=1,max_length=2048,repr=False)
    redirect_uri:str=Field(min_length=10,max_length=1024)


@app.put('/api/admin/oauth-settings')
def oauth_settings(body:OAuthConfiguration,user=Depends(admin),conn=Depends(connection,scope='function')):
    from urllib.parse import urlsplit
    uri=urlsplit(body.redirect_uri)
    if (uri.scheme!='https' or not uri.hostname or uri.username or uri.password or uri.query or uri.fragment
            or uri.path!='/api/oauth/callback' or body.redirect_uri!=os.environ['FCA_PUBLIC_ORIGIN']+'/api/oauth/callback'):
        raise HTTPException(422,'Rückkehradresse muss der HTTPS-Adresse dieser FCA-Installation mit /api/oauth/callback entsprechen.')
    if conn.execute("SELECT j.id FROM acquisitions j JOIN cloud_accounts a ON a.id=j.account_id WHERE a.provider=%s AND j.status IN ('queued','running','pausing')",(body.provider,)).fetchone():
        raise HTTPException(409,'Für diesen Anbieter läuft noch eine Sicherung.')
    oauth.save_configuration(body.provider,body.client_id,body.client_secret,body.redirect_uri)
    audit(conn,user,'oauth_application_configured',details={'provider':body.provider})
    return {'ok':True}


@app.get('/api/cases/{case_id}/acquisitions/{job_id}/report/{kind}')
def acquisition_report(case_id:UUID,job_id:UUID,kind:Literal['bericht','dateien'],user=Depends(identity),conn=Depends(connection,scope='function')):
    from fastapi.responses import FileResponse
    case_access(conn,user,case_id)
    job=conn.execute('SELECT directory,status FROM acquisitions WHERE case_id=%s AND id=%s',(case_id,job_id)).fetchone()
    if not job: raise HTTPException(404,'Sicherung nicht gefunden.')
    name='Sicherungsbericht.json' if kind=='bericht' else 'Dateien.jsonl'
    path=evidence.file_path(evidence.directory(job['directory']+'/_FCA'),name)
    if not path.is_file(): raise HTTPException(404,'Bericht ist noch nicht verfügbar.')
    return FileResponse(path,media_type='application/json' if kind=='bericht' else 'application/x-ndjson',filename=str(job_id)+'-'+name)
