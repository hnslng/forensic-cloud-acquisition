"""API/security tests with explicitly synthetic provider responses, never Apple acceptance."""
import os
from pathlib import Path
from uuid import UUID

import pytest
from providers.apple.adapter import AuthStep, ProviderError
from backend import cloud_auth
from test_phase1 import synthetic_database, client, new_case, migration_connection


@pytest.fixture
def synthetic_icloud(monkeypatch, tmp_path):
    root = tmp_path / 'cloud-auth'
    root.mkdir(mode=0o700)
    key = tmp_path / 'cloud-key'
    key.write_text('Synthetic-Master-Key-For-Tests-Only-Long-Enough-2026')
    monkeypatch.setenv('FCA_CLOUD_AUTH_ROOT', str(root))
    monkeypatch.setenv('FCA_CLOUD_MASTER_KEY_FILE', str(key))
    monkeypatch.setattr(cloud_auth, 'available', lambda: True)
    calls = []
    class SyntheticSession:
        def __init__(self, path, key, context):
            self._state = '2fa_do'
            calls.append(('context', context))
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def begin(self, apple_id, password):
            assert apple_id == 'synthetic@example.invalid'
            assert password == '  Synthetic-Apple-Password  '
            return AuthStep('challenge', 'config_2fa')
        def resume_challenge(self, state, field, choices):
            assert state == '2fa_do' and field == 'config_2fa'
        def answer(self, code):
            if code != '123456': raise ProviderError('synthetic safe failure')
            return AuthStep('authenticated')
        def browse(self, service, path):
            calls.append(('browse', service, path))
            return [{'name': 'Synthetic-folder', 'path': 'Synthetic-folder', 'is_dir': True, 'size': -1}]
        def forget(self): calls.append(('forget',))
    monkeypatch.setattr(cloud_auth, 'ICloudSession', SyntheticSession)
    return calls, root


def account(c, case):
    return c.post('/api/cases/' + case['id'] + '/cloud-accounts', json={'provider': 'apple', 'label': 'Synthetic iCloud'}).json()


def path(case, cloud):
    return '/api/cases/' + case['id'] + '/cloud-accounts/' + cloud['id'] + '/icloud/'


def login(c, base):
    return c.post(base + 'login', json={'apple_id': 'synthetic@example.invalid', 'password': '  Synthetic-Apple-Password  '})


def test_synthetic_icloud_login_2fa_browse_forget_and_audit(synthetic_icloud):
    calls, root = synthetic_icloud
    c = client(); case = new_case(c); cloud = account(c, case); base = path(case, cloud)
    assert c.post(base + 'browse', json={'service': 'drive', 'path': ''}).status_code == 409
    challenge = login(c, base)
    assert challenge.status_code == 200, challenge.text
    challenge = challenge.json()
    assert challenge['status'] == 'challenge' and 'state' not in challenge
    assert c.post(base + 'confirm', json={'challenge_id': 'wrong-challenge-value', 'answer': '123456'}).status_code == 409
    result = c.post(base + 'confirm', json={'challenge_id': challenge['challenge_id'], 'answer': '123456'})
    assert result.json()['status'] == 'connected'
    accounts = c.get('/api/cases/' + case['id'] + '/cloud-accounts').json()
    assert accounts[0]['can_browse'] and accounts[0]['connection_status'] == 'connected'
    assert accounts[0]['acquisition_status'] == 'unavailable'
    # No listing is triggered by successful authentication or catalog reads.
    assert not any(call[0] == 'browse' for call in calls)
    result = c.post(base + 'browse', json={'service': 'drive', 'path': ''})
    assert result.json()['entries'][0]['name'] == 'Synthetic-folder'
    assert not result.json()['downloads_available']
    for invalid in ['../other', 'folder//other', 'other:root']:
        assert c.post(base + 'browse', json={'service': 'drive', 'path': invalid}).status_code == 422
    assert c.post(base + 'forget', json={}).json()['status'] == 'disconnected'
    events = c.get('/api/cases/' + case['id'] + '/audit').json()
    assert any(e['event_type'] == 'cloud_confirm_completed' for e in events)
    assert any(e['event_type'] == 'cloud_browse_completed' for e in events)
    for forbidden in ['Synthetic-Apple-Password', 'synthetic@example.invalid', challenge['challenge_id'], '123456']:
        assert forbidden not in str(events)
        assert not any(forbidden in file.read_text() for file in root.rglob('*.json'))


def test_icloud_case_viewer_csrf_and_challenge_owner(synthetic_icloud):
    c, bob, admin = client(), client('bob'), client('admin')
    case = new_case(c); cloud = account(c, case); base = path(case, cloud)
    assert login(bob, base).status_code == 404
    bob_id = bob.get('/api/auth/me').json()['id']
    admin.put('/api/cases/' + case['id'] + '/members', json={'user_id': bob_id, 'access': 'viewer'})
    assert login(bob, base).status_code == 404
    assert bob.post(base + 'browse', json={'service': 'drive'}).status_code == 404
    admin.put('/api/cases/' + case['id'] + '/members', json={'user_id': bob_id, 'access': 'editor'})
    challenge = login(c, base).json()
    assert bob.post(base + 'confirm', json={'challenge_id': challenge['challenge_id'], 'answer': '123456'}).status_code == 409
    with migration_connection() as db:
        db.execute('DELETE FROM case_members WHERE case_id=%s AND user_id=%s', (case['id'], c.get('/api/auth/me').json()['id']))
    assert c.post(base + 'confirm', json={'challenge_id': challenge['challenge_id'], 'answer': '123456'}).status_code == 404
    c = client('admin'); del c.headers['X-CSRF-Token']
    assert login(c, base).status_code == 403


def test_icloud_rate_limit_validation_and_unimplemented_provider(synthetic_icloud):
    c = client(); case = new_case(c); cloud = account(c, case); base = path(case, cloud)
    for _ in range(8): assert login(c, base).status_code == 200
    assert login(c, base).status_code == 429
    bad = c.post(base + 'login', json={'apple_id': 'x', 'password': 'SECRET-INPUT', 'role': 'admin'})
    assert bad.status_code == 422 and 'SECRET-INPUT' not in bad.text
    other = c.post('/api/cases/' + case['id'] + '/cloud-accounts', json={'provider': 'google', 'label': 'Synthetic Google'}).json()
    assert login(c, path(case, other)).status_code == 409


def test_expired_challenge_and_separate_keys(synthetic_icloud):
    calls, root = synthetic_icloud
    c = client(); case = new_case(c); cloud = account(c, case); base = path(case, cloud)
    challenge = login(c, base).json()
    directory = root / case['id'] / cloud['id']
    cloud_auth._write_state(directory, {'status': 'challenge', 'expires': 1})
    assert c.post(base + 'confirm', json={'challenge_id': challenge['challenge_id'], 'answer': '123456'}).status_code == 409
    assert cloud_auth.status(UUID(case['id']), UUID(cloud['id']))['connection_status'] == 'expired'
    assert cloud_auth._key(case['id'], cloud['id']) != cloud_auth._key(case['id'], str(UUID(int=1)))
    assert cloud_auth._key(case['id'], cloud['id']) != cloud_auth._key(str(UUID(int=1)), cloud['id'])
