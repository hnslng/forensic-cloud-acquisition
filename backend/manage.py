"""Offline bootstrap; no password arguments or credential output."""
from pathlib import Path
from backend.db import connect, audit
from backend.identity import hash_password


def main():
    password = Path('/run/secrets/initial_admin_password').read_text().strip()
    if len(password) < 14:
        raise SystemExit('Initiales Passwort zu kurz.')
    with connect() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(10501)')
        if conn.execute("SELECT id FROM users WHERE role='admin'").fetchone():
            raise SystemExit('Administrator existiert bereits; kein Überschreiben.')
        user = conn.execute("INSERT INTO users(username,initials,password_hash,role) VALUES ('admin','HNL',%s,'admin') RETURNING id,initials", (hash_password(password),)).fetchone()
        audit(conn, user, 'administrator_bootstrapped')
    print('Initialer Administrator angelegt. Passwort bleibt in externer Secret-Datei.')


if __name__ == '__main__':
    main()
