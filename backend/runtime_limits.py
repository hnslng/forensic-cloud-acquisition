"""Administrator installation ceilings; laboratory defaults remain 4/2."""
import os

def ceilings():
    files=int(os.environ.get('FCA_MAX_FILE_PARALLELISM','4'))
    accounts=int(os.environ.get('FCA_MAX_ACCOUNT_PARALLELISM','2'))
    if not 1<=files<=16 or not 1<=accounts<=8 or files*accounts>32:
        raise ValueError('Ungültiges FCA-Ressourcenprofil (höchstens 16 Dateien / 8 Konten und 32 Übertragungsplätze insgesamt).')
    return {'file_parallelism':files,'account_parallelism':accounts}
