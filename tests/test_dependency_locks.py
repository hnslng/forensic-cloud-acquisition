"""Prevent version-lock/hash-lock drift in release builds; no network needed."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RuntimeDependencyLocks(unittest.TestCase):
    def test_hash_lock_tracks_exact_runtime_versions(self):
        versions = [line for line in (ROOT/'backend/requirements.lock').read_text().splitlines() if line and not line.startswith('#')]
        locked = re.findall(r'^([A-Za-z0-9_.-]+==[0-9.]+) \\$', (ROOT/'backend/requirements.hashes').read_text(), re.MULTILINE)
        self.assertEqual(locked, versions)

    def test_each_dependency_has_only_complete_sha256_hashes(self):
        content = (ROOT/'backend/requirements.hashes').read_text()
        blocks = re.split(r'\n\s*\n', '\n'.join(line for line in content.splitlines() if not line.startswith('#')))
        for block in blocks:
            if not block.strip():
                continue
            lines = block.splitlines()
            self.assertGreater(len(lines), 1)
            for line in lines[1:]:
                self.assertRegex(line, r'^    --hash=sha256:[0-9a-f]{64}( \\)?$')


if __name__ == '__main__':
    unittest.main()
