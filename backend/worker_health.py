"""No credentials in health output; coordinator owns a session advisory lock."""
from backend.db import connect

def main():
    with connect() as conn:
        ready=conn.execute("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND classid=0 AND objid=47203106 AND granted) AS ok").fetchone()['ok']
        if not ready: raise SystemExit(1)

if __name__=='__main__':main()
