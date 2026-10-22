"""Signed online bootstrap trust and guided setup tests; synthetic artifacts only."""
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from scripts.build_bootstrap import generate
from scripts.build_install_package import export_archive
from infrastructure.installer import guided, manager
from infrastructure.installer.package import Refused, write_manifest


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.key=self.root/'private.key'; self.pub=self.root/'release.pub'
        subprocess.run(['openssl','genpkey','-algorithm','ED25519','-out',str(self.key)],check=True,capture_output=True)
        subprocess.run(['openssl','pkey','-in',str(self.key),'-pubout','-out',str(self.pub)],check=True,capture_output=True)
        package=self.root/'package'; package.mkdir()
        (package/'synthetic.txt').write_text('only synthetic data')
        write_manifest(package,'0.6.0-test.1','sha256:'+'a'*64,'sha256:'+'b'*64,[],'c'*40)
        subprocess.run(['openssl','pkeyutl','-sign','-inkey',str(self.key),'-rawin','-in',str(package/'manifest.json'),'-out',str(package/'manifest.sig')],check=True,capture_output=True)
        self.archive=self.root/'fca-0.6.0-test.1.tar.gz'
        export_archive(package,self.archive,'0.6.0-test.1',self.key)
        script=generate(self.archive,self.pub,'0.6.0-test.1',self.root/'bootstrap')
        self.mod=types.ModuleType('fca_bootstrap_test')
        exec(compile(script.read_text(),str(script),'exec'),self.mod.__dict__)
        self.work=self.root/'work'; self.work.mkdir()

    def download_fixture(self,url,destination,maximum):
        source=self.root/url.rsplit('/',1)[-1]
        self.assertLessEqual(source.stat().st_size,maximum)
        shutil.copyfile(source,destination)

    def test_signed_download_extracts_without_running_installer(self):
        with patch.object(self.mod,'download',side_effect=self.download_fixture):
            package,key=self.mod.fetch_release(self.work)
        self.assertEqual((package/'synthetic.txt').read_text(),'only synthetic data')
        self.assertEqual(key.read_text(),self.pub.read_text())

    def test_bootstrap_command_pins_own_hash_and_release(self):
        command=(self.root/'bootstrap/INSTALL.txt').read_text()
        self.assertIn('/releases/download/v0.6.0-test.1/fca-bootstrap.py',command)
        self.assertIn('hashlib.sha256(b).hexdigest()==expected',command)
        self.assertNotIn('/latest/',command)
        self.assertNotIn('Authorization',command)
        subprocess.run(['bash','-n'],input=command.split('\n\n')[1].encode(),check=True)

    def test_bad_signature_stops_before_archive_download(self):
        Path(str(self.archive)+'.sha256.sig').write_bytes(b'x'*64)
        calls=[]
        def fetch(url,*args):
            calls.append(url); self.download_fixture(url,*args)
        with patch.object(self.mod,'download',side_effect=fetch), self.assertRaises(self.mod.Refused):
            self.mod.fetch_release(self.work)
        self.assertEqual(len(calls),2)
        self.assertFalse((self.work/self.archive.name).exists())

    def test_tampered_archive_rejected_before_unpack(self):
        content=bytearray(self.archive.read_bytes()); content[-1]^=1; self.archive.write_bytes(content)
        with patch.object(self.mod,'download',side_effect=self.download_fixture), self.assertRaises(self.mod.Refused):
            self.mod.fetch_release(self.work)
        self.assertFalse((self.work/'fca-0.6.0-test.1').exists())

    def test_builder_refuses_tampered_release(self):
        with self.archive.open('ab') as target: target.write(b'bad')
        with self.assertRaises(ValueError): generate(self.archive,self.pub,'0.6.0-test.1',self.root/'other')

    def test_only_official_https_download_hosts(self):
        for url in ('http://github.com/a','https://evil.test/x','https://github.com.evil.test/x','https://user@github.com/x','https://github.com:444/x'):
            with self.subTest(url=url), self.assertRaises(self.mod.Refused): self.mod.checked_url(url)
        self.mod.checked_url('https://release-assets.githubusercontent.com/x')

    def test_private_release_fails_without_requesting_credentials(self):
        client=types.SimpleNamespace(open=lambda *a,**k: (_ for _ in ()).throw(HTTPError(a[0],404,'private',{},None)))
        with patch.object(self.mod,'build_opener',return_value=client), self.assertRaisesRegex(self.mod.Refused,'anonym nicht verfügbar'):
            self.mod.download('https://github.com/a',self.work/'missing',128)

    def test_unsafe_tar_members_rejected_before_any_extraction(self):
        for name,kind in (('fca-0.6.0-test.1/../../escape',tarfile.REGTYPE),('/escape',tarfile.REGTYPE),('fca-0.6.0-test.1/link',tarfile.SYMTYPE),('fca-0.6.0-test.1/hard',tarfile.LNKTYPE),('fca-0.6.0-test.1/device',tarfile.CHRTYPE)):
            with self.subTest(name=name):
                archive=self.root/'unsafe.tar.gz'
                with tarfile.open(archive,'w:gz') as target:
                    member=tarfile.TarInfo(name);member.type=kind;member.linkname='/etc/shadow';target.addfile(member)
                with self.assertRaises(self.mod.Refused): self.mod.unpack(archive,self.work)
        self.assertEqual(list(self.work.iterdir()),[])

    def test_duplicate_tar_members_rejected(self):
        archive=self.root/'duplicate.tar.gz'
        with tarfile.open(archive,'w:gz') as target:
            for _ in range(2): target.addfile(tarfile.TarInfo('fca-0.6.0-test.1/same'))
        with self.assertRaises(self.mod.Refused): self.mod.unpack(archive,self.work)


class GuidedStorageTests(unittest.TestCase):
    def test_directory_storage_is_explicit_and_bound_to_filesystem(self):
        with tempfile.TemporaryDirectory() as temporary:
            config={'evidence_root':str(Path(temporary).resolve()),'storage_mode':'directory','storage_filesystem_uuid':'test-filesystem-123'}
            with patch.object(manager,'run',return_value=b'test-filesystem-123\n'):
                self.assertTrue(manager.storage_present(config))
            with patch.object(manager,'run',return_value=b'wrong-filesystem-456\n'):
                self.assertFalse(manager.storage_present(config))

    def test_wireguard_never_accepts_system_directory(self):
        config=json.loads(Path('infrastructure/installer/answers.example.json').read_text())
        config.update(storage_mode='directory', storage_filesystem_uuid='test-filesystem-123')
        with self.assertRaises(Refused): manager.validate_config(config)

    def test_existing_tls_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);(folder/'ca.key').write_text('preserve')
            with patch.object(guided,'canonical',return_value=folder), self.assertRaises(Refused): guided.create_lab_tls({'server_name':'10.0.2.15'})
            self.assertEqual((folder/'ca.key').read_text(),'preserve')

    def test_guided_sources_have_no_disk_format_or_partition_command(self):
        source=Path('infrastructure/installer/guided.py').read_text()
        for command in ('mkfs','wipefs','sfdisk','parted','fdisk'):
            self.assertNotIn(command,source)


if __name__=='__main__': unittest.main()
