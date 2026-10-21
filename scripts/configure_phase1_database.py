#!/usr/bin/env python3
"""Run with sudo in the FCA VM; secrets never appear in process arguments."""
import os
from pathlib import Path
import secrets
import subprocess

ROOT = Path('/etc/fca/secrets')
COMPOSE = ['docker', 'compose', '--env-file', '/etc/fca/compose.env']


def sql(statement):
    return subprocess.check_output(COMPOSE + ['exec', '-T', 'database', 'psql', '-v', 'ON_ERROR_STOP=1', '-At', '-U', 'fca_bootstrap', '-d', 'fca'], input=statement.encode()).decode()


def main():
    assert os.geteuid() == 0
    os.chdir(os.environ.get('FCA_PROJECT_ROOT', '/opt/fca'))
    for name in ('api', 'migrate'):
        path = ROOT / (name + '_password')
        role = 'fca_' + name
        exists = sql(f"SELECT 1 FROM pg_roles WHERE rolname='{role}';").strip() == '1'
        if exists:
            assert path.exists(), 'Existing role without matching external secret; manual recovery required'
            continue
        password = secrets.token_hex(32)
        with path.open('x') as handle:
            handle.write(password + '\n')
        os.chown(path, 0, 10001); path.chmod(0o640)
        sql(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '{password}';")
    sql('REVOKE CREATE ON SCHEMA public FROM PUBLIC; GRANT USAGE ON SCHEMA public TO fca_api,fca_migrate; GRANT CREATE ON SCHEMA public TO fca_migrate; ALTER TABLE schema_migrations OWNER TO fca_migrate;')
    if sql('SELECT max(version) FROM schema_migrations;').strip() == '1':
        sql('SET ROLE fca_migrate;\n' + Path('migrations/0002_identity_cases.sql').read_text())
    if sql('SELECT max(version) FROM schema_migrations;').strip() == '2':
        sql('SET ROLE fca_migrate;\n' + Path('migrations/0003_revoke_case_members.sql').read_text())
    initial = ROOT / 'initial_admin_password'
    if not initial.exists() and sql("SELECT count(*) FROM users WHERE role='admin';").strip() == '0':
        with initial.open('x') as handle:
            handle.write(secrets.token_urlsafe(24) + '\n')
        os.chown(initial, 0, 10001); initial.chmod(0o640)
    print('Database roles and phase 1 migration configured; no credentials printed.')


if __name__ == '__main__':
    main()
