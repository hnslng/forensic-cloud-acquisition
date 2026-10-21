#!/usr/bin/env python3
"""Render the approved VM's NoCloud seed with a public key, never a private key."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-key', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    key = args.public_key.read_text().strip()
    if '\n' in key or key.split(' ', 1)[0] not in ('ssh-rsa', 'ssh-ed25519', 'ecdsa-sha2-nistp256'):
        raise SystemExit('Nur ein gültiger einzeiliger öffentlicher SSH-Schlüssel ist zulässig.')
    template = Path(__file__).resolve().parents[1] / 'infrastructure/proxmox/user-data.yaml.in'
    args.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    files = {
        'user-data': template.read_text().replace('@PUBLIC_KEY_JSON@', json.dumps(key)),
        'meta-data': 'instance-id: fca-lab-105-20261021\nlocal-hostname: fca-lab\n',
        'network-config': 'version: 2\nethernets:\n  lab:\n    match:\n      macaddress: "bc:24:11:fa:01:05"\n    dhcp4: true\n    dhcp6: false\n    accept-ra: false\n',
    }
    if any((args.output_dir / name).exists() for name in files):
        raise SystemExit('Seed-Dateien existieren bereits; kein Überschreiben.')
    for name, content in files.items():
        (args.output_dir / name).write_text(content)
    print('NoCloud-Seed mit öffentlichem Schlüssel vorbereitet.')


if __name__ == '__main__':
    main()
