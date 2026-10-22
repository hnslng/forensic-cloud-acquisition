"""Synthetic preservation witnesses in a disposable installer VM only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from infrastructure.installer.manager import compose, sql, cfg, backup

def witnesses(database='fca'):
    tables=sql("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;", database).splitlines()
    return {t:sql('SELECT md5(coalesce(string_agg(row_to_json(t)::text, chr(10) ORDER BY row_to_json(t)::text), chr(10))) FROM '+t+' t;',database) for t in tables}

assert Path('/root/FCA_INSTALLER_DISPOSABLE_GUEST').is_file()
path = Path('/srv/fca/evidence/FCA-Sicherungen/preservation.bin')
if sys.argv[1] == 'seed':
    path.write_bytes(b'FCA synthetic evidence\x00\xff' * 1024)
    compose('exec', '-T', 'api', 'python', '-', data=b'''
from backend.db import connect
from backend.identity import hash_password
from backend import evidence, oauth
with connect() as conn:
    admin=conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()['id']
    user=conn.execute("INSERT INTO users(username,initials,password_hash,role) VALUES ('synthetic_operator','TEST',%s,'operator') RETURNING id", (hash_password('synthetic-only-password-123'),)).fetchone()['id']
    case=conn.execute("INSERT INTO cases(business_number,name,created_by,operator_initials) VALUES ('INSTALL-TEST','synthetic',%s,'TEST') RETURNING *",(admin,)).fetchone()
    conn.execute("INSERT INTO case_members(case_id,user_id,access) VALUES (%s,%s,'viewer')",(case['id'],user))
    account=conn.execute("INSERT INTO cloud_accounts(case_id,provider,label,created_by) VALUES (%s,'google','synthetic-disconnected',%s) RETURNING *",(case['id'],admin)).fetchone()
    account_dir=evidence.ensure_account(conn,case,account,'drive')
    evidence.directory(account_dir+'/synthetic-paused-run')
    conn.execute("INSERT INTO acquisitions(case_id,account_id,category,requested_by,operator_initials,status,directory,reason) VALUES (%s,%s,'drive',%s,'TEST','paused',%s,'Manuell pausiert')",(case['id'],account['id'],admin,account_dir+'/synthetic-paused-run'))
    oauth.save(case['id'],account['id'],{'synthetic_preservation':'no real credentials'})
    conn.execute("INSERT INTO audit_events(actor_id,operator_initials,case_id,event_type) VALUES (%s,'TEST',%s,'installer_synthetic_test')",(admin,case['id']))
''')
    sql("CREATE TABLE installer_preservation (value text NOT NULL); INSERT INTO installer_preservation VALUES ('synthetic-preserved');")
    Path('/root/evidence-hash').write_text(hashlib.sha256(path.read_bytes()).hexdigest())
    Path('/root/table-witnesses').write_text(json.dumps(witnesses()))
    auth=Path('/var/lib/fca/cloud-auth')
    Path('/root/vault-witnesses').write_text(json.dumps({str(p.relative_to(auth)):hashlib.sha256(p.read_bytes()).hexdigest() for p in auth.rglob('*') if p.is_file()}))
elif sys.argv[1] == 'check':
    assert witnesses() == json.loads(Path('/root/table-witnesses').read_text())
    auth=Path('/var/lib/fca/cloud-auth')
    assert {str(p.relative_to(auth)):hashlib.sha256(p.read_bytes()).hexdigest() for p in auth.rglob('*') if p.is_file()} == json.loads(Path('/root/vault-witnesses').read_text())
    compose('exec', '-T', 'api', 'python', '-', data=b'''
from backend.db import connect
from backend import oauth
with connect() as conn:
    account=conn.execute("SELECT case_id,id FROM cloud_accounts WHERE label='synthetic-disconnected'").fetchone()
    assert oauth.load(account['case_id'],account['id']) == {'synthetic_preservation':'no real credentials'}
''')
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
        assert witnesses('installer_restore_probe') == json.loads(Path('/root/table-witnesses').read_text())
    finally:
        compose('exec', '-T', 'database', 'dropdb', '-U', 'fca_bootstrap', 'installer_restore_probe')
    with tarfile.open(target / 'state.tar') as archive:
        data = archive.extractfile('evidence/FCA-Sicherungen/preservation.bin').read()
        assert hashlib.sha256(data).hexdigest() == Path('/root/evidence-hash').read_text()
        assert archive.extractfile('config/secrets/cloud_master_key').read() == Path('/etc/fca/secrets/cloud_master_key').read_bytes()
print('Synthetic preservation: PASS')
