"""Exercise the generated ONE-command installer through a real PTY in QEMU."""
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import time

assert Path('/root/FCA_INSTALLER_DISPOSABLE_GUEST').is_file()
command=Path('/root/bootstrap/INSTALL.txt').read_text().split('\n\n',1)[1].strip()
# Answers are synthetic; no passwords, tokens or real cloud logins.
answers=(['labor','10.0.2.15','10.0.2.15','10.0.2.0/24','/srv/fca/evidence','/var/backups/fca','labor','labor','SYSTEMSPEICHER','ja'] if sys.argv[1] in ('first','install') else ['ja'])
master,slave=pty.openpty()
env=dict(os.environ)
if Path('/root/fixture-ca.pem').exists(): env['SSL_CERT_FILE']='/root/fixture-ca.pem'
if sys.argv[1]=='first': env['PATH']='/root/failing-apt:'+env['PATH']
process=subprocess.Popen(['bash','-c',command],stdin=slave,stdout=slave,stderr=slave,env=env,start_new_session=True)
os.close(slave)
# Send only when a prompt arrives; certificate generation can take a few seconds.
buffer=b''; deadline=time.monotonic()+900
try:
    while time.monotonic()<deadline:
        if select.select([master],[],[],1)[0]:
            try: chunk=os.read(master,65536)
            except OSError: break
            if not chunk: break
            sys.stdout.buffer.write(chunk);sys.stdout.buffer.flush();buffer+=chunk
            if buffer.rstrip().endswith(b':') and answers:
                os.write(master,(answers.pop(0)+'\n').encode());buffer=b''
        elif process.poll() is not None: break
    else:
        process.kill();raise AssertionError('Bootstrap timeout')
finally:
    os.close(master)
status=process.wait(timeout=30)
if sys.argv[1]=='first':
    assert status != 0, 'Injected APT failure must stop the first installation'
    assert Path('/etc/fca/installation.json').is_file()
else:
    assert status == 0, 'Bootstrap repeat/resume failed'
print('BOOTSTRAP_PTY_'+sys.argv[1].upper()+'_PASS')
