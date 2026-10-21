import hashlib
import hmac
import os
from pathlib import Path
import secrets
import shutil
from typing import Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from psycopg.errors import UniqueViolation

from backend.db import connect, audit
from backend.identity import identity_provider, verify_password, hash_password, BusyAuthentication

app = FastAPI(title='FORENSIC CLOUD ACQUISITION', version='0.2.0', docs_url=None, redoc_url=None, openapi_url=None)
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
        return value.strip() if isinstance(value, str) and 'password' not in info.field_name else value


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
            audit(conn, user, 'case_created', case['id'], body.operator_initials.upper())
    except UniqueViolation:
        raise HTTPException(409, 'Geschäftszahl bereits vorhanden.')
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
    return {'phase': 1, 'acquisition_available': False, 'evidence_mounted': ready,
            'free_bytes': disk.free if disk else None, 'total_bytes': disk.total if disk else None,
            'note': 'Cloud-Anmeldung und Sicherungen folgen ab Phase 2. Nur Testlabor.'}
