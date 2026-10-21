"""Canonical private evidence tree. IDs prevent collisions after path normalization."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import unicodedata

class StorageError(RuntimeError): pass

def root():
    path = Path(os.environ.get('FCA_EVIDENCE_ROOT', '/evidence')).absolute()
    if path.resolve() != path or not (path / '.fca-volume-id').is_file():
        raise StorageError('Sicherungsdatenträger ist nicht eingebunden.')
    return path

def component(name):
    text = unicodedata.normalize('NFC', str(name))
    text = re.sub(r'[^\w. -]', '-', text, flags=re.UNICODE).strip(' .-')[:80]
    return text or 'Ohne-Bezeichnung'

def directory(relative):
    base = root()
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or any(p in ('.', '..') for p in parts):
        raise StorageError('Ungültiger Sicherungspfad.')
    path = base
    for part in parts:
        path = path / part
        path.mkdir(mode=0o700, exist_ok=True)
        if path.is_symlink() or path.resolve() != path or not path.is_dir():
            raise StorageError('Unsicherer Sicherungspfad.')
    return path

def file_path(base, relative):
    parts = relative.split('/')
    if any(p in ('', '.', '..') or '\\' in p or ':' in p or any(ord(c)<32 for c in p) for p in parts):
        raise StorageError('Ungültiger Dateipfad.')
    path = Path(base)
    for part in parts[:-1]:
        path = path / part
        path.mkdir(mode=0o700, exist_ok=True)
        if path.is_symlink() or path.resolve() != path: raise StorageError('Unsicherer Dateipfad.')
    result = path / parts[-1]
    if result.is_symlink() or (result.exists() and not result.is_file()): raise StorageError('Unsichere Zieldatei.')
    return result

def source_name(name, identifier):
    # Stable IDs distinguish duplicate names and portable/case-insensitive collisions.
    value = component(name)
    suffix = hashlib.sha256(str(identifier).encode()).hexdigest()[:16]
    stem, extension = os.path.splitext(value)
    return stem + '__' + suffix + extension

def ensure_case(conn, case):
    relative = 'FCA-Sicherungen/' + component(case['business_number']) + '__' + str(case['id'])
    row = conn.execute('INSERT INTO evidence_cases(case_id,directory) VALUES (%s,%s) ON CONFLICT(case_id) DO UPDATE SET case_id=excluded.case_id RETURNING directory', (case['id'], relative)).fetchone()
    directory(row['directory'])
    return row['directory']

def ensure_account(conn, case, account, category):
    prefix = {('apple','drive'):'iCloud', ('apple','photos'):'iCloud_Fotos',
              ('google','drive'):'Google_Drive', ('google','calendar'):'Google_Kalender',
              ('microsoft','drive'):'OneDrive', ('microsoft','calendar'):'Outlook_Kalender'}[(account['provider'],category)]
    # Serialize allocation per case. This also protects simultaneous account additions.
    conn.execute('SELECT id FROM cases WHERE id=%s FOR UPDATE', (case['id'],))
    case_directory = ensure_case(conn, case)
    existing = conn.execute('SELECT directory FROM evidence_accounts WHERE account_id=%s AND category=%s', (account['id'], category)).fetchone()
    if existing: return case_directory + '/' + existing['directory']
    used = {r['directory'] for r in conn.execute('SELECT directory FROM evidence_accounts WHERE case_id=%s', (case['id'],))}
    number = 1
    while prefix + '_' + str(number) in used: number += 1
    name = prefix + '_' + str(number)
    conn.execute('INSERT INTO evidence_accounts(account_id,category,case_id,directory) VALUES (%s,%s,%s,%s)', (account['id'],category,case['id'],name))
    directory(case_directory + '/' + name)
    return case_directory + '/' + name

def sha256(path):
    value = hashlib.sha256()
    with open(path, 'rb') as handle:
        while chunk := handle.read(1024*1024): value.update(chunk)
    return value.hexdigest()

def space(reserve, needed=0):
    if shutil.disk_usage(root()).free - max(0, needed) < reserve:
        raise StorageError('Zu wenig freier Speicherplatz. Sicherung pausiert.')

def atomic_json(path, value):
    import json
    temp = path.with_name(path.name + '.tmp')
    if temp.is_symlink(): raise StorageError('Unsichere Berichtsdatei.')
    with open(temp, 'w', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, default=str, indent=2)
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temp, path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)
