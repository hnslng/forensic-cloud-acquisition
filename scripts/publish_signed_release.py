#!/usr/bin/env python3
"""Reassemble and publish an OFFLINE-signed release; CI never receives a private key."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import types
from urllib.request import Request, urlopen
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from infrastructure.installer.package import sha256, verify
from scripts.build_install_package import write_archive
from scripts.build_bootstrap import generate

REPO='hnslng/forensic-cloud-acquisition'
ROOT=Path(__file__).resolve().parents[1]


def api(path):
    request=Request('https://api.github.com/repos/'+REPO+path,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN']})
    with urlopen(request,timeout=30) as response:
        return json.load(response)


def main():
    if os.environ.get('GITHUB_REPOSITORY') != REPO or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('Releaseveröffentlichung ausschließlich im vorgesehenen Repository-CI.')
    folder=Path(sys.argv[1]).resolve()
    settings=json.loads((folder/'publish.json').read_text())
    version=settings['version']
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+-rc\.[0-9]+',version) or folder.name != 'v'+version:
        raise SystemExit('Dieser Freigabeweg veröffentlicht ausschließlich explizite Releasekandidaten.')
    run=api('/actions/runs/'+str(int(settings['ci_run'])))
    if run['conclusion'] != 'success' or run['head_sha'] != settings['ci_head_sha']:
        raise SystemExit('Freigegebene frische VM-Tests sind nicht erfolgreich.')
    artifact=api('/actions/artifacts/'+str(int(settings['artifact_id'])))
    if artifact['digest'] != settings['artifact_digest'] or artifact['workflow_run']['id'] != settings['ci_run'] or artifact['expired']:
        raise SystemExit('CI-Artefakt stimmt nicht mit der signierten Freigabe überein.')
    with tempfile.TemporaryDirectory(prefix='fca-publication-') as temporary:
        work=Path(temporary)
        candidate=work/'candidate'
        subprocess.run(['gh','run','download',str(settings['ci_run']),'--repo',REPO,'--name','fca-online-installer-test-candidate','--dir',str(candidate)],check=True)
        lock=json.loads((candidate/'bootstrap-lock.json').read_text())
        archive=candidate/('fca-'+lock['version']+'.tar.gz')
        if sha256(archive) != settings['candidate_sha256'] or lock['archive_sha256'] != settings['candidate_sha256']:
            raise SystemExit('CI-Paketbytes wurden verändert.')
        lock['public_key']=(candidate/'trusted-release.pub').read_text()
        validator=types.ModuleType('fca_release_validator')
        exec(compile((ROOT/'infrastructure/installer/bootstrap.py.in').read_text().replace('__FCA_RELEASE_JSON__',repr(lock)),'bootstrap-validator','exec'),validator.__dict__)
        validator.signature(candidate/'trusted-release.pub',Path(str(archive)+'.sha256'),Path(str(archive)+'.sha256.sig'))
        extraction=work/'extraction';extraction.mkdir(mode=0o700)
        package=validator.unpack(archive,extraction)
        original=verify(package,candidate/'trusted-release.pub')
        if original['source_revision'] != settings['source_revision']:
            raise SystemExit('Ungeprüfter Quellstand im Paket.')
        # Only the manifest/version/signature changes. Every payload byte must still
        # match the separately signed production manifest before an archive is made.
        for name in ('manifest.json','manifest.sig'):
            shutil.copyfile(folder/name,package/name)
        production=verify(package,folder/'fca-release.pub')
        if production['version'] != version or production['source_revision'] != settings['source_revision']:
            raise SystemExit('Releaseversion oder Quellstand stimmt nicht.')
        assets=work/'assets';assets.mkdir()
        final_archive=assets/('fca-'+version+'.tar.gz')
        write_archive(package,final_archive,version)
        if sha256(final_archive) != settings['archive_sha256']:
            raise SystemExit('Archiv nicht bytegleich zum lokal freigegebenen Release. Keine Veröffentlichung.')
        for path in folder.iterdir():
            if path.is_file() and path.name not in ('manifest.json','manifest.sig','publish.json'):
                shutil.copyfile(path,assets/path.name)
        validator.signature(folder/'fca-release.pub',Path(str(final_archive)+'.sha256'),Path(str(final_archive)+'.sha256.sig'))
        expected=work/'expected-bootstrap'
        generate(final_archive,folder/'fca-release.pub',version,expected)
        for name in ('fca-bootstrap.py','INSTALL.txt','bootstrap-lock.json'):
            if (folder/name).read_bytes() != (expected/name).read_bytes():
                raise SystemExit('Bootstrap oder Startbefehl weicht von der signierten Freigabe ab.')
        # Existing releases are never edited/replaced. Draft remains on failed upload.
        tag='v'+version
        subprocess.run(['gh','release','create',tag,'--repo',REPO,'--target',settings['source_revision'],'--draft','--prerelease','--title','FCA '+version+' – Debian-Installer','--notes-file',str(folder/'RELEASE-NOTES.md')],check=True)
        subprocess.run(['gh','release','upload',tag,'--repo',REPO,*map(str,sorted(assets.iterdir()))],check=True)
        subprocess.run(['gh','release','edit',tag,'--repo',REPO,'--draft=false','--prerelease'],check=True)
        print('SIGNED_FCA_RELEASE_PUBLISHED '+tag)

if __name__=='__main__':
    main()
