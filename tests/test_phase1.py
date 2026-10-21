"""Real PostgreSQL integration tests; always isolated from the lab database."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
import pytest
from fastapi.testclient import TestClient

from backend.db import connect
from backend.identity import hash_password
from backend.main import app, COOKIE, CSRF_COOKIE

PASSWORD = 'Synthetic-Test-Only-2026!'
ORIGIN = 'https://fca.test'


def migration_connection():
    assert os.environ.get('FCA_DB_NAME') == 'fca_test_phase1', 'Never test against the working database'
    return psycopg.connect(host=os.environ.get('FCA_DB_HOST', 'database'), dbname='fca_test_phase1',
                          user='fca_migrate', password=Path(os.environ['FCA_TEST_MIGRATION_PASSWORD_FILE']).read_text().strip(), row_factory=dict_row)


@pytest.fixture(autouse=True)
def synthetic_database():
    with migration_connection() as c:
        c.execute('TRUNCATE audit_events,case_members,cases,sessions,login_limits,users RESTART IDENTITY CASCADE')
        for name, role in [('admin', 'admin'), ('alice', 'operator'), ('bob', 'operator')]:
            c.execute('INSERT INTO users(username,initials,password_hash,role) VALUES (%s,%s,%s,%s)', (name, name[:3].upper(), hash_password(PASSWORD), role))


def client(name='alice'):
    c = TestClient(app, base_url=ORIGIN, headers={'Origin': ORIGIN})
    r = c.post('/api/auth/login', json={'username': name, 'password': PASSWORD})
    assert r.status_code == 200, r.text
    c.headers['X-CSRF-Token'] = c.cookies[CSRF_COOKIE]
    return c


def new_case(c, number='SYNTHETIC-2026-001'):
    r = c.post('/api/cases', json={'business_number': number, 'name': 'Synthetischer Testfall', 'operator_initials': 'QA'})
    assert r.status_code == 201, r.text
    return r.json()


def test_login_cookie_flags_and_session_hash_storage():
    c = client()
    assert all(cookie.secure for cookie in c.cookies.jar)
    with migration_connection() as db:
        row = db.execute('SELECT token_hash,csrf_hash FROM sessions').fetchone()
        assert row['token_hash'] == hashlib.sha256(c.cookies[COOKIE].encode()).hexdigest()
        assert row['token_hash'] != c.cookies[COOKIE]
    assert c.get('/api/auth/me').json()['username'] == 'alice'


def test_unauthenticated_and_cross_origin_requests_are_rejected():
    c = TestClient(app, base_url=ORIGIN)
    assert c.get('/api/cases').status_code == 401
    assert c.post('/api/auth/login', headers={'Origin': 'https://untrusted.invalid'}, json={'username': 'alice', 'password': PASSWORD}).status_code == 403


def test_csrf_is_required_for_case_changes():
    c = client(); del c.headers['X-CSRF-Token']
    assert c.post('/api/cases', json={'business_number': 'SYNTHETIC', 'operator_initials': 'QA'}).status_code == 403


def test_failure_rate_limit_and_validation_do_not_echo_password():
    c = TestClient(app, base_url=ORIGIN, headers={'Origin': ORIGIN})
    for _ in range(5):
        assert c.post('/api/auth/login', json={'username': 'alice', 'password': 'synthetic-invalid'}).status_code == 401
    assert c.post('/api/auth/login', json={'username': 'alice', 'password': PASSWORD}).status_code == 429
    r = c.post('/api/auth/login', json={'username': 'bob', 'password': 'X' * 257})
    assert r.status_code == 422 and 'X' * 257 not in r.text


def test_case_creation_duplicate_and_operator_record():
    c = client(); case = new_case(c)
    assert case['operator_initials'] == 'QA' and case['id']
    assert c.post('/api/cases', json={'business_number': case['business_number'], 'operator_initials': 'QA'}).status_code == 409
    a = c.get('/api/cases/' + case['id'] + '/audit').json()[0]
    assert a['event_type'] == 'case_created' and a['actor'] == 'alice' and a['operator_initials'] == 'QA'


def test_case_separation_for_list_read_write_and_audit():
    alice, bob = client(), client('bob'); case = new_case(alice)
    assert bob.get('/api/cases').json() == []
    for path in ['', '/audit']:
        assert bob.get('/api/cases/' + case['id'] + path).status_code == 404
    assert bob.patch('/api/cases/' + case['id'], json={'name': 'forbidden', 'status': 'active', 'operator_initials': 'ADMIN', 'version': 1}).status_code == 404


def test_initials_cannot_grant_administration_or_case_access():
    alice = client(); new_case(alice)
    assert alice.get('/api/admin/users').status_code == 403
    assert alice.post('/api/admin/users', json={'username': 'illegal', 'initials': 'ADM', 'password': PASSWORD, 'role': 'admin'}).status_code == 403
    assert alice.post('/api/cases', json={'business_number': 'SYNTHETIC-X', 'operator_initials': 'ADMIN', 'role': 'admin'}).status_code == 422


def test_admin_grants_viewer_and_editor_membership():
    alice, bob, admin = client(), client('bob'), client('admin'); case = new_case(alice)
    user_id = next(u['id'] for u in admin.get('/api/admin/users').json() if u['username'] == 'bob')
    assert admin.put('/api/cases/' + case['id'] + '/members', json={'user_id': user_id, 'access': 'viewer'}).status_code == 200
    assert bob.get('/api/cases/' + case['id']).json()['can_edit'] is False
    update = {'name': 'synthetic edit', 'status': 'active', 'operator_initials': 'BOB', 'version': 1}
    assert bob.patch('/api/cases/' + case['id'], json=update).status_code == 404
    assert admin.put('/api/cases/' + case['id'] + '/members', json={'user_id': user_id, 'access': 'editor'}).status_code == 200
    assert bob.patch('/api/cases/' + case['id'], json=update).status_code == 200
    assert admin.delete('/api/cases/' + case['id'] + '/members/' + user_id).status_code == 200
    assert bob.get('/api/cases/' + case['id']).status_code == 404


def test_concurrent_edits_detect_stale_version():
    c = client(); case = new_case(c)
    update = {'name': 'first change', 'status': 'completed', 'operator_initials': 'QA', 'version': 1}
    assert c.patch('/api/cases/' + case['id'], json=update).status_code == 200
    assert c.patch('/api/cases/' + case['id'], json=update).status_code == 409


def test_multiple_users_create_cases_in_parallel():
    clients = [client(), client('bob')]
    with ThreadPoolExecutor(2) as pool:
        rows = list(pool.map(lambda i: new_case(clients[i], 'SYNTHETIC-PARALLEL-' + str(i)), range(2)))
    assert rows[0]['id'] != rows[1]['id']
    assert len(clients[0].get('/api/cases').json()) == len(clients[1].get('/api/cases').json()) == 1


def test_logout_expiry_and_disabled_users_revoke_access():
    c, admin = client(), client('admin'); token = c.cookies[COOKIE]
    assert c.post('/api/auth/logout', json={}).status_code == 200
    old = TestClient(app, base_url=ORIGIN); old.cookies.set(COOKIE, token)
    assert old.get('/api/cases').status_code == 401
    c = client()
    with migration_connection() as db:
        db.execute("UPDATE sessions SET expires_at=now()-interval '1 second' WHERE token_hash=%s", (hashlib.sha256(c.cookies[COOKIE].encode()).hexdigest(),))
    assert c.get('/api/cases').status_code == 401
    c = client(); user_id = c.get('/api/auth/me').json()['id']
    assert admin.patch('/api/admin/users/' + user_id, json={'active': False}).status_code == 200
    assert c.get('/api/cases').status_code == 401


def test_password_change_revokes_all_sessions():
    c, other = client(), client()
    assert c.post('/api/auth/password', json={'current_password': PASSWORD, 'new_password': 'Synthetic-new-password-2026!'}).status_code == 200
    assert c.get('/api/auth/me').status_code == other.get('/api/auth/me').status_code == 401


def test_api_database_role_cannot_alter_audit_or_schema():
    with connect() as c:
        assert c.execute('SELECT current_user').fetchone()['current_user'] == 'fca_api'
        for statement in ['DELETE FROM audit_events', "CREATE TABLE unauthorized (id int)", 'SELECT * FROM schema_migrations']:
            with pytest.raises(psycopg.errors.InsufficientPrivilege), c.transaction():
                c.execute(statement)


def test_admin_creates_user_without_disclosing_hash():
    c = client('admin')
    r = c.post('/api/admin/users', json={'username': 'newuser', 'initials': 'NEW', 'password': PASSWORD, 'role': 'operator'})
    assert r.status_code == 201 and 'password' not in r.text
    assert client('newuser').get('/api/auth/me').json()['role'] == 'operator'


def test_password_whitespace_is_significant():
    c = client()
    password = '  Synthetic-spaces-password!  '
    assert c.post('/api/auth/password', json={'current_password': PASSWORD, 'new_password': password}).status_code == 200
    r = c.post('/api/auth/login', json={'username': 'alice', 'password': password.strip()})
    assert r.status_code == 401
    assert c.post('/api/auth/login', json={'username': 'alice', 'password': password}).status_code == 200
