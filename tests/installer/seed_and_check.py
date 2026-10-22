"""Synthetic preservation witnesses in a disposable installer VM only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from infrastructure.installer.manager import compose, sql, cfg, backup

assert Path('/root/FCA_INSTALLER_DISPOSABLE_GUEST').is_file()
path = Path('/srv/fca/evidence/FCA-Sicherungen/preservation.bin')
if sys.argv[1] == 'seed':
    path.write_bytes(b'FCA synthetic evidence\x00\xff' * 1024)
    sql("CREATE TABLE installer_preservation (value text NOT NULL); INSERT INTO installer_preservation VALUES ('synthetic-preserved');")
    Path('/root/evidence-hash').write_text(hashlib.sha256(path.read_bytes()).hexdigest())
elif sys.argv[1] == 'check':
    assert sql('SELECT value FROM installer_preservation;') == 'synthetic-preserved'
    assert sql("SELECT count(*) FROM users WHERE username='admin';") == '1'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == Path('/root/evidence-hash').read_text()
elif sys.argv[1] == 'restore-check':
    target = sorted(Path('/var/backups/fca').glob('backup-*'))[-1]
    record = json.loads((target / 'backup.json').read_text())
    assert record['status'] == 'restore_probe_passed'
    for name, digest in record['files'].items():
        assert hashlib.sha256((target / name).read_bytes()).hexdigest() == digest
    compose('exec', '-T', 'database', 'createdb', '-U', 'fca_bootstrap', 'installer_restore_probe')
    try:
        with (target / 'database.dump').open('rb') as handle:
            subprocess.run(['docker', 'compose', '--env-file', '/etc/fca/compose.env', '-f', '/etc/fca/compose.json', 'exec', '-T', 'database', 'pg_restore', '--exit-on-error', '--no-owner', '-U', 'fca_bootstrap', '-d', 'installer_restore_probe'], stdin=handle, check=True)
        assert sql('SELECT value FROM installer_preservation;', 'installer_restore_probe') == 'synthetic-preserved'
    finally:
        compose('exec', '-T', 'database', 'dropdb', '-U', 'fca_bootstrap', 'installer_restore_probe')
    with tarfile.open(target / 'state.tar') as archive:
        data = archive.extractfile('evidence/FCA-Sicherungen/preservation.bin').read()
        assert hashlib.sha256(data).hexdigest() == Path('/root/evidence-hash').read_text()
        assert archive.extractfile('config/secrets/cloud_master_key').read() == Path('/etc/fca/secrets/cloud_master_key').read_bytes()
print('Synthetic preservation: PASS')
