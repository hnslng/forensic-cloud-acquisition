#!/usr/bin/env python3
"""FCA bootstrap: generated for ONE verified release, no tokens or latest URLs."""
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import ssl
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, build_opener

RELEASE = {'version': '0.6.0-rc.1', 'public_key': '-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEA2TNc8y9dxNbN2NS1Xt8bCCD3byr/JplEUQmU5hAm+2g=\n-----END PUBLIC KEY-----\n', 'archive_sha256': '3d8ff447e6d6cf3e9986fdc625e176802b4ab2dafa16650b834ed8f33df49164', 'archive_bytes': 332478822, 'unpacked_bytes': 728628770}


class Refused(RuntimeError):
    pass


class HTTPSOnly(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, url):
        checked_url(url)
        return super().redirect_request(request, fp, code, message, headers, url)


def checked_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com') or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise Refused('Nicht zugelassenes Downloadziel.')
    return url


def download(url, destination, maximum):
    checked_url(url)
    client = build_opener(HTTPSOnly(), HTTPSHandler(context=ssl.create_default_context()))
    for attempt in range(3):
        try:
            with client.open(url, timeout=60) as response, destination.open('wb') as output:
                count = 0
                while chunk := response.read(1024*1024):
                    count += len(chunk)
                    if count > maximum:
                        raise Refused('Download überschreitet die freigegebene Größe.')
                    output.write(chunk)
                return
        except HTTPError as error:
            destination.unlink(missing_ok=True)
            if error.code in (401, 403, 404):
                raise Refused('Das festgelegte GitHub-Release ist anonym nicht verfügbar. Repository und Release müssen öffentlich und die Release-Dateien veröffentlicht sein. Keine Anmeldung oder Tokens verwenden.') from None
            if error.code != 429 and error.code < 500:
                raise Refused('GitHub-Download fehlgeschlagen.') from None
            if attempt == 2:
                raise Refused('GitHub-Download nach drei Versuchen fehlgeschlagen.') from None
        except (URLError, TimeoutError, ConnectionError, http.client.HTTPException):
            destination.unlink(missing_ok=True)
            if attempt == 2:
                raise Refused('Download unterbrochen. Erneut starten; bestehende FCA-Daten werden erhalten.') from None
        time.sleep(2**attempt)


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        while chunk := source.read(1024*1024):
            value.update(chunk)
    return value.hexdigest()


def signature(key, content, signature_file):
    result = subprocess.run(['openssl', 'pkeyutl', '-verify', '-pubin', '-inkey', str(key), '-rawin', '-in', str(content), '-sigfile', str(signature_file)], capture_output=True)
    if result.returncode:
        raise Refused('Signatur ungültig. Installation abgebrochen.')


def unpack(archive, destination):
    # Validate the entire index BEFORE extraction. No extractall, links or devices.
    prefix = 'fca-' + RELEASE['version']
    with tarfile.open(archive, 'r:gz') as source:
        members = source.getmembers()
        seen = set()
        total = 0
        if len(members) > 50000:
            raise Refused('Zu viele Archivdateien.')
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != prefix or member.name in seen or not (member.isdir() or member.isfile()) or member.mode & 0o7000:
                raise Refused('Unsicherer Archivinhalt.')
            seen.add(member.name)
            total += member.size
            if total > RELEASE['unpacked_bytes']:
                raise Refused('Archivinhalt überschreitet freigegebene Größe.')
        for member in members:
            target = destination.joinpath(*PurePosixPath(member.name).parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True, mode=0o700)
            else:
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with source.extractfile(member) as input_file, target.open('xb') as output:
                    shutil.copyfileobj(input_file, output, 1024*1024)
    return destination/prefix


def fetch_release(work):
    name = 'fca-' + RELEASE['version'] + '.tar.gz'
    base = 'https://github.com/hnslng/forensic-cloud-acquisition/releases/download/v' + RELEASE['version'] + '/'
    key = work/'release.pub'
    key.write_text(RELEASE['public_key'])
    archive = work/name
    checksum = work/(name+'.sha256')
    sig = work/(name+'.sha256.sig')
    print('Lade und prüfe FCA ' + RELEASE['version'] + ' …', flush=True)
    download(base+checksum.name, checksum, 512)
    download(base+sig.name, sig, 128)
    signature(key, checksum, sig)
    expected = RELEASE['archive_sha256'] + '  ' + name + '\n'
    if checksum.read_text() != expected:
        raise Refused('Signiertes Release stimmt nicht mit dieser freigegebenen Version überein.')
    download(base+name, archive, RELEASE['archive_bytes'])
    if archive.stat().st_size != RELEASE['archive_bytes'] or digest(archive) != RELEASE['archive_sha256']:
        raise Refused('Prüfsumme des Releasepakets stimmt nicht.')
    package = unpack(archive, work)
    signature(key, package/'manifest.json', package/'manifest.sig')
    if json.loads((package/'manifest.json').read_text()).get('version') != RELEASE['version']:
        raise Refused('Paketversion stimmt nicht.')
    # Both outer archive AND manifest authenticated before any downloaded code runs.
    return package, key


def main():
    if len(sys.argv) != 1:
        raise Refused('Dieser Bootstrap akzeptiert keine fremden Downloadziele, Schlüssel oder Versionen.')
    if os.geteuid() != 0:
        raise Refused('Bitte als root auf dem neuen FCA-Server starten.')
    os.umask(0o077)
    release = Path('/etc/os-release').read_text()
    values = dict(line.split('=', 1) for line in release.splitlines() if '=' in line)
    if values.get('ID', '').strip('"') != 'debian' or values.get('VERSION_ID', '').strip('"') != '13' or subprocess.check_output(['dpkg', '--print-architecture']).strip() != b'amd64':
        raise Refused('Dieser Bootstrap benötigt Debian 13 amd64.')
    if shutil.which('openssl') is None:
        raise Refused('Das Debian-Paket openssl fehlt.')
    if not sys.stdin.isatty():
        raise Refused('Interaktive Konsole erforderlich. Den angegebenen Installationsbefehl direkt starten.')
    if shutil.disk_usage('/var/tmp').free < RELEASE['archive_bytes'] + RELEASE['unpacked_bytes'] + 5*1024**3:
        raise Refused('Zu wenig freier Systemspeicher für Download, Paket und 5-GiB-Reserve.')
    with tempfile.TemporaryDirectory(prefix='fca-bootstrap-', dir='/var/tmp') as temporary:
        package, key = fetch_release(Path(temporary))
        subprocess.run([sys.executable, str(package/'scripts/fca_guided_install.py'), '--package', str(package), '--trusted-key', str(key)], check=True)


if __name__ == '__main__':
    try:
        main()
    except (Refused, OSError, ValueError, tarfile.TarError, subprocess.CalledProcessError, KeyboardInterrupt) as error:
        print('FCA-Installation angehalten: ' + str(error), file=sys.stderr)
        sys.exit(1)
