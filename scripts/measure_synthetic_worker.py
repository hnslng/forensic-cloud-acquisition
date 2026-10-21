#!/usr/bin/env python3
"""Bounded synthetic Rclone soak. No cloud, database, existing cases or downloads.

Run in a separate limited container. Local streaming copies are intentionally
bandwidth-limited; measured throughput is NOT a provider/network prediction.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
from unittest.mock import patch
from uuid import UUID

from backend import evidence
from providers.acquisition import AppleDownload
from providers.apple.adapter import AccountContext


def observation():
    value={}
    base=Path('/sys/fs/cgroup')
    for name in ('memory.current','memory.peak'):
        if (base/name).exists():value[name]=int((base/name).read_text())
    for name in ('cpu.stat','memory.events'):
        if (base/name).exists():value[name]={k:int(v) for k,v in (line.split() for line in (base/name).read_text().splitlines())}
    return value


def measure(seconds,accounts,transfers,binary):
    samples=[];completed=0;total=0
    payload=bytes(range(256))*4096;checksum=hashlib.sha256(payload).hexdigest()
    popen=subprocess.Popen
    def runtime(args,*a,**kw):return popen(args+['--bwlimit','8M','--disable','Copy'],*a,**kw)
    with tempfile.TemporaryDirectory(prefix='fca-synthetic-soak-') as directory,ExitStack() as stack:
        root=Path(directory).resolve();root.chmod(0o700)
        source=root/'source';source.mkdir();(source/'synthetic.bin').write_bytes(payload)
        sessions=[]
        stack.enter_context(patch('providers.apple.adapter.subprocess.Popen',runtime))
        stack.enter_context(patch.object(evidence,'space',lambda *_:None))
        for index in range(accounts):
            config=root/str(index);config.mkdir(mode=0o700)
            session=stack.enter_context(AppleDownload(config/'rclone.conf','SYNTHETIC-SOAK-ONLY-'+('x'*48),AccountContext(UUID(int=1),UUID(int=index+2)),binary=binary))
            session._rpc('config/create',{'name':session.remote,'type':'alias','parameters':{'remote':str(source)},'opt':{'nonInteractive':True}})
            sessions.append(session)
        before=sessions[0]._rpc('operations/stat',{'fs':str(source),'remote':'synthetic.bin'})['item']
        start=time.monotonic();samples.append({'elapsed':0,'resources':observation()})
        def copy(pair):
            index,slot=pair;target=root/(str(index)+'-'+str(slot)+'.part')
            sessions[index]._copy_from(str(source),'synthetic.bin',{'metadata':dict(before)},target,0,lambda _:None)
            assert hashlib.sha256(target.read_bytes()).hexdigest()==checksum
            target.unlink() # Only this temporary synthetic output; force actual copy next batch.
            return len(payload)
        with ThreadPoolExecutor(max_workers=accounts*transfers) as pool:
            while time.monotonic()-start<seconds:
                results=list(pool.map(copy,[(a,f) for a in range(accounts) for f in range(transfers)]))
                total+=sum(results);completed+=len(results)
                samples.append({'elapsed':round(time.monotonic()-start,3),'resources':observation()})
        elapsed=time.monotonic()-start
    return {'synthetic_only':True,'scope':'local streamed aliases, artificial 8MiB/s per process cap; no cloud/FCA queue',
            'accounts':accounts,'transfers_per_account':transfers,'seconds':round(elapsed,3),
            'completed_files':completed,'verified_sha256_files':completed,'bytes':total,
            'mib_per_second':round(total/elapsed/1024**2,2),'samples':samples}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seconds',type=int,default=60);p.add_argument('--accounts',type=int,choices=(1,2),default=2)
    p.add_argument('--transfers',type=int,choices=(1,2,4),default=4);p.add_argument('--rclone',default='/usr/local/bin/rclone')
    args=p.parse_args()
    if not 10<=args.seconds<=300:p.error('10–300 Sekunden verwenden.')
    print(json.dumps(measure(args.seconds,args.accounts,args.transfers,args.rclone),indent=2))


if __name__=='__main__':main()
