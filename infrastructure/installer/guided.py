"""Minimal interactive setup, shared by the signed online and offline package.

Never partitions/formats disks, edits DNS or changes an existing certificate.
"""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import tempfile

from infrastructure.installer import manager as m
from infrastructure.installer.package import Refused, canonical, verify


def ask(label, default=None):
    value = input(label + (f' [{default}]' if default else '') + ': ').strip()
    return value or default


def local_addresses():
    return [(a['local'], a['prefixlen']) for i in json.loads(m.run(['ip', '-j', 'address']))
            for a in i.get('addr_info', []) if a.get('family') == 'inet'
            and ipaddress.ip_address(a['local']).is_private
            and not ipaddress.ip_address(a['local']).is_loopback]


def create_lab_tls(config):
    folder = canonical('/etc/fca/tls')
    # Do not partially replace an existing CA, server certificate or key.
    if folder.exists() and any(folder.iterdir()):
        raise Refused('TLS-Verzeichnis ist bereits belegt. Vorhandene Zertifikate auswählen.')
    m.directory(folder)
    host = config['server_name']
    san = ('IP:' if m._is_ip(host) else 'DNS:') + host
    with tempfile.TemporaryDirectory(prefix='fca-tls-', dir=folder) as temporary:
        work = Path(temporary)
        m.run(['openssl', 'req', '-x509', '-newkey', 'rsa:3072', '-nodes', '-sha256',
               '-keyout', work/'ca.key', '-out', work/'ca.pem', '-subj', '/CN=FCA private Labor-CA', '-days', '3650',
               '-addext', 'basicConstraints=critical,CA:TRUE,pathlen:0',
               '-addext', 'keyUsage=critical,keyCertSign,cRLSign'])
        m.run(['openssl', 'req', '-newkey', 'rsa:3072', '-nodes', '-sha256',
               '-keyout', work/'privkey.pem', '-out', work/'request.csr', '-subj', '/CN='+host])
        (work/'extensions').write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\nsubjectAltName='+san+'\n')
        m.run(['openssl', 'x509', '-req', '-in', work/'request.csr', '-CA', work/'ca.pem',
               '-CAkey', work/'ca.key', '-CAcreateserial', '-out', work/'fullchain.pem',
               '-days', '365', '-sha256', '-extfile', work/'extensions'])
        for name in ('ca.key', 'ca.pem', 'privkey.pem', 'fullchain.pem'):
            m.write(folder/name, (work/name).read_text(), 0o600 if name.endswith('.key') or name == 'privkey.pem' else 0o644)
    print('Neue private Labor-CA: /etc/fca/tls/ca.pem. Dieses öffentliche CA-Zertifikat am Arbeitsplatz als vertrauenswürdig hinterlegen.')
    print('Der private CA-Schlüssel bleibt geschützt auf dem Server; im Behördenbetrieb die vorhandene interne CA verwenden.')


def configure():
    addresses = local_addresses()
    default_ip = addresses[0][0] if len(addresses) == 1 else None
    mode = ask('Betrieb: labor oder wireguard', 'labor')
    address = ask('Vorhandene private Server-IP', default_ip)
    host = ask('HTTPS-Name oder Labor-IP', address if mode == 'labor' else None)
    networks = [str(ipaddress.ip_network(f'{ip}/{bits}', strict=False)) for ip, bits in addresses if ip == address]
    allowed = ask('Zugelassene private Netze (Komma getrennt)', networks[0] if networks else None)
    evidence = ask('Speicherort der Cloud-Sicherungen', '/srv/fca/evidence')
    backup = ask('Speicherort der Backups', '/var/backups/fca')
    profile = ask('Ressourcenprofil: labor, standard oder behoerde', 'labor')
    tls = ask('HTTPS: vorhandene interne Zertifikate oder neue Labor-CA? (intern/labor)', 'labor' if mode == 'labor' else 'intern')
    if tls not in ('intern', 'labor') or (mode != 'labor' and tls != 'intern'):
        raise Refused('Neue CA ausschließlich im Laborbetrieb zulässig.')
    config = dict(mode=mode, listen_address=address, server_name=host,
                  allowed_networks=[v.strip() for v in allowed.split(',')], evidence_root=evidence,
                  backup_root=backup, profile=profile,
                  certificate='/etc/fca/tls/fullchain.pem', certificate_key='/etc/fca/tls/privkey.pem', ca_certificate='/etc/fca/tls/ca.pem')
    if tls == 'intern':
        for field, label in (('certificate','Zertifikatskette'), ('certificate_key','Privater HTTPS-Schlüssel'), ('ca_certificate','Interne CA-Kette')):
            config[field] = ask(label, config[field])
    config = m.validate_config(config)
    path = canonical(config['evidence_root'])
    if path.exists() and (not path.is_dir() or not m.empty_volume(path)):
        raise Refused('Speicherort ist belegt. Bestehende Daten werden niemals übernommen oder gelöscht.')
    use_directory = not os.path.ismount(path)
    if use_directory:
        if mode != 'labor':
            raise Refused('Für den Behördenbetrieb zuerst einen leeren Datenträger am Speicherort einbinden.')
        print('Kein eigener Datenträger eingebunden. Im Labor kann ein neuer leerer Ordner verwendet werden. Er teilt den Speicher mit dem vorhandenen Dateisystem. Es wird nichts formatiert.')
        if ask('Diesen Speicher ausdrücklich verwenden? Zum Bestätigen SYSTEMSPEICHER eingeben') != 'SYSTEMSPEICHER':
            raise Refused('Abgebrochen. Alternativ einen leeren Datenträger einbinden und erneut starten.')
        ancestor = path
        while not ancestor.exists():
            ancestor = ancestor.parent
        identity = m.run(['findmnt', '-n', '-o', 'UUID', '-T', str(ancestor)]).decode().strip()
        config.update(storage_mode='directory', storage_filesystem_uuid=identity)
        config = m.validate_config(config)
    print('FCA wird unter https://' + host + ' eingerichtet; Sicherungen: ' + str(path))
    if ask('Installation mit diesen Angaben beginnen? (ja/NEIN)', 'NEIN') != 'ja':
        raise Refused('Installation abgebrochen.')
    if tls == 'labor':
        create_lab_tls(config)
    if use_directory:
        m.directory(path, 0o755)
    return config


def main(argv=None):
    parser = argparse.ArgumentParser(description='Geführte FCA-Erstinstallation')
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--trusted-key', type=Path, required=True)
    args = parser.parse_args(argv)
    if os.geteuid() != 0:
        parser.exit(1, 'Bitte als root starten.\n')
    os.umask(0o077)
    try:
        verify(args.package, args.trusted_key)
        # Resume and repetition reuse the existing configuration without new keys.
        if m.CONFIG.exists():
            return m.main(['install', '--package', str(args.package), '--trusted-key', str(args.trusted_key)])
        # Protect the entire wizard, including CA and directory preparation.
        import fcntl
        with open('/run/lock/fca-lifecycle.lock', 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            m.require_new_host()
            config = configure()
            m.force_local_docker()
            # Keep the lock through installation. Answers contain no credentials.
            with tempfile.TemporaryDirectory(prefix='fca-answers-') as temporary:
                answers = Path(temporary)/'answers.json'
                m.write(answers, json.dumps(config))
                m.install(argparse.Namespace(package=args.package, trusted_key=args.trusted_key, config=answers, yes=True))
    except (Refused, OSError, ValueError, EOFError) as error:
        parser.exit(1, 'Installation angehalten: ' + str(error) + '\n')
