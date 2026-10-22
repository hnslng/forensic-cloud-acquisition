"""Short invocation: real checksum boundary, no host/package/network mutations."""
import hashlib
import io
import os
from pathlib import Path
import re
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


def invocation():
    return (ROOT/'releases/START-v1.txt').read_text().split('\n\n',1)[1].strip()


class ShortCommandTests(unittest.TestCase):
    def run_command(self, tamper=False, download_fails=False):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve(); binaries=root/'bin';binaries.mkdir()
            fixture=root/'starter';fixture.write_bytes((ROOT/'start.sh').read_bytes()+(b'\n# tampered\n' if tamper else b''))
            for name,body in {'apt-get':'exit 0', 'wget':('exit 7' if download_fails else 'cp "$FCA_TEST_STARTER" start.sh'), 'bash':'touch "$FCA_TEST_EXEC_MARKER"'}.items():
                path=binaries/name;path.write_text('#!/bin/sh\n'+body+'\n');path.chmod(0o755)
            env=dict(os.environ,PATH=str(binaries)+os.pathsep+os.environ['PATH'],TMPDIR=str(root),FCA_TEST_STARTER=str(fixture),FCA_TEST_EXEC_MARKER=str(root/'executed'))
            result=subprocess.run(['/bin/bash','-c',invocation()],env=env,capture_output=True)
            return result.returncode,(root/'executed').exists()

    def test_exact_documented_command_accepts_verified_starter(self):
        self.assertEqual(self.run_command(),(0,True))

    def test_corrupted_starter_never_executes(self):
        status,executed=self.run_command(tamper=True)
        self.assertNotEqual(status,0);self.assertFalse(executed)

    def test_failed_download_never_executes(self):
        status,executed=self.run_command(download_fails=True)
        self.assertNotEqual(status,0);self.assertFalse(executed)

    def test_readme_and_copy_file_use_the_same_fixed_command(self):
        readme=(ROOT/'README.md').read_text()
        self.assertIn('```sh\n'+invocation()+'\n```',readme)
        digest=hashlib.sha256((ROOT/'start.sh').read_bytes()).hexdigest()
        self.assertIn(digest+'  start.sh',invocation())
        self.assertNotIn('latest',invocation())
        self.assertNotIn('.sha256',invocation())
        self.assertLess(len(invocation()),400)

    def test_starter_pins_existing_verified_release_bootstrap(self):
        source=(ROOT/'start.sh').read_text()
        digest=hashlib.sha256((ROOT/'releases/v0.6.0-rc.1/fca-bootstrap.py').read_bytes()).hexdigest()
        self.assertIn("EXPECTED = '"+digest+"'",source)
        self.assertIn('/releases/download/v0.6.0-rc.1/fca-bootstrap.py',source)
        subprocess.run(['/bin/sh','-n',str(ROOT/'start.sh')],check=True)


class StarterBootstrapBoundaryTests(unittest.TestCase):
    def run_python_stage(self,content):
        code=(ROOT/'start.sh').read_text().split("<<'PY'\n",1)[1].split('\nPY\n',1)[0]
        with tempfile.TemporaryDirectory() as temporary:
            client=types.SimpleNamespace(open=lambda *a,**k:io.BytesIO(content))
            with patch('urllib.request.build_opener',return_value=client),patch('sys.argv',['starter',temporary]):
                namespace={}
                exec(compile(code,'starter-bootstrap-download','exec'),namespace)
            return (Path(temporary)/'bootstrap.py').read_bytes(),namespace

    def test_verified_bootstrap_is_saved(self):
        data=(ROOT/'releases/v0.6.0-rc.1/fca-bootstrap.py').read_bytes()
        saved,_=self.run_python_stage(data)
        self.assertEqual(saved,data)

    def test_tampered_bootstrap_is_not_saved_or_executed(self):
        with self.assertRaisesRegex(SystemExit,'Bootstrap-Prüfsumme ungültig'):
            self.run_python_stage(b'print("malicious")')

    def test_redirect_cannot_downgrade_https_or_change_download_host(self):
        _,namespace=self.run_python_stage((ROOT/'releases/v0.6.0-rc.1/fca-bootstrap.py').read_bytes())
        for target in ('http://github.com/x','https://evil.test/x','https://github.com.evil.test/x','https://user@github.com/x'):
            with self.subTest(target=target),self.assertRaises(SystemExit):
                namespace['HTTPSOnly']().redirect_request(None,None,302,'',{},target)

if __name__=='__main__':unittest.main()
