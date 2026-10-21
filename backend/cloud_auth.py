"""iCloud connection boundary. Provider secrets stay in per-account encrypted files.

No downloads; browsing only after an explicit case-authorized request. The
application database stores no Apple credentials or cookies.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import stat
import threading
import time
from uuid import UUID

from providers.apple.adapter import AccountContext, ICloudSession, ProviderError

_GATE = threading.BoundedSemaphore(1)


def available():
    return (os.environ.get('FCA_ICLOUD_ENABLED') == '1'
            and Path(os.environ.get('FCA_CLOUD_MASTER_KEY_FILE', '/not-configured')).is_file()
            and Path('/usr/local/bin/rclone').is_file())


def _directory(case_id, account_id):
    root = Path(os.environ['FCA_CLOUD_AUTH_ROOT']).absolute()
    if root.resolve() != root or root.is_symlink():
        raise ProviderError('Ungültiges Anmeldedatenverzeichnis.')
    for path in [root, root / str(case_id), root / str(case_id) / str(account_id)]:
        path.mkdir(mode=0o700, exist_ok=True)
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ProviderError('Anmeldedatenverzeichnis ist nicht ausreichend geschützt.')
    return path


def _key(case_id, account_id):
    master = Path(os.environ['FCA_CLOUD_MASTER_KEY_FILE']).read_bytes().strip()
    if len(master) < 48:
        raise ProviderError('Cloud-Schlüssel ist nicht eingerichtet.')
    return hmac.new(master, f'fca-icloud-v1:{case_id}:{account_id}'.encode(), hashlib.sha256).hexdigest()


def _read_state(directory):
    path = directory / 'connection.json'
    if not path.exists():
        return {'status': 'disconnected'}
    if path.is_symlink() or path.stat().st_size > 8192:
        raise ProviderError('Ungültiger Anmeldestatus.')
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError):
        raise ProviderError('Anmeldestatus ist nicht lesbar.') from None


def _write_state(directory, state):
    path = directory / ('state-' + secrets.token_hex(8) + '.tmp')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        json.dump(state, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(path, directory / 'connection.json')


def status(case_id, account_id):
    """Public metadata only. Never return internal challenge state, cookies or keys."""
    if not available():
        return {'connection_status': 'unavailable', 'can_authenticate': False, 'can_browse': False}
    state = _read_state(_directory(case_id, account_id))
    value = state.get('status', 'disconnected')
    if value == 'challenge' and state.get('expires', 0) < time.time():
        value = 'expired'
    # Upstream trust normally lasts 30 days; use conservative 29-day deadline.
    if value == 'connected' and state.get('expires', 0) < time.time():
        value = 'expired'
    if value not in ('challenge', 'connected', 'expired', 'disconnected', 'error'):
        value = 'disconnected'
    return {'connection_status': value, 'can_authenticate': True, 'can_browse': value == 'connected'}


def _step_state(adapter, step, user_id):
    if step.status == 'authenticated':
        return {'status': 'connected', 'expires': time.time() + 29 * 86400}
    return {'status': 'challenge', 'expires': time.time() + 600,
            'user_id': str(user_id), 'challenge_id': secrets.token_urlsafe(24),
            'state': adapter._state, 'field': step.field, 'choices': list(step.choices)}


def _public_step(state):
    if state['status'] == 'connected':
        return {'status': 'connected'}
    return {'status': 'challenge', 'challenge_id': state['challenge_id'],
            'field': state['field'], 'choices': state['choices']}


def perform(case_id, account_id, user_id, action, *, apple_id=None, password=None,
            challenge_id=None, answer=None, service=None, path=None):
    if not available():
        raise ProviderError('iCloud-Anbindung ist nicht eingerichtet.')
    if not _GATE.acquire(blocking=False):
        raise ProviderError('Eine iCloud-Anfrage läuft bereits. Bitte kurz warten.')
    try:
        directory = _directory(case_id, account_id)
        context = AccountContext(UUID(str(case_id)), UUID(str(account_id)))
        with ICloudSession(directory / 'rclone.conf', _key(case_id, account_id), context) as adapter:
            state = _read_state(directory)
            if action == 'begin':
                _write_state(directory, {'status': 'disconnected'})
                try:
                    step = adapter.begin(apple_id, password)
                except (ProviderError, OSError):
                    _write_state(directory, {'status': 'error'})
                    raise ProviderError('iCloud-Anmeldung fehlgeschlagen. Zugangsdaten, 2FA und erlaubten Webzugriff prüfen.') from None
                from backend import oauth
                oauth.save(case_id, account_id, {'account_identifier': apple_id})
                state = _step_state(adapter, step, user_id)
                _write_state(directory, state)
                return _public_step(state)
            if action == 'answer':
                if (state.get('status') != 'challenge' or state.get('expires', 0) < time.time()
                        or state.get('user_id') != str(user_id)
                        or not secrets.compare_digest(state.get('challenge_id', ''), challenge_id or '')):
                    raise ProviderError('Anmeldung abgelaufen oder nicht dieser Sitzung zugeordnet. Bitte neu anmelden.')
                adapter.resume_challenge(state['state'], state['field'], state['choices'])
                try:
                    step = adapter.answer(answer)
                except ProviderError:
                    _write_state(directory, {'status': 'error'})
                    raise ProviderError('iCloud-Bestätigung fehlgeschlagen. Bitte neu anmelden.') from None
                state = _step_state(adapter, step, user_id)
                _write_state(directory, state)
                return _public_step(state)
            if action == 'browse':
                if state.get('status') != 'connected' or state.get('expires', 0) < time.time():
                    raise ProviderError('Bitte dieses iCloud-Konto zuerst anmelden.')
                try:
                    entries = adapter.browse(service, path)
                except ProviderError:
                    _write_state(directory, {'status': 'error'})
                    # No certainty whether expiry, ADP approval or provider outage.
                    raise ProviderError('Dieser iCloud-Bereich ist derzeit nicht zugänglich. Webzugriff/ADP-Freigabe prüfen oder erneut anmelden.') from None
                return {'service': service, 'path': path, 'entries': entries, 'downloads_available': False}
            if action == 'forget':
                adapter.forget()
                from backend import oauth
                encrypted, _ = oauth.vault(case_id, account_id)
                encrypted.unlink(missing_ok=True)
                _write_state(directory, {'status': 'disconnected'})
                return {'status': 'disconnected'}
            raise ValueError('Unsupported action')
    finally:
        _GATE.release()
