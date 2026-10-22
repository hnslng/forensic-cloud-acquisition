"""Validate all package bytes against an independently trusted signing key."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

class Refused(RuntimeError):
    pass


def sha256(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def canonical(path):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise Refused('Symbolische Links im Pfad sind nicht zulässig.')
    return path


def safe_relative(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_./+~:%-]+', value):
        raise Refused('Ungültiger Paketpfad.')
    path = Path(value)
    if path.is_absolute() or any(p in ('..', '.') for p in value.split('/')):
        raise Refused('Unsicherer Paketpfad.')
    return path


def verify(directory, trusted_key):
    directory = canonical(directory)
    key = canonical(trusted_key)
    # Trust anchor must be delivered independently; never trust a bundled key.
    if key == directory or directory in key.parents:
        raise Refused('Vertrauensschlüssel muss außerhalb des Pakets liegen.')
    for path in (key, directory / 'manifest.json', directory / 'manifest.sig'):
        if path.is_symlink() or not path.is_file():
            raise Refused('Signatur, Manifest oder Vertrauensschlüssel fehlt.')
    result = subprocess.run(['openssl', 'pkeyutl', '-verify', '-pubin', '-inkey', str(key),
                             '-rawin', '-in', str(directory / 'manifest.json'),
                             '-sigfile', str(directory / 'manifest.sig')], capture_output=True)
    if result.returncode:
        raise Refused('Release-Signatur ist ungültig.')
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest.get('format') != 1 or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.-]+)?', manifest.get('version', '')):
        raise Refused('Nicht unterstütztes Releaseformat.')
    if manifest.get('architecture') != 'amd64':
        raise Refused('Dieses Paket unterstützt nur amd64.')
    if manifest.get('schema') != 9:
        raise Refused('Für diese Schemaversion ist ein geprüftes Installationswerkzeug erforderlich.')
    for field in ('app_image', 'database_image'):
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', manifest.get(field, '')):
            raise Refused('Image muss über seine unveränderliche Inhalts-ID referenziert sein.')
    files = manifest.get('files', {})
    required = {'images.tar', 'compose.template.json', 'scripts/configure_phase1_database.py',
                'frontend/index.html', 'frontend/app.js', 'frontend/styles.css', 'migrations/0001_bootstrap.sql'}
    if not required.issubset(files):
        raise Refused('Release enthält nicht alle benötigten Dateien.')
    actual = set()
    for path in directory.rglob('*'):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise Refused('Links und Spezialdateien sind im Release nicht erlaubt.')
        if path.is_file() and path.relative_to(directory).as_posix() not in ('manifest.json', 'manifest.sig'):
            actual.add(path.relative_to(directory).as_posix())
    if actual != set(files):
        raise Refused('Zusätzliche oder fehlende Dateien im Release.')
    for name, record in files.items():
        path = directory / safe_relative(name)
        if path.stat().st_size != record['size'] or sha256(path) != record['sha256']:
            raise Refused('Integritätsprüfung fehlgeschlagen: ' + name)
    for deb in manifest.get('dependencies', []):
        if not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*', deb['name']) or not deb['version']:
            raise Refused('Ungültige Abhängigkeitsbeschreibung.')
        if deb['file'] not in files or not deb['file'].startswith('debs/') or not deb['file'].endswith('.deb'):
            raise Refused('Nicht gesperrte Betriebssystemabhängigkeit.')
    return manifest


def write_manifest(directory, version, app_image, database_image, dependencies, source):
    directory = Path(directory)
    files = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise Refused('Kein Link im Release erlaubt.')
        if path.is_file() and path.relative_to(directory).as_posix() not in ('manifest.json', 'manifest.sig'):
            files[path.relative_to(directory).as_posix()] = {'size': path.stat().st_size, 'sha256': sha256(path)}
    value = dict(format=1, version=version, architecture='amd64', schema=9,
                 source_revision=source, app_image=app_image, database_image=database_image,
                 dependencies=dependencies, files=files)
    (directory / 'manifest.json').write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
    return value
