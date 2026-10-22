#!/usr/bin/env python3
"""Release engineering only: build a versioned, signed, self-contained amd64 package.

Run after application CI on a disposable Debian 13 amd64 builder. The .deb directory
must contain the complete dependency closure from that clean baseline (see docs).
No signing key is copied to the package. No GitHub credentials needed at runtime.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infrastructure.installer.package import write_manifest, verify

ROOT = Path(__file__).resolve().parents[1]
POSTGRES = 'postgres@sha256:858bb5e98eed02eb8cafbcdc007f9a65d1b613972028944a8ec2133ccaf80d27'


def call(*args, **kwargs):
    return subprocess.check_output([str(v) for v in args], **kwargs).decode().strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--debs', type=Path, required=True)
    parser.add_argument('--signing-key', type=Path, required=True)
    parser.add_argument('--trusted-key', type=Path, required=True)
    parser.add_argument('--app-image', required=True, help='CI-tested local image ID sha256:...')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Ausgabe muss neu sein.')
    args.output.mkdir(parents=True)
    for name in ('infrastructure/installer', 'frontend', 'migrations'):
        shutil.copytree(ROOT / name, args.output / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (args.output / 'scripts').mkdir()
    for name in ('fca_admin.py', 'configure_phase1_database.py', 'prepare_private_https.py'):
        shutil.copy(ROOT / 'scripts' / name, args.output / 'scripts' / name)
    shutil.copy(ROOT / 'install.sh', args.output / 'install.sh')
    shutil.copy(ROOT / 'update.sh', args.output / 'update.sh')
    shutil.copytree(ROOT / 'docs', args.output / 'docs')
    env = dict(os.environ, FCA_STATE_ROOT='/var/lib/fca', FCA_EVIDENCE_ROOT='/srv/fca/evidence',
               FCA_POSTGRES_PASSWORD_FILE='/etc/fca/secrets/postgres_password',
               FCA_API_PASSWORD_FILE='/etc/fca/secrets/api_password', FCA_PUBLIC_ORIGIN='https://fca.invalid')
    template = json.loads(call('docker', 'compose', '-f', ROOT / 'compose.yaml', '--profile', 'application', 'config', '--format', 'json', env=env))
    for service in template['services'].values():
        service.pop('build', None)
    (args.output / 'compose.template.json').write_text(json.dumps(template, indent=2) + '\n')
    call('docker', 'pull', '--platform', 'linux/amd64', POSTGRES)
    postgres_id = call('docker', 'image', 'inspect', '--format', '{{.Id}}', POSTGRES)
    for image in (args.app_image, postgres_id):
        if call('docker', 'image', 'inspect', '--format', '{{.Architecture}}', image) != 'amd64':
            parser.error('Nur amd64-Images werden unterstützt.')
    subprocess.check_call(['docker', 'save', '-o', str(args.output / 'images.tar'), args.app_image, POSTGRES])
    debs = args.output / 'debs'
    debs.mkdir()
    dependencies = []
    for source in sorted(args.debs.glob('*.deb')):
        shutil.copy(source, debs / source.name)
        package = call('dpkg-deb', '-f', source, 'Package')
        version = call('dpkg-deb', '-f', source, 'Version')
        dependencies.append(dict(name=package, version=version, file='debs/' + source.name))
    needed = {'docker.io', 'docker-cli', 'docker-compose', 'nginx', 'openssl', 'ca-certificates'}
    # Already-installed baseline packages are locked too: explicitly download them.
    if not needed.issubset({v['name'] for v in dependencies}):
        parser.error('Die gesperrten direkten Abhängigkeiten fehlen.')
    source = call('git', '-C', ROOT, 'rev-parse', 'HEAD')
    write_manifest(args.output, args.version, args.app_image, postgres_id, dependencies, source)
    subprocess.check_call(['openssl', 'pkeyutl', '-sign', '-inkey', str(args.signing_key), '-rawin', '-in', str(args.output / 'manifest.json'), '-out', str(args.output / 'manifest.sig')])
    verify(args.output, args.trusted_key)
    print('Signiertes Installationspaket erstellt: ' + str(args.output))


if __name__ == '__main__':
    main()
