#!/usr/bin/env python3
"""Run only on a disposable clean Debian 13 amd64 RELEASE BUILDER, never a server.

APT verifies signed Debian metadata and .deb hashes. Resolve once, then sign the
entire downloaded dependency closure into the release. Server installation never
resolves/downloads dependencies. If a locked version disappears, build fails.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    lock = json.loads((Path(__file__).resolve().parents[1] / 'infrastructure/installer/debian13-amd64.lock.json').read_text())
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('Neuen leeren Ausgabeordner wählen; keine alten .deb-Versionen beimischen.')
    args.output.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(['apt-get', 'update'])
    packages = [f'{k}={v}' for k, v in lock['direct_packages'].items()]
    # Resolve against an EMPTY package status database. Otherwise APT omits
    # dependencies already present in the builder and minimal target servers fail.
    # Download-only never unpacks packages or changes the real dpkg database.
    with tempfile.TemporaryDirectory(prefix='fca-dependency-state-') as state:
        empty_status = Path(state) / 'status'
        empty_status.touch()
        subprocess.check_call(['apt-get', '-y', '--download-only', '--no-install-recommends',
            '-o', 'Dir::State::status=' + str(empty_status),
            '-o', 'Dir::State::extended_states=' + str(Path(state) / 'extended_states'),
            '-o', 'Dir::Cache::archives=' + str(args.output.resolve()), 'install', *packages])
    # Include exact direct packages even if already present in the baseline image.
    subprocess.check_call(['apt-get', 'download', *packages], cwd=args.output)
    print('Vollständigen Satz vor Freigabe in frischer Debian-VM offline installieren und testen.')


if __name__ == '__main__':
    main()
