"""Idempotent additive directory initialization after migration; no existing row edits."""
from backend.db import connect
from backend import acquisitions,evidence

def main():
    with connect() as conn:
        cases=conn.execute('SELECT * FROM cases ORDER BY created_at,id').fetchall()
    for case in cases:
        with connect() as conn:
            evidence.ensure_case(conn,case)
            accounts=conn.execute('SELECT * FROM cloud_accounts WHERE case_id=%s ORDER BY created_at,id',(case['id'],)).fetchall()
            for account in accounts:
                for category in acquisitions.CATEGORIES[account['provider']]:evidence.ensure_account(conn,case,account,category)
    print('Fall- und Kontoordner initialisiert; bestehende Falldaten unverändert.')

if __name__=='__main__':main()
