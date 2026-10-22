#!/usr/bin/env python3
"""Certbot DNS-01 hook: one configured hostname, additive TXT records only."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time
import urllib.error
import urllib.request


class ChallengeError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def private_file(path):
    path = Path(path)
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077 or path.resolve() != path):
        raise ChallengeError('Unsicher geschützte ACME-Konfiguration.')
    return path.read_text().strip()


class IonosChallenge:
    def __init__(self, config):
        self.host = config['host']
        self.zone = config['zone_id']
        if (not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*\.[a-z]{2,63}', self.host)
                or not re.fullmatch(r'[a-f0-9-]{36}', self.zone)):
            raise ChallengeError('Ungültige ACME-Konfiguration.')
        self.key_file = config['key_file']
        self.state = Path(config['state_directory'])
        self.servers = config['nameservers']
        if not self.servers or any(not re.fullmatch(r'[a-zA-Z0-9.-]+', s) for s in self.servers):
            raise ChallengeError('Ungültige autoritative Nameserver.')
        self.opener = urllib.request.build_opener(NoRedirect())

    def api(self, method, suffix='', body=None):
        permitted = ((method == 'GET' and suffix == '')
                     or (method == 'POST' and suffix == '/records')
                     or (method == 'DELETE' and re.fullmatch(r'/records/[a-f0-9-]{36}', suffix)))
        if not permitted:
            raise ChallengeError('DNS-Operation ist nicht freigegeben.')
        key = private_file(self.key_file)
        req = urllib.request.Request(
            'https://api.hosting.ionos.com/dns/v1/zones/' + self.zone + suffix,
            method=method, data=None if body is None else json.dumps(body).encode(),
            headers={'X-API-Key': key, 'Accept': 'application/json', 'Content-Type': 'application/json'})
        try:
            with self.opener.open(req, timeout=30) as response:
                data = response.read(4 * 1024 * 1024 + 1)
                if len(data) > 4 * 1024 * 1024:
                    raise ChallengeError('DNS-Antwort zu groß.')
                return json.loads(data) if data else None
        except urllib.error.HTTPError as error:
            raise ChallengeError('IONOS-DNS-Anfrage fehlgeschlagen (HTTP ' + str(error.code) + ').') from None
        except (OSError, ValueError):
            raise ChallengeError('IONOS-DNS-Anfrage fehlgeschlagen; keine Zugangsdaten ausgegeben.') from None

    def matching(self, token):
        records = self.api('GET').get('records', [])
        return [r for r in records if r.get('name', '').lower().rstrip('.') == '_acme-challenge.' + self.host
                and r.get('type') == 'TXT' and r.get('content', '').strip('"') == token]

    def marker(self, token):
        return self.state / (hashlib.sha256((self.host + ':' + token).encode()).hexdigest() + '.json')

    def auth(self, token):
        marker = self.marker(token)
        if not marker.exists():
            previous = self.matching(token)
            if previous:
                entry = {'owned': False}
            else:
                self.api('POST', '/records', [{'name': '_acme-challenge.' + self.host,
                         'type': 'TXT', 'content': token, 'ttl': 60, 'prio': 0, 'disabled': False}])
                created = self.matching(token)
                if len(created) != 1:
                    raise ChallengeError('Erstellter Challenge-Eintrag nicht eindeutig bestätigt.')
                entry = {'owned': True, 'id': created[0]['id']}
            fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'w') as handle:
                json.dump(entry, handle)
                handle.flush()
                os.fsync(handle.fileno())
        self.wait(token)

    def wait(self, token):
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            ready = True
            for server in self.servers:
                result = subprocess.run(['dig', '@' + server, '_acme-challenge.' + self.host,
                         'TXT', '+short', '+time=2', '+tries=1'], capture_output=True, text=True, timeout=5)
                values = [line.strip().strip('"') for line in result.stdout.splitlines()]
                ready = ready and result.returncode == 0 and token in values
            if ready:
                return
            time.sleep(5)
        raise ChallengeError('Challenge noch nicht auf allen autoritativen Nameservern sichtbar.')

    def cleanup(self, token):
        marker = self.marker(token)
        if not marker.exists():
            return
        entry = json.loads(private_file(marker))
        if entry.get('owned'):
            matches = self.matching(token)
            own = [r for r in matches if r.get('id') == entry.get('id')]
            if own:
                self.api('DELETE', '/records/' + own[0]['id'])
            elif any(r.get('id') == entry.get('id') for r in self.api('GET').get('records', [])):
                raise ChallengeError('Challenge-Eintrag geändert; keine Löschung fremder Daten.')
        marker.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['auth', 'cleanup'])
    parser.add_argument('--config', default='/etc/fca/acme/ionos.json')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ChallengeError('ACME-Hook muss administrativ ausgeführt werden.')
    challenge = IonosChallenge(json.loads(private_file(args.config)))
    token = os.environ.get('CERTBOT_VALIDATION', '')
    if (os.environ.get('CERTBOT_DOMAIN') != challenge.host
            or not re.fullmatch(r'[A-Za-z0-9_-]{20,256}', token)):
        raise ChallengeError('Challenge gehört nicht zum eingerichteten FCA-Namen.')
    challenge.state.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = challenge.state.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077
            or challenge.state.resolve() != challenge.state):
        raise ChallengeError('Unsicherer ACME-Zustandsspeicher.')
    with (challenge.state / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        getattr(challenge, args.action)(token)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error) if isinstance(error, ChallengeError) else 'ACME-Hook fehlgeschlagen; keine Zugangsdaten ausgegeben.')
        raise SystemExit(1) from None
