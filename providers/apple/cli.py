"""Manual test bench for an explicitly approved iCloud test account; not the FCA UI."""
import argparse
import getpass
import json
import os
from pathlib import Path
import stat
import sys
from uuid import UUID

from .adapter import ICloudSession, ProviderError, Scope


def main():
    parser = argparse.ArgumentParser(description='Isolated iCloud phase-2 test bench; no downloads or production case updates.')
    parser.add_argument('--case-id', type=UUID, required=True)
    parser.add_argument('--account-id', type=UUID, required=True)
    parser.add_argument('--service', choices=['drive', 'photos'], required=True)
    parser.add_argument('--scope', required=True, help='Explicit approved synthetic folder/album relative path; never account root')
    parser.add_argument('--operator', required=True)
    parser.add_argument('--state-root', type=Path, default=Path('/state'))
    parser.add_argument('--key-file', type=Path, default=Path('/run/secrets/icloud_test_key'))
    parser.add_argument('--connect-test-account', action='store_true', help='Explicitly initiate a real Apple login (default: offline preflight only)')
    args = parser.parse_args()
    try:
        approval = Scope(args.case_id, args.account_id, args.service, args.scope, args.operator)
        key_info = args.key_file.stat()
        if not stat.S_ISREG(key_info.st_mode) or stat.S_IMODE(key_info.st_mode) & 0o027:
            raise ProviderError('External key must be a private regular secret file (0600 or 0640).')
        key = args.key_file.read_text().strip()
        root = args.state_root.resolve(strict=True)
        if root != args.state_root.absolute() or stat.S_IMODE(root.stat().st_mode) & 0o077:
            raise ProviderError('Private canonical state directory required.')
        directory = root
        for part in (str(args.case_id), str(args.account_id)):
            directory = directory / part
            directory.mkdir(mode=0o700, exist_ok=True)
            if directory.is_symlink() or directory.stat().st_uid != os.getuid():
                raise ProviderError('Private account directory ownership required.')
        with ICloudSession(directory / 'rclone.conf', key, approval) as adapter:
            capabilities = adapter.capabilities()
            print(json.dumps(capabilities, ensure_ascii=False))
            if not args.connect_test_account:
                print('Offline preflight only. No Apple login or cloud access performed.')
                return 0
            if not sys.stdin.isatty():
                raise ProviderError('Real login requires an interactive trusted terminal; never pipe credentials.')
            print('Only use the explicitly approved test account and synthetic scope. No downloads will run.')
            apple_id = input('Testkonto Apple-ID: ').strip()
            password = getpass.getpass('Apple-Passwort (kein app-spezifisches Passwort): ')
            try:
                step = adapter.begin(apple_id, password)
            finally:
                password = None
            while step.status == 'challenge':
                if step.choices:
                    print('Angebotene Auswahlwerte: ' + ', '.join(step.choices))
                code = getpass.getpass('2FA-Code bzw. angebotene Auswahl (oder sms): ')
                try:
                    step = adapter.answer(code)
                finally:
                    code = None
            entries = adapter.list_approved_directory()
            # Neither account identifiers, names, tokens nor filenames enter console logs.
            print(json.dumps({'real_apple_authentication': True, 'approved_scope_listed': True,
                              'entry_count': len(entries), 'downloads_started': False}))
            print('Manual test succeeded; FCA application account status was not changed. Keep the encryption key separately.')
        return 0
    except (ProviderError, ValueError, OSError):
        print('iCloud test could not complete. Check private configuration, scope, credentials and 2FA. No upstream details logged.', file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print('iCloud test cancelled.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
