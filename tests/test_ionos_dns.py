"""Synthetic DNS zone: challenge must never replace unrelated records."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.ionos_dns_challenge import IonosChallenge, ChallengeError, private_file


class ChallengeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        key = root / 'key'
        key.write_text('SYNTHETIC-SECRET')
        key.chmod(0o600)
        self.challenge = IonosChallenge({'host': 'fca.example.org',
            'zone_id': '00000000-0000-0000-0000-000000000001',
            'key_file': str(key), 'state_directory': str(root), 'nameservers': ['ns.example.org']})
        self.token = 'SYNTHETIC-' + 'a' * 40
        self.existing = {'id': '00000000-0000-0000-0000-000000000002',
                         'name': 'existing.example.org', 'type': 'A', 'content': '192.0.2.1'}
        self.records = [self.existing.copy()]
        self.operations = []

    def api(self, method, suffix='', body=None):
        self.operations.append((method, suffix))
        if method == 'GET':
            return {'records': self.records}
        if method == 'POST':
            self.assertEqual(suffix, '/records')
            self.assertEqual(len(body), 1)
            self.assertEqual(body[0]['type'], 'TXT')
            self.assertEqual(body[0]['name'], '_acme-challenge.fca.example.org')
            self.records.append({**body[0], 'id': '00000000-0000-0000-0000-000000000003'})
        elif method == 'DELETE':
            self.records[:] = [r for r in self.records if not suffix.endswith(r['id'])]
        else:
            self.fail('Zone-replacing operation attempted')

    def test_add_verify_cleanup_preserves_all_existing_records(self):
        with patch.object(self.challenge, 'api', side_effect=self.api), patch.object(self.challenge, 'wait'):
            self.challenge.auth(self.token)
            self.challenge.auth(self.token)
            self.assertEqual(len(self.records), 2)
            self.challenge.cleanup(self.token)
            self.challenge.cleanup(self.token)
        self.assertEqual(self.records, [self.existing])
        self.assertEqual(sum(m == 'POST' for m, _ in self.operations), 1)

    def test_existing_matching_txt_is_never_deleted(self):
        self.records.append({'id': '00000000-0000-0000-0000-000000000003',
            'name': '_acme-challenge.fca.example.org', 'type': 'TXT', 'content': self.token})
        with patch.object(self.challenge, 'api', side_effect=self.api), patch.object(self.challenge, 'wait'):
            self.challenge.auth(self.token)
            self.challenge.cleanup(self.token)
        self.assertEqual(len(self.records), 2)
        self.assertFalse(any(m in ('POST', 'DELETE') for m, _ in self.operations))

    def test_changed_record_is_not_deleted(self):
        with patch.object(self.challenge, 'api', side_effect=self.api), patch.object(self.challenge, 'wait'):
            self.challenge.auth(self.token)
            self.records[-1]['content'] = 'CHANGED'
            with self.assertRaises(ChallengeError):
                self.challenge.cleanup(self.token)
        self.assertFalse(any(m == 'DELETE' for m, _ in self.operations))

    def test_private_files_and_symlinks(self):
        p = Path(self.temp.name).resolve() / 'public'
        p.write_text('SYNTHETIC')
        p.chmod(0o644)
        with self.assertRaises(ChallengeError):
            private_file(p)
        p.chmod(0o600)
        link = p.with_name('link')
        link.symlink_to(p)
        with self.assertRaises(ChallengeError):
            private_file(link)

    def test_disallows_zone_replacement_or_untrusted_api_path(self):
        for method, path in [('PUT', ''), ('DELETE', ''), ('POST', ''), ('PUT', '/../../other-zone')]:
            with self.subTest(method=method, path=path), self.assertRaises(ChallengeError):
                self.challenge.api(method, path)


if __name__ == '__main__':
    unittest.main()
