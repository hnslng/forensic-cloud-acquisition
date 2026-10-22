"""Host lifecycle. All persistent state is outside immutable version directories.

No partitioning, DNS, firewall, WireGuard, host reboot, remote shell or git pull.
"""
import argparse
import datetime
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import ssl
import subprocess
import sys
import tarfile
import uuid
from urllib.request import urlopen

from infrastructure.installer.package import Refused, canonical, sha256, verify
from scripts.prepare_private_https import prepare

CONFIG = Path('/etc/fca/installation.json')
RELEASES = Path('/opt/fca-releases')
CURRENT = Path('/opt/fca-current')
ENV = Path('/etc/fca/compose.env')
COMPOSE = Path('/etc/fca/compose.json')
GIB = 1024**3
PROFILES = {'labor': (2, 2, 4, 2), 'standard': (4, 8, 4, 2), 'behoerde': (8, 16, 4, 2)}


def run(command, *, data=None):
    # Never propagate captured provider/SQL/Compose output or secret-bearing errors.
    result = subprocess.run([str(v) for v in command], input=data, capture_output=True)
    if result.returncode:
        raise Refused('Befehl fehlgeschlagen: ' + ' '.join(str(v) for v in command[:10]) + '. Details geschützt am Server prüfen.')
    return result.stdout


def write(path, text, mode=0o600):
    path = canonical(path)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex)
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def directory(path, mode=0o700):
    path = canonical(path)
    path.mkdir(parents=True, mode=mode, exist_ok=True)
    if not path.is_dir():
        raise Refused('Verzeichnis fehlt.')
    if path.stat().st_uid != 0 or path.stat().st_mode & 0o022:
        raise Refused('Verzeichnis muss root gehören und gegen fremde Schreibzugriffe geschützt sein.')
    return path


def cfg():
    if not CONFIG.is_file():
        raise Refused('Keine verwaltete FCA-Installation gefunden. Bestehende Laborinstallation wird nicht übernommen.')
    return validate_config(json.loads(CONFIG.read_text()))


def validate_config(value):
    value = dict(value)
    if value.get('mode') not in ('labor', 'wireguard') or value.get('profile') not in PROFILES:
        raise Refused('Betriebsart oder Ressourcenprofil ungültig.')
    address = ipaddress.ip_address(value['listen_address'])
    if address.version != 4 or not address.is_private or address.is_loopback or address.is_unspecified or address.is_multicast:
        raise Refused('Eine explizite private Serveradresse ist erforderlich.')
    host = value['server_name'].lower()
    try:
        host_address = ipaddress.ip_address(host)
    except ValueError:
        prepare(host, str(address), value['allowed_networks'])
    else:
        if value['mode'] != 'labor' or host_address != address:
            raise Refused('IP-Zugriff ist nur im Labor mit derselben Serveradresse zulässig.')
    networks = [ipaddress.ip_network(v, strict=True) for v in value['allowed_networks']]
    if not networks or any(not n.is_private or n.prefixlen == 0 or n.is_loopback or n.is_multicast for n in networks):
        raise Refused('Nur explizite private LAN-/WireGuard-Netze freigeben.')
    for field in ('evidence_root', 'certificate', 'certificate_key', 'ca_certificate', 'backup_root'):
        path = canonical(value[field])
        if not re.fullmatch(r'/[A-Za-z0-9_./-]+', str(path)) or '..' in path.parts or str(path) == '/':
            raise Refused('Absolute Pfade ohne Sonderzeichen erforderlich.')
        value[field] = str(path)
    evidence = Path(value['evidence_root'])
    backup = Path(value['backup_root'])
    protected = (Path('/etc'), Path('/opt'), Path('/var/lib'), Path('/usr'), Path('/boot'), Path('/dev'), Path('/proc'), Path('/sys'), Path('/run'))
    if any(evidence == p or p in evidence.parents for p in protected):
        raise Refused('Sicherungsdaten benötigen einen eigenen Pfad außerhalb von Systemverzeichnissen.')
    if evidence == backup or evidence in backup.parents or backup in evidence.parents:
        raise Refused('Backup und Sicherungsdaten dürfen nicht ineinander liegen.')
    value['server_name'] = host
    value['listen_address'] = str(address)
    value['allowed_networks'] = [str(n) for n in networks]
    value.setdefault('state_root', '/var/lib/fca')
    if value['state_root'] != '/var/lib/fca':
        raise Refused('Der Zustandsordner ist in dieser Paketversion fest vorgegeben.')
    return value


def interactive():
    def ask(label, default=None):
        answer = input(label + (f' [{default}]' if default else '') + ': ').strip()
        return answer or default
    mode = ask('Betriebsart: labor oder wireguard', 'labor')
    address = ask('Private Server-IP (vorhandenes LAN/WireGuard)')
    host = ask('HTTPS-Name oder Labor-IP', address if mode == 'labor' else None)
    return validate_config(dict(mode=mode, listen_address=address, server_name=host,
        allowed_networks=ask('Zugelassene private Netze, durch Komma getrennt').split(','),
        evidence_root=ask('Bereits eingebundener, leerer Sicherungsdatenträger', '/srv/fca/evidence'),
        backup_root=ask('Geschützter Backup-Speicher', '/var/backups/fca'),
        profile=ask('Ressourcenprofil: labor, standard oder behoerde', 'labor'),
        certificate=ask('Vorhandene HTTPS-Zertifikatskette', '/etc/fca/tls/fullchain.pem'),
        certificate_key=ask('Vorhandener HTTPS-Schlüssel', '/etc/fca/tls/privkey.pem'),
        ca_certificate=ask('Vertrauenswürdige CA-Kette', '/etc/fca/tls/ca.pem')))


def empty_volume(path):
    # ext4 creates this empty recovery directory during formatting by the admin.
    return all(p.name == 'lost+found' and p.is_dir() and not p.is_symlink() and not any(p.iterdir()) for p in path.iterdir())


def mounted_evidence(config, initialize=False):
    path = canonical(config['evidence_root'])
    if not path.is_dir() or not os.path.ismount(path):
        raise Refused('Sicherungsdatenträger muss vorab an diesem Pfad eingebunden sein; kein Fallback auf die Systemdisk.')
    marker = path / '.fca-volume-id'
    if not marker.exists():
        if not initialize or not empty_volume(path):
            raise Refused('Datenträger ist nicht leer oder besitzt keine FCA-Kennung.')
        write(marker, config.get('volume_id', str(uuid.uuid4())) + '\n', 0o644)
    if marker.is_symlink() or not marker.is_file():
        raise Refused('Ungültige Datenträgerkennung.')
    if config.get('volume_id') and marker.read_text().strip() != config['volume_id']:
        raise Refused('Falscher Sicherungsdatenträger eingebunden.')
    return marker.read_text().strip()


def preflight(config):
    os_release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if os_release.get('ID', '').strip('"') != 'debian' or os_release.get('VERSION_ID', '').strip('"') != '13':
        raise Refused('Unterstützt wird Debian 13.')
    if run(['dpkg', '--print-architecture']).decode().strip() != 'amd64':
        raise Refused('Zunächst nur Debian 13 amd64 freigegeben.')
    memory = int(re.search(r'MemTotal:\s+(\d+)', Path('/proc/meminfo').read_text())[1]) * 1024
    cpu, ram, _, _ = PROFILES[config['profile']]
    if (os.cpu_count() or 0) < cpu or memory < ram * GIB * .9:
        raise Refused('Das gewählte Ressourcenprofil passt nicht zu CPU/RAM.')
    if shutil.disk_usage('/var').free < 5 * GIB:
        raise Refused('Mindestens 5 GiB freier Systemspeicher sind erforderlich.')
    if shutil.disk_usage(config['evidence_root']).free < 3 * GIB:
        raise Refused('Mindestens 3 GiB freier Sicherungsspeicher sind erforderlich.')
    interfaces = json.loads(run(['ip', '-j', 'address']))
    if not any(a['local'] == config['listen_address'] for i in interfaces for a in i.get('addr_info', [])):
        raise Refused('Die angegebene private IP ist auf diesem Server nicht vorhanden.')
    for field in ('certificate', 'certificate_key', 'ca_certificate'):
        if not canonical(config[field]).is_file():
            raise Refused('Vorhandene, administrativ freigegebene TLS-Dateien erforderlich.')
    key = Path(config['certificate_key']).stat()
    if key.st_uid != 0 or key.st_mode & 0o077:
        raise Refused('HTTPS-Schlüssel muss root gehören und nur für root lesbar sein (0600).')
    context = ssl.create_default_context(cafile=config['ca_certificate'])
    # Checks certificate/key consistency and trusted chain before changing services.
    context.load_cert_chain(config['certificate'], config['certificate_key'])
    field = '-verify_ip' if _is_ip(config['server_name']) else '-verify_hostname'
    run(['openssl', 'verify', '-CAfile', config['ca_certificate'], '-untrusted', config['certificate'], field, config['server_name'], config['certificate']])
    run(['openssl', 'x509', '-checkend', '604800', '-noout', '-in', config['certificate']])


def _is_ip(value):
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def install_dependencies(package, manifest):
    # All direct AND resolved transitive .debs are contained in the signed package.
    # Never apt update, add a repository, download a script or choose a candidate here.
    missing = []
    for item in manifest['dependencies']:
        result = subprocess.run(['dpkg-query', '-W', '-f=${Version}', item['name']], capture_output=True)
        if result.returncode == 0:
            installed = result.stdout.decode()
            if installed != item['version']:
                newer = subprocess.run(['dpkg', '--compare-versions', installed, 'gt', item['version']]).returncode == 0
                if newer:
                    raise Refused('Neuere installierte Abhängigkeit: ' + item['name'] + '. Kein automatisches Downgrade.')
                missing.append(str(package / item['file']))
        else:
            missing.append(str(package / item['file']))
    if missing:
        policy = Path('/usr/sbin/policy-rc.d')
        owned_policy = not policy.exists()
        if owned_policy:
            write(policy, '#!/bin/sh\nexit 101\n', 0o755)
        try:
            run(['apt-get', '-y', '--no-download', '--no-install-recommends', 'install', *missing])
        finally:
            if owned_policy:
                policy.unlink()
        # Only the package-created default on a previously empty web server.
        default = Path('/etc/nginx/sites-enabled/default')
        if default.is_symlink() and str(default.readlink()) == '/etc/nginx/sites-available/default':
            default.unlink()
    run(['systemctl', 'start', 'docker', 'nginx'])
    for command in (['docker', 'version'], ['docker', 'compose', 'version'], ['nginx', '-v']):
        run(command)


def compose(*args, data=None):
    return run(['docker', 'compose', '--env-file', ENV, '-f', COMPOSE, '--profile', 'application', *args], data=data)


def sql(statement, database='fca'):
    return compose('exec', '-T', 'database', 'psql', '-v', 'ON_ERROR_STOP=1', '-At', '-U', 'fca_bootstrap', '-d', database, data=statement.encode()).decode().strip()


def secret(name, config):
    path = Path('/etc/fca/secrets') / name
    if not path.exists():
        write(path, secrets.token_urlsafe(48) + '\n', 0o640)
        os.chown(path, 0, 10001)
    if path.is_symlink() or path.stat().st_mode & 0o007:
        raise Refused('Unsichere Secret-Datei.')


def render_compose(config, manifest, release):
    value = json.loads((release / 'compose.template.json').read_text())
    value['name'] = 'fca'
    for network in value.get('networks', {}).values():
        network.pop('name', None)
    for name, service in value['services'].items():
        service.pop('build', None)
        service['image'] = manifest['database_image'] if name == 'database' else manifest['app_image']
        service['restart'] = 'on-failure:3'
        if name == 'database':
            service['volumes'] = [config['state_root'] + '/postgres:/var/lib/postgresql/data']
        else:
            service['volumes'] = [config['evidence_root'] + ':/evidence', config['state_root'] + '/cloud-auth:/cloud-auth']
            service['environment']['FCA_MAX_FILE_PARALLELISM'] = '4'
            service['environment']['FCA_MAX_ACCOUNT_PARALLELISM'] = '2'
            if name == 'api':
                service['environment']['FCA_PUBLIC_ORIGIN'] = 'https://' + config['server_name']
    for name in value['secrets']:
        value['secrets'][name] = {'file': '/etc/fca/secrets/' + name}
    return value


def nginx(config):
    host = config['server_name']
    # Reuse the reviewed HTTPS renderer. Only laboratory mode permits an IP SAN.
    render_host = 'fca.internal.example' if _is_ip(host) else host
    _, text = prepare(render_host, config['listen_address'], config['allowed_networks'], config['certificate'], config['certificate_key'])
    return text.replace('server_name ' + render_host + ';', 'server_name ' + host + ';').replace('/var/www/fca;', '/opt/fca-current/frontend;')


def switch(release):
    temp = CURRENT.with_name(CURRENT.name + '-' + uuid.uuid4().hex)
    temp.symlink_to(release)
    os.replace(temp, CURRENT)


def materialize(package, manifest):
    directory(RELEASES, 0o755)
    release = RELEASES / manifest['version']
    if release.exists():
        if (release / 'manifest.json').read_bytes() != (package / 'manifest.json').read_bytes():
            raise Refused('Versionsnummer ist bereits mit anderem Inhalt belegt.')
        # Verify installed bytes too, including payloads; never reuse a changed release.
        return release
    temp = RELEASES / ('.staging-' + uuid.uuid4().hex)
    shutil.copytree(package, temp)
    for path in temp.rglob('*'):
        path.chmod(0o755 if path.is_dir() or path.name in ('install.sh', 'update.sh') else 0o644)
    temp.chmod(0o755)
    # Caller re-verifies after copy before executing code/loading images.
    temp.rename(release)
    return release


def load_images(release, manifest):
    run(['docker', 'load', '-i', release / 'images.tar'])
    for name in ('app_image', 'database_image'):
        actual = run(['docker', 'image', 'inspect', '--format', '{{.Id}}', manifest[name]]).decode().strip()
        if actual != manifest[name]:
            raise Refused('Geladenes Image stimmt nicht mit dem signierten Manifest überein.')


def migrations(release):
    exists = sql("SELECT to_regclass('public.schema_migrations') IS NOT NULL;") == 't'
    if not exists:
        # A nonempty unknown DB must never be bootstrapped as a fresh FCA instance.
        if sql("SELECT count(*) FROM pg_tables WHERE schemaname='public';") != '0':
            raise Refused('Vorhandene unbekannte Datenbank; keine Initialisierung.')
        sql((release / 'migrations/0001_bootstrap.sql').read_text())
    env = dict(os.environ, FCA_PROJECT_ROOT=str(release), FCA_SECRET_ROOT='/etc/fca/secrets',
               FCA_COMPOSE_ENV=str(ENV), FCA_COMPOSE_FILE=str(COMPOSE))
    result = subprocess.run([sys.executable, str(release / 'scripts/configure_phase1_database.py')], env=env, capture_output=True)
    if result.returncode or sql('SELECT max(version) FROM schema_migrations;') != '9':
        raise Refused('Datenbankmigration fehlgeschlagen. Dienste bleiben angehalten; geprüftes Backup verwenden.')
    if sql("SELECT count(*) FROM users WHERE role='admin';") == '0':
        # Secret bind exists only for this short-lived bootstrap container.
        compose('run', '--rm', '--no-deps', '-v', '/etc/fca/secrets/initial_admin_password:/run/secrets/initial_admin_password:ro',
                'api', 'python', '-m', 'backend.manage')


def configure_files(config, manifest, release):
    write(COMPOSE, json.dumps(render_compose(config, manifest, release), indent=2) + '\n')
    write(ENV, '# Keine Zugangsdaten. Secrets liegen ausschließlich in separaten Dateien.\n')
    unit = f'''[Unit]
Description=Forensic Cloud Acquisition
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target
RequiresMountsFor={config['evidence_root']} {config['state_root']}

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStartPre=/usr/bin/python3 /opt/fca-current/scripts/fca_admin.py guard
ExecStart=/usr/bin/docker compose --env-file /etc/fca/compose.env -f /etc/fca/compose.json --profile application up -d --no-build --pull never --wait --wait-timeout 180
ExecStop=/usr/bin/docker compose --env-file /etc/fca/compose.env -f /etc/fca/compose.json --profile application stop
TimeoutStartSec=240
TimeoutStopSec=180
UMask=0077

[Install]
WantedBy=multi-user.target
'''
    write(Path('/etc/systemd/system/fca.service'), unit, 0o644)
    site = Path('/etc/nginx/conf.d/fca-managed.conf')
    if site.exists() and not CONFIG.exists():
        raise Refused('Bestehende nginx-Konfiguration wird nicht übernommen.')
    write(site, nginx(config), 0o644)
    run(['nginx', '-t'])
    run(['systemctl', 'daemon-reload'])
    run(['systemctl', 'enable', 'docker', 'nginx', 'fca'])


def start():
    compose('up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '180')
    run(['systemctl', 'reload', 'nginx'])
    # Mark systemd's oneshot unit active so boot/shutdown owns the same stack.
    run(['systemctl', 'start', 'fca'])


def install(args):
    package = canonical(args.package)
    manifest = verify(package, args.trusted_key)
    resuming = CONFIG.exists()
    if resuming:
        config = cfg()
        if args.config and validate_config(json.loads(Path(args.config).read_text())) != {k: v for k, v in config.items() if k not in ('volume_id', 'installation_status', 'pending_manifest')}:
            raise Refused('Bestehende Konfiguration weicht ab. Installation ändert sie nicht.')
        if config.get('installation_status') == 'ready':
            if not CURRENT.exists() or json.loads((CURRENT / 'manifest.json').read_text())['version'] != manifest['version']:
                raise Refused('Andere Version installiert. Dafür ausschließlich update.sh verwenden.')
            mounted_evidence(config)
            verify(CURRENT.resolve(), args.trusted_key)
            diagnose(config)
            print('Installation bereits vorhanden und geprüft; keine Daten oder Zugangsdaten geändert.')
            return
        # Resume only the exact signed package recorded before the first mutation.
        if config.get('pending_manifest') != sha256(package / 'manifest.json'):
            raise Refused('Abgebrochene Installation benötigt dasselbe geprüfte Paket.')
    else:
        if Path('/opt/fca').exists() or CURRENT.exists() or CURRENT.is_symlink() or COMPOSE.exists() or any(p.exists() and any(p.iterdir()) for p in (Path('/var/lib/fca'), Path('/etc/fca/secrets'))):
            raise Refused('Vorhandene FCA-Installation erkannt. Keine automatische Übernahme oder Neuinstallation.')
        config = validate_config(json.loads(Path(args.config).read_text())) if args.config else interactive()
        if not os.path.ismount(config['evidence_root']) or not empty_volume(Path(config['evidence_root'])):
            raise Refused('Für Erstinstallation ist ein bereits eingebundener, vollständig leerer Sicherungsdatenträger erforderlich.')
        # Never modify an existing web server configuration on a shared host.
        if any(p.exists() and any(p.iterdir()) for p in (Path('/etc/nginx/conf.d'), Path('/etc/nginx/sites-enabled'))):
            raise Refused('Bestehenden Webserver administrativ prüfen. Keine automatische Übernahme.')
    preflight(config)
    print('FCA-Installation; Abhängigkeiten werden ausschließlich aus dem signierten Paket installiert.')
    if not args.yes and input('Installation auf diesem vorbereiteten Server beginnen? [ja/NEIN]: ') != 'ja':
        raise Refused('Installation abgebrochen.')
    directory('/etc/fca', 0o750)
    directory('/etc/fca/secrets', 0o750)
    if not resuming:
        config['volume_id'] = str(uuid.uuid4())
        config['pending_manifest'] = sha256(package / 'manifest.json')
        config['installation_status'] = 'initializing'
        write(CONFIG, json.dumps(config, indent=2) + '\n')
    directory(config['state_root'])
    cloud = canonical(Path(config['state_root']) / 'cloud-auth')
    cloud.mkdir(mode=0o700, exist_ok=True)
    if not cloud.is_dir() or cloud.stat().st_uid not in (0,10001) or cloud.stat().st_mode & 0o077:
        raise Refused('Cloud-Verzeichnis ist nicht ausreichend geschützt.')
    os.chown(cloud, 10001, 10001)
    directory(config['backup_root'])
    mounted_evidence(config, initialize=True)
    secret('postgres_password', config)
    secret('cloud_master_key', config)
    release = materialize(package, manifest)
    verify(release, args.trusted_key)
    install_dependencies(release, manifest)
    load_images(release, manifest)
    configure_files(config, manifest, release)
    switch(release)
    compose('up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '180', 'database')
    migrations(release)
    start()
    diagnose(config)
    config['installation_status'] = 'ready'
    config.pop('pending_manifest', None)
    write(CONFIG, json.dumps(config, indent=2) + '\n')
    print('FCA eingerichtet. Startkonto: admin. Initialpasswort ausschließlich lokal unter /etc/fca/secrets/initial_admin_password abrufen und anschließend ändern.')


def stopped():
    compose('stop', 'worker', 'api')


def backup(config):
    mounted_evidence(config)
    backup_root = directory(config['backup_root'])
    size = sum(p.stat().st_size for root in (Path(config['evidence_root']), Path(config['state_root']) / 'cloud-auth', Path(config['state_root']) / 'postgres') for p in root.rglob('*') if p.is_file() and not p.is_symlink())
    if shutil.disk_usage(backup_root).free < size + 2 * GIB:
        raise Refused('Zu wenig freier Backupspeicher für Daten, Dump und 2-GiB-Reserve.')
    target = directory(backup_root / ('backup-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]))
    # All writers stay stopped from dump through evidence/credential snapshot.
    stopped()
    command = ['docker', 'compose', '--env-file', str(ENV), '-f', str(COMPOSE), 'exec', '-T', 'database']
    with (target / 'database.dump').open('xb') as handle:
        os.chmod(handle.name, 0o600)
        result = subprocess.run(command + ['pg_dump', '-U', 'fca_bootstrap', '-d', 'fca', '-Fc'], stdout=handle, stderr=subprocess.DEVNULL)
        if result.returncode:
            raise Refused('Datenbankbackup fehlgeschlagen; Dienste bleiben angehalten.')
    # Independent restore probe verifies the entire archive can be restored.
    probe = 'fca_restore_' + uuid.uuid4().hex
    try:
        compose('exec', '-T', 'database', 'createdb', '-U', 'fca_bootstrap', probe)
        with (target / 'database.dump').open('rb') as handle:
            result = subprocess.run(command + ['pg_restore', '--exit-on-error', '--no-owner', '-U', 'fca_bootstrap', '-d', probe], stdin=handle, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if result.returncode:
                raise Refused('Datenbank-Restoreprobe fehlgeschlagen.')
        original = sql('SELECT max(version) FROM schema_migrations;')
        if sql('SELECT max(version) FROM schema_migrations;', probe) != original:
            raise Refused('Restoreprobe stimmt nicht überein.')
    finally:
        compose('exec', '-T', 'database', 'dropdb', '--if-exists', '-U', 'fca_bootstrap', probe)
    with tarfile.open(target / 'state.tar', 'w') as archive:
        archive.add('/etc/fca', arcname='config')
        archive.add(Path(config['state_root']) / 'cloud-auth', arcname='cloud-auth')
        archive.add(config['evidence_root'], arcname='evidence')
        for field in ('certificate', 'certificate_key', 'ca_certificate'):
            archive.add(config[field], arcname='tls/' + field)
    (target / 'state.tar').chmod(0o600)
    release = CURRENT.resolve()
    metadata = dict(release=str(release), manifest_sha256=sha256(release / 'manifest.json'),
                    files={name: sha256(target / name) for name in ('database.dump', 'state.tar')},
                    status='restore_probe_passed', schema=int(original))
    write(target / 'backup.json', json.dumps(metadata, indent=2) + '\n')
    print('Backup mit Datenbank-Restoreprobe erstellt: ' + str(target))
    return target


def update(args):
    config = cfg()
    if config.get('installation_status') != 'ready':
        raise Refused('Erst die abgebrochene Installation mit install.sh abschließen.')
    mounted_evidence(config)
    preflight(config)
    package = canonical(args.package)
    manifest = verify(package, args.trusted_key)
    current_manifest = json.loads((CURRENT / 'manifest.json').read_text())
    if manifest['version'] == current_manifest['version']:
        if manifest != current_manifest:
            raise Refused('Versionsnummer mit anderem Inhalt; Update verweigert.')
        diagnose(config)
        print('Diese geprüfte Version ist bereits installiert.')
        return
    if manifest['schema'] < int(sql('SELECT max(version) FROM schema_migrations;')):
        raise Refused('Kein automatisches Schema-Downgrade. Dokumentierten Rollback verwenden.')
    if not args.yes and input('Geprüfte Version ' + manifest['version'] + ' mit Wartungsunterbrechung installieren? [ja/NEIN]: ') != 'ja':
        raise Refused('Update abgebrochen.')
    release = materialize(package, manifest)
    verify(release, args.trusted_key)
    # OS dependency changes are deliberately not part of an application update.
    for dep in manifest['dependencies']:
        installed = run(['dpkg-query', '-W', '-f=${Version}', dep['name']]).decode()
        if installed != dep['version']:
            raise Refused('Betriebssystemabhängigkeiten müssen vor dem Update separat abgeglichen werden.')
    load_images(release, manifest)
    old_release = CURRENT.resolve()
    old_compose = COMPOSE.read_text()
    saved = backup(config)  # errors never restart potentially inconsistent writers
    try:
        write(COMPOSE, json.dumps(render_compose(config, manifest, release), indent=2) + '\n')
        migrations(release)
        switch(release)
        start()
        diagnose(config)
    except Exception:
        stopped()
        # Runtime rollback only if schema remained compatible. Never undo database/data.
        if sql('SELECT max(version) FROM schema_migrations;') == str(current_manifest['schema']):
            write(COMPOSE, old_compose)
            switch(old_release)
            start()
        raise Refused('Update fehlgeschlagen. Sicherung: ' + str(saved) + '. Kein automatisches Zurückschreiben von Daten.') from None
    print('Update abgeschlossen; bestehende Schlüssel und Daten erhalten. Vorherige Version und Backup bleiben verfügbar.')


def rollback(args):
    config = cfg()
    release = canonical(RELEASES / args.version)
    if release.parent != RELEASES or not release.is_dir():
        raise Refused('Vorherige Version ist lokal nicht vorhanden.')
    manifest = verify(release, args.trusted_key)
    if sql('SELECT max(version) FROM schema_migrations;') != str(manifest['schema']):
        raise Refused('Rollback mit abweichendem Schema benötigt Wiederherstellung auf separatem Ziel und ausdrückliche Freigabe.')
    if input('Programm auf ' + manifest['version'] + ' zurücksetzen, Daten behalten? [ja/NEIN]: ') != 'ja':
        raise Refused('Rollback abgebrochen.')
    backup(config)
    write(COMPOSE, json.dumps(render_compose(config, manifest, release), indent=2) + '\n')
    switch(release)
    start()
    diagnose(config)
    print('Programmrollback abgeschlossen. Daten und Schlüssel wurden nicht zurückgeschrieben.')


def diagnose(config):
    checks = []
    def check(name, action):
        try:
            result = action()
            if result is False:
                raise Refused('Prüfung fehlgeschlagen.')
            checks.append({'check': name, 'ok': True})
        except Exception:
            checks.append({'check': name, 'ok': False})
    check('Sicherungsdatenträger und Kennung', lambda: mounted_evidence(config))
    check('Debian, Ressourcen, private IP und HTTPS-Dateien', lambda: preflight(config))
    check('Dienste und Container', lambda: _services())
    check('Datenbankschema', lambda: sql('SELECT max(version) FROM schema_migrations;') == '9')
    check('Schlüsselrechte', lambda: all(p.stat().st_uid == 0 and not p.stat().st_mode & 0o007 and not p.is_symlink() for p in Path('/etc/fca/secrets').iterdir()))
    check('Cloud-Zustand und Schreibrechte', lambda: _permissions(config))
    check('Private Bindung und interne Datenbank', lambda: _bindings(config))
    check('nginx-Konfiguration', lambda: run(['nginx', '-t']))
    check('HTTPS-Vertrauen und Anwendungsantwort', lambda: _https(config))
    memory = {line.split(':')[0]: line.split(':')[1].strip() for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:', 'MemAvailable:'))}
    report = {'checks': checks, 'memory': memory,
              'free_system_bytes': shutil.disk_usage('/var').free,
              'free_evidence_bytes': shutil.disk_usage(config['evidence_root']).free}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not all(c['ok'] for c in checks):
        raise Refused('Diagnose meldet Fehler. Installation ist noch nicht abgenommen.')
    return report


def _services():
    run(['systemctl', 'is-active', '--quiet', 'docker', 'nginx', 'fca'])
    raw = compose('ps', '--format', 'json').decode().strip()
    try:
        values = json.loads(raw)
        values = values if isinstance(values, list) else [values]
    except ValueError:
        values = [json.loads(line) for line in raw.splitlines() if line]
    return {v.get('Service') for v in values} == {'api','worker','database'} and all(v.get('Health') == 'healthy' and v.get('State') == 'running' for v in values)


def _bindings(config):
    ids = compose('ps', '-q').decode().split()
    if len(ids) != 3:
        return False
    containers = json.loads(run(['docker','inspect',*ids]))
    for container in containers:
        service = container['Config']['Labels']['com.docker.compose.service']
        ports = container['NetworkSettings']['Ports']
        published = [(port, b) for port, bindings in ports.items() for b in (bindings or [])]
        if service == 'api':
            if len(published) != 1 or published[0][0] != '8000/tcp' or published[0][1] != {'HostIp':'127.0.0.1','HostPort':'8000'}:
                return False
        elif published:
            return False
    # A different nginx include must not introduce a wildcard/HTTP listener.
    rendered = run(['nginx','-T']).decode()
    listeners = re.findall(r'^\s*listen\s+([^;]+);', rendered, re.MULTILINE)
    return listeners == [config['listen_address'] + ':443 ssl']


def _permissions(config):
    cloud = canonical(Path(config['state_root']) / 'cloud-auth')
    return cloud.stat().st_uid == 10001 and cloud.stat().st_mode & 0o777 == 0o700 and \
        compose('exec', '-T', 'api', 'python', '-c', "from backend.evidence import root; import os; assert os.access(root()/'FCA-Sicherungen',os.W_OK)") is not None


def _https(config):
    # Resolve the configured name, validate the chain AND SAN; no -k / CERT_NONE.
    context = ssl.create_default_context(cafile=config['ca_certificate'])
    with urlopen('https://' + config['server_name'] + '/api/health', context=context, timeout=10) as result:
        return result.status == 200


def main(argv=None):
    parser = argparse.ArgumentParser(description='FCA-Installation, Update und Diagnose')
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('install', 'update'):
        item = sub.add_parser(command)
        item.add_argument('--package', required=True, type=Path)
        item.add_argument('--trusted-key', required=True, type=Path)
        item.add_argument('--yes', action='store_true', help='Nur für vorab geprüfte automatisierte Installationen')
        if command == 'install':
            item.add_argument('--config', type=Path, help='Vorab geprüfte JSON-Antwortdatei, ohne Zugangsdaten')
    item = sub.add_parser('rollback')
    item.add_argument('--version', required=True)
    item.add_argument('--trusted-key', required=True, type=Path)
    sub.add_parser('diagnose')
    sub.add_parser('guard')
    sub.add_parser('backup')
    args = parser.parse_args(argv)
    if os.geteuid() != 0:
        parser.exit(1, 'Als root oder mit sudo ausführen.\n')
    os.umask(0o077)
    if args.command == 'guard':
        try:
            mounted_evidence(cfg())
        except (Refused, OSError, ValueError):
            parser.exit(1, 'FCA-Sicherungsdatenträger fehlt oder ist falsch.\n')
        return
    # One lifecycle writer. Do not place lock in a replaceable release directory.
    with open('/run/lock/fca-lifecycle.lock', 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(1, 'Ein Installations-/Wartungsvorgang läuft bereits.\n')
        try:
            if args.command == 'install':
                install(args)
            elif args.command == 'update':
                update(args)
            elif args.command == 'guard':
                mounted_evidence(cfg())
            elif args.command == 'rollback':
                rollback(args)
            elif args.command == 'diagnose':
                diagnose(cfg())
            elif args.command == 'backup':
                config = cfg()
                backup(config)
                start()
        except (Refused, ValueError, OSError, KeyError) as error:
            # Errors must never print secrets from subprocess output/config values.
            parser.exit(1, 'FCA: ' + (str(error) if isinstance(error, Refused) else 'Ungültige Konfiguration oder fehlende Voraussetzung.') + '\n')
