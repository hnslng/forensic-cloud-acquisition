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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    lock = json.loads((Path(__file__).resolve().parents[1] / 'infrastructure/installer/debian13-amd64.lock.json').read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(['apt-get', 'update'])
    packages = [f'{k}={v}' for k, v in lock['direct_packages'].items()]
    subprocess.check_call(['apt-get', '-y', '--download-only', '--no-install-recommends', '-o', 'Dir::Cache::archives=' + str(args.output.resolve()), 'install', *packages])
    # Include exact direct packages even if already present in the baseline image.
    subprocess.check_call(['apt-get', 'download', *packages], cwd=args.output)
    print('Vollständigen Satz vor Freigabe in frischer Debian-VM offline installieren und testen.')


if __name__ == '__main__':
    main()
