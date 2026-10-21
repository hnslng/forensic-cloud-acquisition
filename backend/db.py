import os
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def connect():
    return psycopg.connect(
        host=os.environ.get('FCA_DB_HOST', 'database'),
        port=int(os.environ.get('FCA_DB_PORT', '5432')),
        dbname=os.environ.get('FCA_DB_NAME', 'fca'),
        user=os.environ.get('FCA_DB_USER', 'fca_api'),
        password=Path(os.environ['FCA_DB_PASSWORD_FILE']).read_text().strip(),
        connect_timeout=5, options='-c statement_timeout=10000 -c idle_in_transaction_session_timeout=15000',
        row_factory=dict_row,
    )


def audit(conn, actor, event, case_id=None, initials=None, details=None):
    conn.execute('INSERT INTO audit_events(actor_id,operator_initials,case_id,event_type,details) VALUES (%s,%s,%s,%s,%s)',
                 (actor['id'] if actor else None, initials or (actor['initials'] if actor else None),
                  case_id, event, Jsonb(details or {})))
