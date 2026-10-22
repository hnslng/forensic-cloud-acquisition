#!/usr/bin/env python3
"""Release engineering: record SHA-256 for binary wheels of EXACT locked versions.

Review/commit this lock and run CI before publishing. Never resolves latest and
never runs on an installation server. PyPI metadata is fetched via verified HTTPS.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def package(line):
    name, version = line.split('==')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or not re.fullmatch(r'[0-9.]+', version):
        raise ValueError('Exact simple package versions required')
    with urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=30) as response:
        value = json.load(response)
    hashes = sorted({v['digests']['sha256'] for v in value['urls'] if v['packagetype'] == 'bdist_wheel'})
    if not hashes or any(not re.fullmatch('[0-9a-f]{64}', v) for v in hashes):
        raise ValueError('Missing valid binary wheel hashes: ' + line)
    return line + ' \\\n' + ' \\\n'.join('    --hash=sha256:' + v for v in hashes)


def main():
    lines = [v.strip() for v in (ROOT / 'backend/requirements.lock').read_text().splitlines() if v.strip() and not v.startswith('#')]
    with ThreadPoolExecutor(max_workers=4) as pool:
        entries = list(pool.map(package, lines))
    target = ROOT / 'backend/requirements.hashes'
    target.write_text('# Generated from exact requirements.lock versions and official PyPI SHA-256 metadata.\n# Runtime installs binary wheels only; review this file and rerun CI before release.\n' + '\n\n'.join(entries) + '\n')
    print('Binary wheel hashes locked for', len(entries), 'packages.')


if __name__ == '__main__':
    main()
