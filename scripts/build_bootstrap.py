#!/usr/bin/env python3
"""Generate a pinned bootstrap ONLY from an already signed, verified release archive."""
import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tarfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infrastructure.installer.package import sha256

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'https://github.com/hnslng/forensic-cloud-acquisition'


def generate(archive, key, version, output):
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.-]+)?', version):
        raise ValueError('Ungültige Version')
    if archive.name != f'fca-{version}.tar.gz':
        raise ValueError('Archivname muss zur Releaseversion passen')
    checksum = Path(str(archive)+'.sha256')
    subprocess.run(['openssl','pkeyutl','-verify','-pubin','-inkey',str(key),'-rawin','-in',str(checksum),'-sigfile',str(checksum)+'.sig'], check=True, capture_output=True)
    if checksum.read_text() != sha256(archive)+'  '+archive.name+'\n':
        raise ValueError('Archivprüfsumme stimmt nicht')
    with tarfile.open(archive,'r:gz') as source:
        members = source.getmembers()
        manifest = json.load(source.extractfile(f'fca-{version}/manifest.json'))
        if manifest['version'] != version:
            raise ValueError('Manifestversion stimmt nicht')
    locked = dict(version=version, public_key=key.read_text(), archive_sha256=sha256(archive),
                  archive_bytes=archive.stat().st_size, unpacked_bytes=sum(m.size for m in members))
    output.mkdir(parents=True, exist_ok=False)
    script = output/'fca-bootstrap.py'
    script.write_text((ROOT/'infrastructure/installer/bootstrap.py.in').read_text().replace('__FCA_RELEASE_JSON__',repr(locked)))
    script.chmod(0o644)
    url = REPOSITORY+f'/releases/download/v{version}/fca-bootstrap.py'
    # The copyable command pins the bootstrap itself before executing its code.
    loader = "import hashlib,os,pathlib,subprocess,sys,tempfile,urllib.request; u="+repr(url)+"; b=urllib.request.urlopen(u,timeout=60).read(1048577); expected="+repr(sha256(script))+"; (len(b)<=1048576 and hashlib.sha256(b).hexdigest()==expected) or sys.exit('Bootstrap-Pruefsumme ungueltig'); f=tempfile.NamedTemporaryFile(prefix='fca-start-',suffix='.py'); f.write(b); f.flush(); r=subprocess.run([sys.executable,f.name]); sys.exit(r.returncode)"
    lock=json.loads((ROOT/'infrastructure/installer/debian13-amd64.lock.json').read_text())
    prerequisites={'python3':'3.13.5-1', 'openssl':lock['direct_packages']['openssl'], 'ca-certificates':lock['direct_packages']['ca-certificates']}
    packages=' '.join(shlex.quote(k+'='+v) for k,v in prerequisites.items())
    command="bash -c "+shlex.quote("set -eu; [ \"$(id -u)\" = 0 ] || { echo 'Bitte als root starten.' >&2; exit 1; }; if ! python3 -c 'import ssl, urllib.request, tarfile' >/dev/null 2>&1 || ! command -v openssl >/dev/null || [ ! -s /etc/ssl/certs/ca-certificates.crt ]; then apt-get update; apt-get install -y --no-install-recommends "+packages+"; fi; python3 -c "+shlex.quote(loader))
    (output/'INSTALL.txt').write_text('Als root auf Debian 13 amd64 ausführen. Repository und Release müssen öffentlich sein.\n\n'+command+'\n')
    (output/'bootstrap-lock.json').write_text(json.dumps({k:v for k,v in locked.items() if k!='public_key'},indent=2)+'\n')
    return script


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',required=True,type=Path)
    p.add_argument('--trusted-key',required=True,type=Path)
    p.add_argument('--version',required=True)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    generate(a.archive,a.trusted_key,a.version,a.output)

if __name__=='__main__':
    main()
