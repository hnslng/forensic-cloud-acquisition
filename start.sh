#!/bin/sh
# FCA starter v1: verify this file against the independently supplied SHA-256
# BEFORE running it. The signed FCA release and offline installer are unchanged.
set -eu
umask 077
[ "$(id -u)" = 0 ] || { echo 'Bitte als root auf der neuen Debian-VM starten.' >&2; exit 1; }
. /etc/os-release
[ "$ID:$VERSION_ID" = debian:13 ] && [ "$(dpkg --print-architecture)" = amd64 ] || {
    echo 'Unterstützt wird Debian 13 amd64.' >&2; exit 1;
}
if ! python3 -c 'import ssl, urllib.request' >/dev/null 2>&1 || ! command -v openssl >/dev/null || [ ! -s /etc/ssl/certs/ca-certificates.crt ]; then
    apt-get update
    apt-get install -y --no-remove --no-install-recommends python3=3.13.5-1 openssl=3.5.7-1~deb13u3 ca-certificates=20250419
fi
# stdin remains attached to the console for the interactive installation.
# The heredoc provides Python code only, never credentials or installer answers.
FCA_BOOTSTRAP_WORK=$(mktemp -d /var/tmp/fca-start.XXXXXXXX)
trap 'rm -rf -- "$FCA_BOOTSTRAP_WORK"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
python3 - "$FCA_BOOTSTRAP_WORK" <<'PY'
import hashlib
from pathlib import Path
import ssl
import sys
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, build_opener

URL = 'https://github.com/hnslng/forensic-cloud-acquisition/releases/download/v0.6.0-rc.1/fca-bootstrap.py'
EXPECTED = '7f08c70fb33dba6d72c7f0744fc9cf9cf5979b540fd4b82735a94c3ff18414a3'

class HTTPSOnly(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, url):
        target = urlparse(url)
        if target.scheme != 'https' or target.hostname not in ('github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com') or target.username or target.password or target.port not in (None, 443):
            raise SystemExit('Nicht zugelassenes Bootstrap-Downloadziel.')
        return super().redirect_request(request, fp, code, message, headers, url)

client = build_opener(HTTPSOnly(), HTTPSHandler(context=ssl.create_default_context()))
try:
    with client.open(URL, timeout=60) as response:
        data = response.read(1024 * 1024 + 1)
except Exception:
    raise SystemExit('Fester FCA-Bootstrap ist nicht anonym erreichbar. Internetzugang und öffentliches GitHub-Release prüfen; keine Tokens eingeben.') from None
if len(data) > 1024 * 1024 or hashlib.sha256(data).hexdigest() != EXPECTED:
    raise SystemExit('Bootstrap-Prüfsumme ungültig. Installation angehalten.')
(Path(sys.argv[1]) / 'bootstrap.py').write_bytes(data)
print('FCA-Bootstrap geprüft. Starte die geführte Installation …', flush=True)
PY
# A separate invocation inherits the original terminal; do not consume it in Python.
python3 "$FCA_BOOTSTRAP_WORK/bootstrap.py"
