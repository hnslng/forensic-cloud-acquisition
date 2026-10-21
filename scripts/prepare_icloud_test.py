#!/usr/bin/env python3
"""Prepare an isolated manual iCloud test context. No account or cloud access."""
import argparse
import json
import os
from pathlib import Path
import secrets
from uuid import UUID, uuid4


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run as root on the FCA test VM.')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case-id', type=UUID)
    parser.add_argument('--account-id', type=UUID)
    args = parser.parse_args()
    case_id, account_id = args.case_id or uuid4(), args.account_id or uuid4()
    state_root = Path('/var/lib/fca/phase2-icloud')
    state_root.mkdir(mode=0o700, exist_ok=True)
    if state_root.is_symlink():
        raise SystemExit('Refusing a symlink state root.')
    os.chown(state_root, 10001, 10001)
    state_root.chmod(0o700)
    key_root = Path('/etc/fca/secrets/phase2-icloud')
    key_root.mkdir(mode=0o700, exist_ok=True)
    if key_root.is_symlink():
        raise SystemExit('Refusing a symlink key root.')
    key = key_root / (str(case_id) + '-' + str(account_id) + '.key')
    config = state_root / str(case_id) / str(account_id) / 'rclone.conf'
    if not key.exists():
        if config.exists():
            raise SystemExit('Existing configuration has lost its key; manual recovery required.')
        descriptor = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        with os.fdopen(descriptor, 'w') as handle:
            handle.write(secrets.token_urlsafe(48) + '\n')
        os.chown(key, 0, 10001)
        key.chmod(0o640)
    print(json.dumps({'case_id': str(case_id), 'account_id': str(account_id),
                      'key_file': str(key), 'state_root': str(state_root),
                      'application_database_modified': False, 'cloud_access_performed': False}, indent=2))


if __name__ == '__main__':
    main()
