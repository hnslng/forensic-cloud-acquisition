#!/usr/bin/env python3
"""HTTPS acceptance on the real guest; only synthetic case data, no credential output."""
import http.cookiejar
import json
import ssl
import subprocess
import time
from pathlib import Path
import urllib.request
import urllib.error

ORIGIN = 'https://10.0.1.189'


def main():
    context = ssl.create_default_context(cafile='/etc/fca/tls/lab-ca.crt')
    cookies = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), urllib.request.HTTPCookieProcessor(cookies))

    def call(method, path, body=None):
        headers = {'Origin': ORIGIN, 'Content-Type': 'application/json'}
        headers.update({'X-CSRF-Token': c.value for c in cookies if c.name == '__Host-fca_csrf'})
        r = urllib.request.Request(ORIGIN + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with opener.open(r, timeout=10) as response:
            return json.load(response)

    user = call('POST', '/api/auth/login', {'username': 'admin', 'password': Path('/etc/fca/secrets/initial_admin_password').read_text().strip()})
    assert user['role'] == 'admin'
    assert all(c.secure for c in cookies)
    number = 'SYNTHETISCH-PHASE1-' + time.strftime('%Y%m%d-%H%M%S')
    case = call('POST', '/api/cases', {'business_number': number, 'name': 'Phase-1-Abnahme (synthetisch)', 'operator_initials': 'TEST'})
    call('PATCH', '/api/cases/' + case['id'], {'name': case['name'], 'operator_initials': 'TEST', 'status': 'archived', 'version': case['version']})
    assert len(call('GET', '/api/cases/' + case['id'] + '/audit')) >= 2
    assert call('GET', '/api/status')['evidence_mounted'] is True
    subprocess.run(['docker', 'compose', '--env-file', '/etc/fca/compose.env', '--profile', 'application', 'restart', 'api'], cwd='/opt/fca', check=True, stdout=subprocess.DEVNULL)
    for _ in range(30):
        try:
            assert call('GET', '/api/auth/me')['id'] == user['id']
            break
        except (urllib.error.URLError, ConnectionError):
            time.sleep(1)
    else:
        raise SystemExit('API did not return after restart')
    assert call('GET', '/api/cases/' + case['id'])['status'] == 'archived'
    call('POST', '/api/auth/logout', {})
    try:
        call('GET', '/api/auth/me')
    except urllib.error.HTTPError as e:
        assert e.code == 401
    else:
        raise AssertionError('Logout did not revoke session')
    print(json.dumps({'https_chain_and_ip_verified': True, 'secure_session': True, 'case_and_audit': True,
                      'session_and_case_survive_api_restart': True, 'logout_revoked': True, 'synthetic_case_id': case['id']}))


if __name__ == '__main__':
    main()
