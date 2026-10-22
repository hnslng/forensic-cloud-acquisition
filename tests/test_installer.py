"""Installer trust boundary and lifecycle safety contracts, no host mutation."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tarfile
import unittest
from unittest.mock import patch

from infrastructure.installer.package import Refused, safe_relative, sha256, verify, verify_exact, write_manifest
from infrastructure.installer import manager
from scripts.build_install_package import export_archive


class SignedPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.package = self.root / 'package'
        self.package.mkdir()
        self.private = self.root / 'signing.key'
        self.public = self.root / 'trusted.pub'
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'ED25519', '-out', str(self.private)], check=True, capture_output=True)
        subprocess.run(['openssl', 'pkey', '-in', str(self.private), '-pubout', '-out', str(self.public)], check=True, capture_output=True)
        for name in ('images.tar', 'compose.template.json', 'scripts/configure_phase1_database.py', 'frontend/index.html', 'frontend/app.js', 'frontend/styles.css', 'migrations/0001_bootstrap.sql'):
            path = self.package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('synthetic fixture')
        self.sign()

    def sign(self):
        write_manifest(self.package, '0.6.0-test.1', 'sha256:' + 'a'*64, 'sha256:' + 'b'*64, [], 'c'*40)
        subprocess.run(['openssl', 'pkeyutl', '-sign', '-inkey', str(self.private), '-rawin', '-in', str(self.package/'manifest.json'), '-out', str(self.package/'manifest.sig')], check=True, capture_output=True)

    def test_signed_package_validates_all_bytes(self):
        self.assertEqual(verify(self.package, self.public)['version'], '0.6.0-test.1')

    def test_valid_but_exchanged_package_is_not_the_approved_package(self):
        expected = verify(self.package, self.public)
        (self.package/'images.tar').write_text('different signed content')
        self.sign()
        with self.assertRaises(Refused): verify_exact(self.package, self.public, expected)

    def test_outer_archive_can_be_verified_before_executing_package_code(self):
        archive = self.root/'fca-0.6.0-test.1.tar.gz'
        export_archive(self.package, archive, '0.6.0-test.1', self.private)
        checksum = Path(str(archive)+'.sha256')
        command = ['openssl','pkeyutl','-verify','-pubin','-inkey',str(self.public),'-rawin','-in',str(checksum),'-sigfile',str(checksum)+'.sig']
        self.assertEqual(subprocess.run(command,capture_output=True).returncode,0)
        self.assertEqual(checksum.read_text().split()[0], sha256(archive))
        with tarfile.open(archive,'r:gz') as payload:
            self.assertTrue(all(m.name.startswith('fca-0.6.0-test.1') and not m.issym() and not m.islnk() for m in payload))
            self.assertEqual(payload.extractfile('fca-0.6.0-test.1/images.tar').read(),b'synthetic fixture')
        with archive.open('ab') as handle:
            handle.write(b'corruption')
        self.assertNotEqual(checksum.read_text().split()[0], sha256(archive))
        checksum.write_text('0'*64+'  '+archive.name+'\n')
        self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)

    def test_tampered_payload_never_installs(self):
        (self.package/'images.tar').write_text('wrong bytes')
        with self.assertRaises(Refused): verify(self.package, self.public)

    def test_unsigned_manifest_change_rejected(self):
        (self.package/'manifest.json').write_text('{}')
        with self.assertRaises(Refused): verify(self.package, self.public)

    def test_untracked_executable_rejected(self):
        (self.package/'run-me.sh').write_text('bad')
        with self.assertRaises(Refused): verify(self.package, self.public)

    def test_missing_file_rejected(self):
        (self.package/'images.tar').unlink()
        with self.assertRaises(Refused): verify(self.package, self.public)

    def test_link_rejected_even_when_target_hash_matches(self):
        path = self.package/'images.tar'
        original = self.root/'image'
        path.rename(original)
        path.symlink_to(original)
        with self.assertRaises(Refused): verify(self.package, self.public)

    def test_bundled_trust_anchor_rejected(self):
        inside = self.package/'trusted.pub'
        shutil.copy(self.public, inside)
        self.sign()
        with self.assertRaises(Refused): verify(self.package, inside)

    def test_debian_version_characters_are_safe_but_traversal_is_not(self):
        self.assertEqual(str(safe_relative('debs/openssl_3.5.7-1~deb13u2_amd64.deb')), 'debs/openssl_3.5.7-1~deb13u2_amd64.deb')
        safe_relative('debs/docker.io_26.1.5+dfsg1-9+deb13u1_amd64.deb')
        for name in ('/etc/passwd','debs/../../etc/passwd','debs/a;touch','debs/./file'):
            with self.assertRaises(Refused): safe_relative(name)

    def test_wrong_key_rejected(self):
        other = self.root/'other.key'
        subprocess.run(['openssl','genpkey','-algorithm','ED25519','-out',str(other)], check=True, capture_output=True)
        subprocess.run(['openssl','pkey','-in',str(other),'-pubout','-out',str(self.public)], check=True, capture_output=True)
        with self.assertRaises(Refused): verify(self.package, self.public)


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        patcher = patch('infrastructure.installer.manager.canonical', side_effect=lambda p: Path(p))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.value = dict(mode='labor', profile='labor', server_name='10.0.1.5', listen_address='10.0.1.5', allowed_networks=['10.0.1.0/24'], evidence_root='/srv/fca/evidence', backup_root='/var/backups/fca', certificate='/etc/fca/tls/cert.pem', certificate_key='/etc/fca/tls/key.pem', ca_certificate='/etc/fca/tls/ca.pem')

    def test_laboratory_ip_and_wireguard_name(self):
        manager.validate_config(self.value)
        self.value.update(mode='wireguard', server_name='fca.internal.example')
        manager.validate_config(self.value)

    def test_public_listener_denied(self):
        for value in ('0.0.0.0', '8.8.8.8', '127.0.0.1', '224.0.0.1'):
            self.value['listen_address'] = value
            with self.subTest(value=value), self.assertRaises((Refused, ValueError)): manager.validate_config(self.value)

    def test_anywhere_allowlist_denied(self):
        self.value['allowed_networks'] = ['0.0.0.0/0']
        with self.assertRaises(Refused): manager.validate_config(self.value)

    def test_config_injection_denied(self):
        for key, value in [('server_name', 'fca.test; evil'), ('certificate', '/x;evil'), ('evidence_root', '/srv/../etc/fca')]:
            invalid = dict(self.value, **{key: value})
            with self.subTest(key=key), self.assertRaises((Refused, ValueError)): manager.validate_config(invalid)

    def test_evidence_never_inside_system_paths_or_backup(self):
        for path in ('/etc/fca', '/var/lib/fca', '/srv/fca/evidence/sub'):
            self.value['evidence_root'] = path
            if path.startswith('/srv'):
                self.value['backup_root'] = '/srv/fca/evidence'
            with self.assertRaises(Refused): manager.validate_config(self.value)

    def test_no_ip_origin_in_wireguard_mode(self):
        self.value['mode'] = 'wireguard'
        with self.assertRaises(Refused): manager.validate_config(self.value)

    def test_nginx_keeps_private_binding_acl_and_no_query_logs(self):
        text = manager.nginx(self.value)
        self.assertIn('listen 10.0.1.5:443 ssl;', text)
        self.assertIn('allow 10.0.1.0/24;', text)
        self.assertIn('deny all;', text)
        self.assertIn('access_log off;', text)
        self.assertNotIn('listen 0.0.0.0', text)
        self.assertNotIn('listen 80', text)


class StorageTests(unittest.TestCase):
    def test_explicit_permissions_survive_restrictive_umask(self):
        with tempfile.TemporaryDirectory() as root:
            old = os.umask(0o077)
            try:
                for mode in (0o600,0o640,0o644,0o755):
                    path=Path(root).resolve()/str(mode)
                    manager.write(path,'synthetic',mode)
                    self.assertEqual(path.stat().st_mode & 0o777, mode)
            finally:
                os.umask(old)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name).resolve()
        self.config = {'evidence_root': str(self.path)}

    def test_missing_mount_never_creates_marker(self):
        with patch('os.path.ismount', return_value=False), self.assertRaises(Refused):
            manager.mounted_evidence(self.config, initialize=True)
        self.assertFalse((self.path/'.fca-volume-id').exists())

    def test_existing_unmarked_data_never_adopted(self):
        (self.path/'evidence').write_text('preserve')
        with patch('os.path.ismount', return_value=True), self.assertRaises(Refused):
            manager.mounted_evidence(self.config, initialize=True)
        self.assertEqual((self.path/'evidence').read_text(), 'preserve')

    def test_new_mount_gets_stable_id_repeatedly(self):
        self.config['volume_id'] = 'synthetic-id'
        with patch('os.path.ismount', return_value=True):
            self.assertEqual(manager.mounted_evidence(self.config, initialize=True), 'synthetic-id')
            self.assertEqual(manager.mounted_evidence(self.config), 'synthetic-id')

    def test_wrong_volume_denied(self):
        (self.path/'.fca-volume-id').write_text('another-volume')
        self.config['volume_id'] = 'expected'
        with patch('os.path.ismount', return_value=True), self.assertRaises(Refused):
            manager.mounted_evidence(self.config)

    def test_lost_found_does_not_make_fresh_ext4_unusable(self):
        (self.path/'lost+found').mkdir()
        self.assertTrue(manager.empty_volume(self.path))
        (self.path/'lost+found'/'recovered').write_text('preserve')
        self.assertFalse(manager.empty_volume(self.path))


class ServiceDiagnosisTests(unittest.TestCase):
    def test_remote_docker_context_cannot_redirect_maintenance(self):
        with patch.dict(os.environ, {'DOCKER_HOST':'tcp://other-server:2376','DOCKER_CONTEXT':'remote','DOCKER_TLS_VERIFY':'1','DOCKER_CERT_PATH':'/private/remote'}):
            manager.force_local_docker()
            self.assertEqual(os.environ['DOCKER_HOST'],'unix:///var/run/docker.sock')
            self.assertTrue(all(v not in os.environ for v in ('DOCKER_CONTEXT','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH')))

    def test_release_order_does_not_silently_downgrade(self):
        values = ['0.6.0-test.2','0.6.0-test.10','0.6.0','0.6.1','1.0.0']
        self.assertEqual(sorted(reversed(values), key=manager.version_key), values)

    def test_compose_array_and_json_lines_are_supported(self):
        rows = [{'Service':s,'State':'running','Health':'healthy'} for s in ('api','worker','database')]
        for raw in (json.dumps(rows), '\n'.join(json.dumps(r) for r in rows)):
            with self.subTest(raw=raw), patch.object(manager,'run'), patch.object(manager,'compose',return_value=raw.encode()):
                self.assertTrue(manager._services())

    def test_missing_worker_is_not_healthy(self):
        rows = [{'Service':s,'State':'running','Health':'healthy'} for s in ('api','database')]
        with patch.object(manager,'run'), patch.object(manager,'compose',return_value=json.dumps(rows).encode()):
            self.assertFalse(manager._services())

    def test_unhealthy_worker_is_not_healthy(self):
        rows = [{'Service':s,'State':'running','Health':('unhealthy' if s=='worker' else 'healthy')} for s in ('api','worker','database')]
        with patch.object(manager,'run'), patch.object(manager,'compose',return_value=json.dumps(rows).encode()):
            self.assertFalse(manager._services())


if __name__ == '__main__':
    unittest.main()
