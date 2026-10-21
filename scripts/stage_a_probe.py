#!/usr/bin/env python3
"""Isolated feasibility probes: synthetic loopback OAuth and local rclone HTTP copies.

Never connects to cloud accounts, the FCA VM, or PostgreSQL. The only listeners
bind 127.0.0.1. Output contains synthetic aggregate metrics, never OAuth payloads.
This is a test harness, not an investigator sign-in helper or production adapter.
"""
import argparse
import concurrent.futures
import contextlib
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import queue
import re
import resource
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import patch


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        while chunk:=handle.read(256*1024):digest.update(chunk)
    return digest.hexdigest()


class Server(http.server.ThreadingHTTPServer):
    daemon_threads=True
    request_queue_size=64 # avoid the fixture accept backlog becoming an accidental throttle


@contextlib.contextmanager
def serving(handler):
    server=Server(('127.0.0.1',0),handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield server
    finally:server.shutdown();server.server_close();thread.join(3)


def oauth_probe(binary,root):
    received=[];token_requests=[]
    class OAuthMock(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            received.append(query)
            location=query['redirect_uri'][0]+'?'+urllib.parse.urlencode({'code':'SYNTHETIC-CODE','state':query['state'][0]})
            self.send_response(302);self.send_header('Location',location);self.end_headers()
        def do_POST(self):
            body=urllib.parse.parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode())
            token_requests.append(body)
            assert body['code']==['SYNTHETIC-CODE']
            data=json.dumps({'access_token':'SYNTHETIC-ACCESS','refresh_token':'SYNTHETIC-REFRESH','expires_in':3600,'token_type':'Bearer'}).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    with serving(OAuthMock) as server:
        endpoint='http://127.0.0.1:'+str(server.server_port)
        def start(provider):
            env={'PATH':os.defpath,'HOME':str(root),'RCLONE_CONFIG':str(root/'empty.conf'),
                 'RCLONE_'+provider.upper()+'_AUTH_URL':endpoint+'/authorize',
                 'RCLONE_'+provider.upper()+'_TOKEN_URL':endpoint+'/token'}
            if provider=='drive':env['RCLONE_DRIVE_SCOPE']='drive.readonly'
            else:env['RCLONE_ONEDRIVE_ACCESS_SCOPES']='Files.Read offline_access'
            proc=subprocess.Popen([str(binary),'authorize',provider,'synthetic-client','synthetic-secret','--auth-no-open-browser'],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            lines=queue.Queue()
            def consume():
                for line in proc.stdout:lines.put(line)
            threading.Thread(target=consume,daemon=True).start()
            deadline=time.monotonic()+12
            while time.monotonic()<deadline:
                try:line=lines.get(timeout=.1)
                except queue.Empty:
                    if proc.poll() is not None:break
                    continue
                match=re.search(r'http://127\.0\.0\.1:53682/auth\?state=[^\s]+',line)
                if match:return proc,match.group()
            proc.terminate();proc.wait(5)
            raise AssertionError('Synthetic OAuth listener did not start; check fixed port availability')
        result=[]
        for provider in ('drive','onedrive'):
            before=len(token_requests);proc,url=start(provider)
            try:
                # An actual second rclone process cannot bind the same loopback port.
                if provider=='drive':
                    env={'PATH':os.defpath,'HOME':str(root),'RCLONE_CONFIG':str(root/'empty.conf'),'RCLONE_DRIVE_AUTH_URL':endpoint+'/authorize','RCLONE_DRIVE_TOKEN_URL':endpoint+'/token'}
                    second=subprocess.run([str(binary),'authorize','drive','synthetic-client','synthetic-secret','--auth-no-open-browser'],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=8,text=True)
                    assert second.returncode!=0
                with urllib.request.urlopen(url,timeout=10) as response:assert response.status==200
                assert proc.wait(10)==0 and len(token_requests)==before+1
                request=received[-1]
                result.append({'provider':provider,'synthetic_exchange_passed':True,'redirect_uri':request['redirect_uri'][0],
                               'authorization_pkce_present':'code_challenge' in request,'exchange_pkce_present':'code_verifier' in token_requests[-1],
                               'requested_scope':request.get('scope',[''])[0]})
            finally:
                if proc.poll() is None:proc.terminate();proc.wait(5)
        before=len(token_requests);proc,url=start('drive')
        try:
            bad='http://127.0.0.1:53682/?code=SYNTHETIC-CODE&state=WRONG'
            try:urllib.request.urlopen(bad,timeout=5);raise AssertionError('Wrong state accepted')
            except urllib.error.HTTPError as error:assert error.code==400
            assert proc.wait(8)!=0 and len(token_requests)==before
        finally:
            if proc.poll() is None:proc.terminate();proc.wait(5)
    return {'flows':result,'wrong_state_rejected':True,'fixed_port_conflict_observed':True,'real_account_acceptance':False}


def existing_fca_checks(root):
    # Exercise existing FCA OAuth validation/encryption without a DB/cloud login.
    from backend import oauth
    from providers.acquisition import WebProvider,Retryable
    from providers.apple.adapter import ProviderError
    from uuid import UUID
    master=root/'synthetic.key';master.write_text('SYNTHETIC-ONLY-'+'x'*80);master.chmod(0o600)
    auth=root/'auth';auth.mkdir(mode=0o700)
    environment={'FCA_CLOUD_MASTER_KEY_FILE':str(master),'FCA_CLOUD_AUTH_ROOT':str(auth),'FCA_OAUTH_CONFIG_FILE':str(root/'absent')}
    config={'client_id':'synthetic','client_secret':'synthetic','redirect_uri':'https://fca.test/api/oauth/callback'}
    case,account,user=UUID(int=1),UUID(int=2),UUID(int=3)
    with patch.dict(os.environ,environment),patch.object(oauth,'configuration',return_value=config),patch.object(oauth,'available',return_value=True):
        def pending(**overrides):
            value={'user_id':str(user),'state':'s'*48,'expires':time.time()+60,'verifier':'v'*64};value.update(overrides)
            oauth.save(case,account,{'pending':value})
        with patch.object(oauth,'exchange',return_value={'access_token':'SYNTHETIC-TOKEN','refresh_token':'SYNTHETIC-REFRESH','expires_in':3600}) as exchange:
            for actor,other_case,other_account,state,expired in [(UUID(int=4),case,account,'s'*48,False),(user,UUID(int=4),account,'s'*48,False),(user,case,UUID(int=4),'s'*48,False),(user,case,account,'bad',False),(user,case,account,'s'*48,True)]:
                pending(expires=time.time()-1 if expired else time.time()+60)
                try:oauth.complete('google',other_case,other_account,actor,state,'SYNTHETIC');raise AssertionError('Invalid binding accepted')
                except ProviderError:pass
            assert exchange.call_count==0
            pending();assert oauth.complete('google',case,account,user,'s'*48,'SYNTHETIC')['status']=='connected'
            try:oauth.complete('google',case,account,user,'s'*48,'SYNTHETIC');raise AssertionError('Replay accepted')
            except ProviderError:pass
            assert exchange.call_count==1
            vault,_=oauth.vault(case,account);assert b'SYNTHETIC-TOKEN' not in vault.read_bytes()
    provider=WebProvider('microsoft',case,account)
    try:provider.error(urllib.error.HTTPError('https://graph.microsoft.com',429,'',{'Retry-After':'37'},None))
    except Retryable as error:assert error.delay==37 and error.throttled
    try:provider.error(urllib.error.HTTPError('https://graph.microsoft.com',403,'',{},io.BytesIO(b'{"error":{"code":"accessDenied"}}')))
    except Retryable:access_denied_retried=True
    target=root/'provider-hash.bin'
    record={'source_id':'synthetic','metadata':{'eTag':'same','file':{'hashes':{'sha1Hash':'0'*40}}}}
    with patch.object(provider,'request',return_value=io.BytesIO(b'abc')),patch.object(provider,'json',return_value={'eTag':'same'}),patch('backend.evidence.space',return_value=None):
        provider.download(record,target,0,lambda _:None)
    return {'fca_user_case_account_state_expiry_replay_checks_passed':True,'encrypted_token_storage_passed':True,'existing_provider_retry_after_seconds_parsed':37,
            'known_gap_403_accessDenied_retried':access_denied_retried,'known_gap_onedrive_wrong_source_sha1_not_rejected':target.read_bytes()==b'abc'}


def transfer_probe(binary,root,repeats):
    data=root/'http';data.mkdir();fixture={}
    for index,size in enumerate([0,1024,65536,1024*1024,4*1024*1024,8*1024*1024]*3):
        name='synthetic-'+str(index)+'.bin';file=data/name
        block=hashlib.sha256(name.encode()).digest()*8192
        with file.open('wb') as handle:
            remaining=size
            while remaining:part=block[:min(remaining,len(block))];handle.write(part);remaining-=len(part)
        fixture[name]={'size':size,'sha256':sha(file)}
    counters={'active':0,'max_active':0,'responses_429':0,'disconnects':0,'requests':0}
    lock=threading.Lock();faults=False;seen=set()
    class Files(http.server.SimpleHTTPRequestHandler):
        def __init__(self,*a,**kw):super().__init__(*a,directory=str(data),**kw)
        def log_message(self,*args):pass
        def do_GET(self):
            nonlocal faults
            filename=Path(urllib.parse.urlsplit(self.path).path).name
            with lock:
                counters['requests']+=1
                rate=faults and filename=='synthetic-3.bin' and filename not in seen
                cut=faults and filename=='synthetic-4.bin' and filename not in seen
                if rate or cut:seen.add(filename)
            if rate:
                counters['responses_429']+=1;self.send_response(429);self.send_header('Retry-After','1');self.send_header('Content-Length','0');self.end_headers();return
            if cut:
                counters['disconnects']+=1;size=fixture[filename]['size'];self.send_response(200);self.send_header('Content-Length',str(size));self.end_headers()
                self.wfile.write((data/filename).read_bytes()[:65536]);self.wfile.flush();self.connection.shutdown(socket.SHUT_RDWR);self.connection.close();return
            super().do_GET()
        def copyfile(self,source,output):
            with lock:counters['active']+=1;counters['max_active']=max(counters['max_active'],counters['active'])
            try:
                while chunk:=source.read(65536):output.write(chunk);time.sleep(.002)
            except (BrokenPipeError,ConnectionResetError):
                pass # expected when the synthetic interruption probe terminates its client
            finally:
                with lock:counters['active']-=1
    with serving(Files) as server:
        url='http://127.0.0.1:'+str(server.server_port)+'/'
        results=[]
        def one(accounts,parallel,iteration,inject=False):
            nonlocal faults
            faults=inject;seen.clear();counters.update(active=0,max_active=0,responses_429=0,disconnects=0,requests=0)
            destination=root/('run-'+str(accounts)+'-'+str(parallel)+'-'+str(iteration));destination.mkdir()
            baseline=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.monotonic();processes=[];peak_rss=0
            for account in range(accounts):
                target=destination/str(account)
                command=[str(binary),'copy',':http:',str(target),'--http-url',url,'--config',str(root/'empty.conf'),'--transfers',str(parallel),'--checkers','2','--multi-thread-streams','0','--buffer-size','256k','--retries','3','--low-level-retries','3','--retries-sleep','100ms','--stats','0','--log-level','ERROR']
                processes.append((subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE),target))
            while any(proc.poll() is None for proc,_ in processes):
                pids=','.join(str(proc.pid) for proc,_ in processes if proc.poll() is None)
                if pids:
                    measurement=subprocess.run(['ps','-o','rss=','-p',pids],capture_output=True,text=True)
                    peak_rss=max(peak_rss,sum(int(value) for value in measurement.stdout.split() if value.isdigit())*1024)
                time.sleep(.1)
            seconds=time.monotonic()-start;usage=resource.getrusage(resource.RUSAGE_CHILDREN)
            for proc,target in processes:
                _,errors=proc.communicate();assert proc.returncode==0, 'Synthetic copy failed: '+errors.decode()[:120]
                assert {p.name for p in target.iterdir()}==set(fixture),'Incomplete or duplicated files'
                for name,value in fixture.items():assert sha(target/name)==value['sha256']
            total=accounts*sum(value['size'] for value in fixture.values())
            result={'accounts':accounts,'transfers_per_account':parallel,'repeat':iteration,'faults_injected':inject,'seconds':round(seconds,3),'bytes':total,'mib_per_second':round(total/seconds/1024**2,2),'child_cpu_seconds':round(usage.ru_utime+usage.ru_stime-baseline.ru_utime-baseline.ru_stime,3),'sampled_transfer_rss_bytes':peak_rss,'max_http_gets':counters['max_active'],'responses_429':counters['responses_429'],'disconnects':counters['disconnects'],'all_sha256_verified':True}
            shutil.rmtree(destination);return result
        for accounts in (1,2):
            for parallel in (1,2,4,8):
                for iteration in range(repeats):results.append(one(accounts,parallel,iteration))
        results.append(one(1,4,99,True))
        # Interrupt an actual rclone process, then re-run against its own synthetic destination.
        faults=False
        target=root/'restart-test'
        command=[str(binary),'copy',':http:',str(target),'--http-url',url,'--config',str(root/'empty.conf'),'--transfers','2','--checkers','2','--multi-thread-streams','0','--buffer-size','256k','--stats','0','--log-level','ERROR']
        process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        time.sleep(.3);process.terminate();process.wait(10)
        before={p.name:(sha(p),p.stat().st_mtime_ns) for p in target.iterdir() if p.name in fixture}
        completed=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        assert completed.returncode==0
        for name,value in fixture.items():assert sha(target/name)==value['sha256']
        assert all(sha(target/name)==value[0] and (target/name).stat().st_mtime_ns==value[1] for name,value in before.items())
        restart={'process_interrupted':True,'final_sha256_verified':True,'already_completed_files_preserved':len(before),'leftover_temporary_files':sum(p.name not in fixture for p in target.iterdir()),'scope':'rclone local HTTP fixture, not FCA PostgreSQL restart test'}
        shutil.rmtree(target)
    return {'environment':'macOS ARM64 localhost HTTP, artificial 2ms per 64KiB, not FCA VM/cloud speed','fixture':fixture,'runs':results,'restart':restart}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--rclone',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--repeats',default=2,type=int);args=parser.parse_args()
    assert 1<=args.repeats<=3
    binary=args.rclone.resolve();assert binary.is_file()
    with tempfile.TemporaryDirectory(prefix='fca-stage-a-') as directory:
        root=Path(directory).resolve();(root/'empty.conf').touch()
        result={'synthetic_only':True,'vm_access':'not used by this probe','rclone_version':subprocess.check_output([str(binary),'version'],text=True).splitlines()[0]}
        result['oauth']=oauth_probe(binary,root)
        result['existing_fca']=existing_fca_checks(root)
        result['transfers']=transfer_probe(binary,root,args.repeats)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2))
    print(json.dumps({'synthetic_only':True,'oauth_mock_flows':len(result['oauth']['flows']),'benchmark_runs':len(result['transfers']['runs']),'all_sha256_verified':all(r['all_sha256_verified'] for r in result['transfers']['runs']),'output':str(args.output)}))

if __name__=='__main__':main()
