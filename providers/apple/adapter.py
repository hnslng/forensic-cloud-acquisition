"""Pinned isolated Rclone session, also used by the acquisition queue.

Uses pinned upstream rclone, authenticated private Unix IPC, an encrypted config
per case/account. This base class exposes local configuration and one-level
reads; the acquisition subclass traverses only the case-authorized job scope.
No provider mutation API is exposed. Real Apple acceptance requires approval.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import fcntl
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import subprocess
import tempfile
import time
from uuid import UUID

RCLONE_VERSION = 'v1.75.2'
RCLONE_IMAGE = 'rclone/rclone@sha256:2687085f718d3c628f7fdfb77c52a1d344332aed543110bb88088f2c70d43eb5'


class ProviderError(RuntimeError):
    """Safe to display: never contains upstream bodies, account identifiers or secrets."""


@dataclass(frozen=True)
class Scope:
    case_id: UUID
    account_id: UUID
    service: str
    path: str
    approved_by: str

    def __post_init__(self):
        if not isinstance(self.case_id, UUID) or not isinstance(self.account_id, UUID):
            raise ValueError('Case and account UUIDs required')
        parts = self.path.split('/')
        if (self.service not in ('drive', 'photos') or not self.approved_by.strip()
                or not self.path or len(self.path) > 1024
                or any(p in ('', '.', '..') for p in parts)
                or any(ord(c) < 32 or ord(c) == 127 or c in ':\\' for c in self.path)
                or (self.service == 'photos' and len(parts) < 2)):
            raise ValueError('Explicit relative test folder/album scope required; no account-wide scan')


@dataclass(frozen=True)
class AccountContext:
    """Web connection context. Listing requires a separate explicit browse action."""
    case_id: UUID
    account_id: UUID
    service: str = 'drive'

    def __post_init__(self):
        if not isinstance(self.case_id, UUID) or not isinstance(self.account_id, UUID):
            raise ValueError('Case/account UUIDs required')


@dataclass(frozen=True)
class AuthStep:
    status: str
    field: str = ''
    choices: tuple[str, ...] = ()


class _UnixHTTP(http.client.HTTPConnection):
    def __init__(self, path, timeout):
        super().__init__('localhost', timeout=timeout)
        self.socket_path = str(path)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


class ICloudSession:
    """One serialized session; caller supplies an external per-account encryption key.

    Case authorization and persistent audit are enforced by FCA's API and queue.
    Standalone development callers must supply their explicitly approved scope.
    """
    _ENDPOINTS = frozenset(('core/version', 'config/providers', 'config/unlock',
                            'config/listremotes', 'config/create', 'config/update',
                            'config/delete', 'operations/list'))

    def __init__(self, config_path: Path, config_password: str, scope: Scope,
                 binary='/usr/local/bin/rclone', timeout=45):
        if len(config_password) < 32:
            raise ValueError('A separate strong config encryption key is required')
        self.config_path = Path(config_path).absolute()
        self.scope = scope
        self.binary = binary
        self.timeout = timeout
        self.remote = 'fca_' + scope.case_id.hex + '_' + scope.account_id.hex
        self._password = config_password
        self._state = ''
        self._step = None
        self._process = None
        self._runtime = None
        self._lock = None
        self._authorization = None
        self._validated_scope = False

    def __enter__(self):
        try:
            parent = self.config_path.parent
            if parent.resolve() != parent or not parent.is_dir():
                raise ProviderError('Private canonical configuration directory required.')
            info = parent.stat()
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise ProviderError('Configuration directory must be owned by this user and mode 0700.')
            self._lock = open(parent / '.session.lock', 'a+b')
            os.chmod(parent / '.session.lock', 0o600)
            try:
                fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ProviderError('Another session is using this account.') from None
            if self.config_path.exists() or self.config_path.is_symlink():
                info = self.config_path.lstat()
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                        or stat.S_IMODE(info.st_mode) & 0o077):
                    raise ProviderError('Configuration must be a private regular file.')
                self._check_encrypted(allow_empty=True)
            else:
                descriptor = os.open(self.config_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(descriptor)
            self._runtime = tempfile.TemporaryDirectory(prefix='fca-icloud-')
            runtime = Path(self._runtime.name)
            self._socket = runtime / 'rc.sock'
            rc_password = secrets.token_urlsafe(32)
            self._authorization = 'Basic ' + base64.b64encode(('fca:' + rc_password).encode()).decode()
            # No inherited provider/env credentials, no TCP listener, no logs.
            environment = {'PATH': os.defpath, 'HOME': str(runtime), 'TMPDIR': str(runtime),
                           'RCLONE_RC_USER': 'fca', 'RCLONE_RC_PASS': rc_password}
            self._process = subprocess.Popen(
                [self.binary, 'rcd', '--rc-addr', 'unix://' + str(self._socket),
                 '--config', str(self.config_path), '--cache-dir', str(runtime / 'cache'),
                 '--ask-password=false', '--log-level', 'EMERGENCY',
                 '--buffer-size', '256k', '--multi-thread-streams', '0',
                 '--max-stats-groups', '32'],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=environment, start_new_session=True, umask=0o077)
            for _ in range(100):
                if self._socket.exists():
                    break
                if self._process.poll() is not None:
                    raise ProviderError('The isolated iCloud adapter could not start.')
                time.sleep(.05)
            else:
                raise ProviderError('The isolated iCloud adapter did not become ready.')
            if self._rpc('core/version', {}).get('version') != RCLONE_VERSION:
                raise ProviderError('Unsupported rclone version; reviewed pinned release required.')
            # Set the encryption key before ANY credential is submitted or saved.
            self._rpc('config/unlock', {'configPassword': self._password})
            remotes = self._rpc('config/listremotes', {}).get('remotes', [])
            if remotes not in ([], [self.remote]):
                raise ProviderError('Configuration belongs to another account context.')
            return self
        except BaseException:
            self.close()
            raise

    def _rpc(self, endpoint, payload):
        if endpoint not in self._ENDPOINTS:
            raise ProviderError('Operation is not permitted by this adapter.')
        connection = _UnixHTTP(self._socket, self.timeout)
        try:
            connection.request('POST', '/' + endpoint, json.dumps(payload),
                               {'Content-Type': 'application/json', 'Authorization': self._authorization})
            response = connection.getresponse()
            body = response.read(16 * 1024 * 1024 + 1)
            if len(body) > 16 * 1024 * 1024:
                raise ProviderError('Anbieterantwort überschreitet die Sicherheitsgrenze.')
            result = json.loads(body)
            if response.status != 200:
                self._request_failed(result)
            # job/status uses an error field as data for a finished failed job;
            # the acquisition adapter must classify it, not lose its retry kind.
            if not isinstance(result, dict) or (result.get('error') and endpoint!='job/status'):
                raise ProviderError('iCloud adapter returned an unsuccessful response.')
            return result
        except (OSError, http.client.HTTPException, ValueError) as error:
            self._communication_failed(error)
        finally:
            connection.close()

    def _request_failed(self, result):
        raise ProviderError('Anbieterabfrage fehlgeschlagen. Verbindung und Anmeldung prüfen.')

    def _communication_failed(self,error):
        raise ProviderError('Anbieterkommunikation fehlgeschlagen.') from None

    def _check_encrypted(self, allow_empty=False):
        data = self.config_path.read_bytes()
        if allow_empty and not data:
            return
        header = next((line.strip() for line in data.splitlines() if line.strip() and not line.startswith(b'#')), b'')
        if header != b'RCLONE_ENCRYPT_V0:':
            raise ProviderError('Refusing an unencrypted provider configuration.')

    def capabilities(self):
        providers = self._rpc('config/providers', {}).get('providers', [])
        provider = next((p for p in providers if p.get('Name') == 'iclouddrive'), None)
        if not provider:
            raise ProviderError('Pinned runtime lacks the iCloud provider.')
        options = {p['Name']: p for p in provider['Options']}
        services = {p['Value'] for p in options.get('service', {}).get('Examples', [])}
        return {'provider': 'apple', 'runtime_version': RCLONE_VERSION,
                'drive': 'drive' in services, 'photos': 'photos' in services,
                'authentication': 'apple_password_and_2fa',
                'real_account_validated': self._validated_scope, 'acquisition_available': False}

    def _next_step(self, response):
        self._state, self._step = '', None
        if response.get('Error'):
            raise ProviderError('iCloud authentication did not succeed. Retry or reauthenticate.')
        self._state = response.get('State', '')
        if not self._state:
            self._step = AuthStep('authenticated')
        else:
            if not re.fullmatch(r'2fa_do|2fa_sms_select|2fa_sms_[0-9]+_(sms|voice)', self._state):
                self._state = ''
                raise ProviderError('Unreviewed iCloud authentication state; adapter update required.')
            option = response.get('Option') or {}
            field = option.get('Name', '')
            if field not in ('config_2fa', 'config_2fa_sms', 'config_2fa_phone'):
                raise ProviderError('Unreviewed iCloud authentication step; adapter update required.')
            choices = tuple(str(item['Value']) for item in option.get('Examples', []))
            if any(not re.fullmatch(r'[A-Za-z0-9_+-]{1,64}', c) for c in choices):
                raise ProviderError('Unreviewed iCloud authentication choice.')
            self._step = AuthStep('challenge', field, choices)
        self._check_encrypted()
        return self._step

    def begin(self, apple_id: str, password: str):
        self._validated_scope = False
        self._step, self._state = None, ''
        if not apple_id or not password or any(c in apple_id + password for c in '\r\n'):
            raise ValueError('Apple ID and password required; newline input is unsupported')
        if len(apple_id) > 320 or len(password) > 1024:
            raise ValueError('Credentials exceed input limits')
        # Upstream handles SRP/2FA. Always force obscuring INSIDE encrypted config.
        result = self._rpc('config/create', {'name': self.remote, 'type': 'iclouddrive',
                           'parameters': {'service': self.scope.service, 'apple_id': apple_id, 'password': password},
                           'opt': {'nonInteractive': True, 'obscure': True}})
        return self._next_step(result)

    def answer(self, answer: str):
        if self._step is None or self._step.status != 'challenge' or not self._state:
            raise ProviderError('No active authentication challenge.')
        if self._step.choices:
            valid = answer in self._step.choices
        else:
            valid = bool(re.fullmatch(r'\d{6}', answer)) or (self._step.field == 'config_2fa' and answer.lower() == 'sms')
        if not valid:
            raise ValueError('Enter the current six-digit code or an offered choice')
        result = self._rpc('config/update', {'name': self.remote, 'parameters': {},
                           'opt': {'nonInteractive': True, 'continue': True, 'state': self._state, 'result': answer}})
        return self._next_step(result)

    def resume_challenge(self, state, field, choices=()):
        if not re.fullmatch(r'2fa_do|2fa_sms_select|2fa_sms_[0-9]+_(sms|voice)', state):
            raise ProviderError('Invalid saved authentication challenge.')
        if field not in ('config_2fa', 'config_2fa_sms', 'config_2fa_phone'):
            raise ProviderError('Invalid saved authentication field.')
        self._state = state
        self._step = AuthStep('challenge', field, tuple(choices))

    def browse(self, service, path):
        """Explicit user-requested, one-level read. No recursive scan or downloads."""
        if service not in ('drive', 'photos') or len(path) > 1024:
            raise ValueError('Invalid iCloud area')
        if path and (any(p in ('', '.', '..') for p in path.split('/'))
                     or any(ord(c) < 32 or c in ':\\' for c in path)):
            raise ValueError('Invalid folder path')
        if self._rpc('config/listremotes', {}).get('remotes') != [self.remote]:
            raise ProviderError('Authenticate this account first.')
        # Fixed service-only override, never a caller-supplied rclone backend.
        result = self._rpc('operations/list', {'fs': self.remote + ',service=' + service + ':',
                            'remote': path, 'opt': {'recurse': False, 'metadata': False}})
        rows = result.get('list')
        if not isinstance(rows, list):
            raise ProviderError('iCloud listing failed.')
        safe = []
        for row in rows:
            name = row.get('Name')
            if not isinstance(name, str) or name in ('', '.', '..') or any(ord(c)<32 or c in '/\\:' for c in name):
                continue
            safe.append({'name': name, 'path': (path + '/' if path else '') + name,
                         'is_dir': bool(row.get('IsDir')), 'size': row.get('Size')})
        return safe

    def list_approved_directory(self):
        """One-level read inside the explicit test scope. Never account root or recursive."""
        if self._step is None or self._step.status != 'authenticated':
            raise ProviderError('Complete authentication before checking the approved directory.')
        self._validated_scope = False
        result = self._rpc('operations/list', {'fs': self.remote + ':', 'remote': self.scope.path,
                           'opt': {'recurse': False, 'metadata': True}})
        rows = result.get('list')
        if not isinstance(rows, list):
            raise ProviderError('iCloud listing did not return a valid result.')
        self._validated_scope = True
        return rows

    def forget(self):
        """Delete only this LOCAL encrypted credential record, never provider files."""
        self._rpc('config/delete', {'name': self.remote})
        self._check_encrypted()
        self._state, self._step = '', None
        self._validated_scope = False

    def close(self):
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        self._process = None
        if self._runtime is not None:
            self._runtime.cleanup()
            self._runtime = None
        if self._lock is not None:
            self._lock.close()
            self._lock = None
        self._authorization = self._password = self._state = self._step = None

    def __exit__(self, *args):
        self.close()
