"""Synthetic transport contracts + real PostgreSQL queue. Never real cloud accounts."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from uuid import UUID
import pytest

from backend import acquisitions, evidence, oauth, cloud_auth
from backend.db import connect
from providers.acquisition import Retryable, WebProvider, check_url, clean_metadata
from providers.apple.adapter import ProviderError
from test_phase1 import synthetic_database, client, new_case, migration_connection

@pytest.fixture
def storage(monkeypatch,tmp_path):
    key=tmp_path/'key';key.write_text('Synthetic-Master-Key-Test-2026-'+'x'*40)
    auth=tmp_path/'auth';auth.mkdir(mode=0o700)
    monkeypatch.setenv('FCA_CLOUD_MASTER_KEY_FILE',str(key));monkeypatch.setenv('FCA_CLOUD_AUTH_ROOT',str(auth))
    monkeypatch.setattr(cloud_auth,'status',lambda *_:{'connection_status':'connected','can_browse':True,'can_authenticate':True})
    monkeypatch.setenv("FCA_TEST_RERAISE","1")
    acquisitions.STOP.clear()
    monkeypatch.setattr(evidence,"space",lambda *_:None)
    return auth

def setup(c,number='SYNTHETIC-QUEUE'):
    case=new_case(c,number)
    account=c.post('/api/cases/'+case['id']+'/cloud-accounts',json={'provider':'apple','label':'Synthetic account'}).json()
    return case,account,'/api/cases/'+case['id']+'/cloud-accounts/'+account['id']+'/acquisitions'

def enqueue(c,url):
    result=c.post(url,json={'service':'drive','path':''});assert result.status_code==201,result.text
    return result.json()

def row(job):
    with connect() as db: return db.execute('SELECT * FROM acquisitions WHERE id=%s',(job['id'],)).fetchone()

class Synthetic:
    def __init__(self,fail=False):
        self.limits=[];self.active=0;self.maximum=0;self.calls={};self.lock=threading.Lock();self.fail=fail
    def identity(self):return {"synthetic_account":"synthetic@example.invalid"}
    def inventory(self,*args):
        for i,size in enumerate([0,1,1024,65536,262144,17,8192,99]):
            yield {'id':str(i),'path':'Ordner/datei'+str(i),'size':size,'metadata':{'synthetic_size':size}}
    def download(self,record,target,reserve,progress):
        identifier=record['source_id']
        with self.lock:
            self.calls[identifier]=self.calls.get(identifier,0)+1;self.active+=1;self.maximum=max(self.maximum,self.active)
        try:
            target.write_bytes(b'x'*min(8,record['size']));progress(target.stat().st_size);time.sleep(.08)
            if self.fail and identifier=='2' and self.calls[identifier]==1: raise evidence.StorageError('Synthetischer Netzwerkabbruch mit Neustart.')
            target.write_bytes(b'x'*record['size']);progress(record['size'])
        finally:
            with self.lock:self.active-=1

def adapter(monkeypatch,value):
    @contextmanager
    def factory(*args):yield value
    monkeypatch.setattr(acquisitions,'open_provider',factory)

def test_paths_case_collision_accounts_and_no_overwrite(storage,tmp_path):
    c=client();case,account,url=setup(c,'../../Fall:2026/001')
    another=c.post('/api/cases/'+case['id']+'/cloud-accounts',json={'provider':'apple','label':'second'}).json()
    with connect() as db:
        case_row=db.execute('SELECT * FROM cases WHERE id=%s',(case['id'],)).fetchone()
        path=evidence.ensure_case(db,case_row)
        assert '..' not in Path(path).parts and str(case['id']) in path
        assert evidence.directory(path).is_dir()
        one=evidence.ensure_account(db,case_row,{'id':account['id'],'provider':'apple'},'drive')
        two=evidence.ensure_account(db,case_row,{'id':another['id'],'provider':'apple'},'drive')
        assert one.endswith('/iCloud_1') and two.endswith('/iCloud_2')
    assert evidence.source_name('same.txt','1')!=evidence.source_name('same.txt','2')
    root=evidence.root();(root/'escape').symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(evidence.StorageError):evidence.directory('escape/forbidden')
    with pytest.raises(evidence.StorageError):evidence.file_path(root,'../bad')

def test_real_queue_parallel_files_checksums_report_and_completed_immutable(storage,monkeypatch):
    c=client();case,account,url=setup(c);job=enqueue(c,url)
    assert c.post(url,json={'service':'drive','path':''}).status_code==409
    source=Synthetic();adapter(monkeypatch,source);acquisitions.run_job(UUID(job['id']))
    current=row(job);assert current['status']=='completed',current
    assert source.maximum==4 and current['files_done']==8 and current['bytes_done']==sum([0,1,1024,65536,262144,17,8192,99])
    with connect() as db:
        files=db.execute('SELECT * FROM acquisition_files WHERE acquisition_id=%s',(job['id'],)).fetchall()
    for file in files:
        saved=evidence.file_path(evidence.directory(current['directory']+'/Daten'),file['relative_path'])
        assert saved.stat().st_size==file['size'] and evidence.sha256(saved)==file['sha256']
    report=json.loads((evidence.directory(current['directory']+'/_FCA')/'Sicherungsbericht.json').read_text())
    assert report['status']=='completed' and report['sicherungs_id']==job['id']
    assert c.post('/api/cases/'+case['id']+'/acquisitions/'+job['id']+'/resume',json={}).status_code==409
    second=enqueue(c,url);assert second['id']!=job['id']

def test_interrupted_queue_resumes_completed_files_without_duplicates(storage,monkeypatch):
    c=client();case,account,url=setup(c);job=enqueue(c,url)
    source=Synthetic(fail=True);adapter(monkeypatch,source);acquisitions.run_job(UUID(job['id']))
    assert row(job)['status']=='paused'
    with connect() as db: before=db.execute("SELECT source_id,sha256 FROM acquisition_files WHERE acquisition_id=%s AND status='completed'",(job['id'],)).fetchall()
    assert before
    assert c.post('/api/cases/'+case['id']+'/acquisitions/'+job['id']+'/resume',json={}).status_code==200
    acquisitions.run_job(UUID(job['id']));assert row(job)['status']=='completed'
    for item in before: assert source.calls[item['source_id']]==1
    assert source.calls['2']==2
    with connect() as db: assert db.execute('SELECT count(*) AS n FROM acquisition_files WHERE acquisition_id=%s',(job['id'],)).fetchone()['n']==8

def test_queue_permissions_and_settings_limits(storage):
    c=client();case,account,url=setup(c);bob=client('bob');admin=client('admin')
    assert bob.post(url,json={'service':'drive','path':''}).status_code==404
    assert c.put('/api/admin/acquisition-settings',json={'file_parallelism':1,'account_parallelism':1,'reserve_bytes':2147483648}).status_code==403
    assert admin.put('/api/admin/acquisition-settings',json={'file_parallelism':5,'account_parallelism':2,'reserve_bytes':2147483648}).status_code==422
    assert admin.put('/api/admin/acquisition-settings',json={'file_parallelism':4,'account_parallelism':2,'reserve_bytes':2147483648}).status_code==200
    assert admin.get('/api/admin/acquisition-settings').json()['account_parallelism']==2
    del c.headers['X-CSRF-Token'];assert c.post(url,json={'service':'drive','path':''}).status_code==403

def test_low_disk_pauses_before_file_and_revoked_rights_stop(storage,monkeypatch):
    c=client();case,account,url=setup(c);job=enqueue(c,url)
    source=Synthetic();adapter(monkeypatch,source)
    def low(*_):raise evidence.StorageError('Synthetisch: kein Speicherplatz.')
    monkeypatch.setattr(evidence,'space',low)
    acquisitions.run_job(UUID(job['id']));assert row(job)['status']=='paused' and not source.calls
    monkeypatch.setattr(evidence,'space',lambda *_:None)
    with migration_connection() as db:db.execute('DELETE FROM case_members WHERE case_id=%s',(case['id'],));db.execute("UPDATE acquisitions SET status='queued' WHERE id=%s",(job['id'],))
    acquisitions.run_job(UUID(job['id']));assert row(job)['status']=='paused' and not source.calls

def test_tampered_completed_file_never_overwritten(storage,monkeypatch):
    c=client();case,account,url=setup(c);job=enqueue(c,url);source=Synthetic();adapter(monkeypatch,source)
    acquisitions.run_job(UUID(job['id']));current=row(job)
    target=evidence.directory(current['directory']+'/Daten')/'Ordner/datei1';target.write_bytes(b'tampered')
    with migration_connection() as db:db.execute("UPDATE acquisitions SET status='queued' WHERE id=%s",(job['id'],))
    acquisitions.run_job(UUID(job['id']));assert row(job)['status']=='failed' and target.read_bytes()==b'tampered'

def test_oauth_pkce_encryption_user_binding_and_refresh(storage,monkeypatch):
    c=client();case,account,url=setup(c)
    oauth.save_configuration('google','synthetic-client','synthetic-secret','https://fca.test/api/oauth/callback')
    result=oauth.begin('google',case['id'],account['id'],'alice')
    assert 'code_challenge_method=S256' in result['url'] and 'drive.readonly' in result['url']
    value=oauth.load(case['id'],account['id']);nonce=value['pending']['state']
    with pytest.raises(ProviderError):oauth.complete('google',case['id'],account['id'],'bob',nonce,'code')
    monkeypatch.setattr(oauth,'exchange',lambda *_:{'access_token':'Synthetic-access-token','refresh_token':'Synthetic-refresh-token','expires_in':3600})
    oauth.complete('google',case['id'],account['id'],'alice',nonce,'code')
    assert oauth.token('google',case['id'],account['id'])=='Synthetic-access-token'
    assert oauth.status('google',case['id'],account['id'])['can_acquire']
    assert all(b'Synthetic-access-token' not in file.read_bytes() for file in storage.rglob('*.enc'))
    with pytest.raises(ProviderError):oauth.complete('google',case['id'],account['id'],'alice',nonce,'code')

def test_provider_pagination_calendar_and_secret_metadata(monkeypatch):
    provider=WebProvider('google',UUID(int=1),UUID(int=2));calls=[]
    def get(url):
        calls.append(url)
        if 'calendarList' in url:return {'items':[{'id':'synthetic@example.invalid','summary':'Test'}]}
        if 'pageToken=' not in url:return {'items':[{'id':'1','summary':'Termin','recurrence':['RRULE:FREQ=DAILY']}],'nextPageToken':'next'}
        return {'items':[{'id':'2','status':'cancelled'}]}
    monkeypatch.setattr(provider,'json',get)
    records=list(provider.inventory('calendar'))
    assert len(records)==3 and 'RRULE' in records[1]['payload'] and 'cancelled' in records[2]['payload']
    assert 'pageToken=next' in calls[-1]
    with pytest.raises(ProviderError):check_url('https://internal.invalid/token','google')
    assert clean_metadata({'@microsoft.graph.downloadUrl':'secret','name':'safe'})=={'name':'safe'}

def test_throttling_respects_retry_after():
    import urllib.error
    provider=WebProvider('microsoft',UUID(int=1),UUID(int=2))
    with pytest.raises(Retryable) as caught:provider.error(urllib.error.HTTPError('https://graph.microsoft.com',429,'',{'Retry-After':'37'},None))
    assert caught.value.delay==37 and caught.value.throttled


def test_durable_worker_process_restart_and_two_account_limit(storage,monkeypatch):
    """Kill a genuine worker process; another process recovers the persisted queue."""
    import subprocess,sys
    c=client();jobs=[]
    for i in range(3):
        case,account,url=setup(c,'SYNTHETIC-RESTART-'+str(i));jobs.append(enqueue(c,url))
    program='''
import sys,time
sys.path.insert(0,'/app/tests')
from contextlib import contextmanager
from backend import acquisitions,evidence
evidence.space=lambda *_:None
from test_acquisitions import Synthetic
class Slow(Synthetic):
 def download(self,*args):
  time.sleep(1)
  super().download(*args)
@contextmanager
def provider(*args):yield Slow()
acquisitions.open_provider=provider
acquisitions.main()
'''
    process=subprocess.Popen([sys.executable,'-c',program],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        deadline=time.monotonic()+20;maximum=0
        while time.monotonic()<deadline:
            with connect() as db:
                count=db.execute("SELECT count(*) AS n FROM acquisitions WHERE status='running'").fetchone()['n']
            maximum=max(maximum,count)
            if maximum==2:break
            assert process.poll() is None;time.sleep(.05)
        assert maximum==2
        process.kill();process.wait(timeout=5)
        process=subprocess.Popen([sys.executable,'-c',program],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        deadline=time.monotonic()+35
        while time.monotonic()<deadline:
            with connect() as db:
                rows=db.execute('SELECT status FROM acquisitions').fetchall()
                count=sum(r['status']=='running' for r in rows)
            assert count<=2
            if all(r['status']=='completed' for r in rows):break
            assert process.poll() is None;time.sleep(.1)
        assert all(row(j)['status']=='completed' for j in jobs)
    finally:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()


def test_actual_http_disconnect_and_clean_retry(storage,monkeypatch,tmp_path):
    """Real local TCP server cuts a transfer; retry never appends duplicate bytes."""
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    import socket
    import providers.acquisition as transport
    payload=b'network-fixture-'*1024
    class Handler(BaseHTTPRequestHandler):
        calls=0
        def log_message(self,*args):pass
        def do_GET(self):
            if 'alt=media' not in self.path:
                raw=json.dumps({'id':'file','version':'v1'}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
            Handler.calls+=1
            self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers()
            if Handler.calls==1:
                self.wfile.write(payload[:100]);self.wfile.flush();self.connection.shutdown(socket.SHUT_RDWR);self.connection.close()
            else:self.wfile.write(payload)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    monkeypatch.setattr(transport,'check_url',lambda *_:None)
    monkeypatch.setattr(oauth,'token',lambda *_:'SYNTHETIC-LOCAL-ONLY')
    provider=WebProvider('google',UUID(int=1),UUID(int=2));provider.base='http://127.0.0.1:'+str(server.server_port)
    record={'source_id':'file','metadata':{'version':'v1','md5Checksum':hashlib.md5(payload).hexdigest()}}
    target=tmp_path/'network.part'
    try:
        with pytest.raises(Retryable):provider.download(record,target,0,lambda _:None)
        assert target.read_bytes()==payload[:100]
        provider.download(record,target,0,lambda _:None)
        assert target.read_bytes()==payload and Handler.calls==2
    finally:server.shutdown();server.server_close();thread.join(timeout=3)


def test_official_oauth_api_permissions_pkce_and_no_secret_audit(storage,monkeypatch):
    c,admin,bob=client(),client('admin'),client('bob');case=new_case(c)
    url='/api/cases/'+case['id']+'/cloud-accounts'
    account=c.post(url,json={'provider':'google','label':'SYNTHETIC Google'}).json()
    values={'provider':'google','client_id':'synthetic-client','client_secret':'SYNTHETIC-CLIENT-SECRET','redirect_uri':'https://fca.test/api/oauth/callback'}
    assert c.put('/api/admin/oauth-settings',json=values).status_code==403
    assert admin.put('/api/admin/oauth-settings',json={**values,'redirect_uri':'https://untrusted.invalid/api/oauth/callback'}).status_code==422
    assert admin.put('/api/admin/oauth-settings',json=values).status_code==200
    begin=c.post(url+'/'+account['id']+'/oauth/begin',json={})
    assert begin.status_code==200 and 'code_challenge_method=S256' in begin.json()['url']
    assert 'SYNTHETIC-CLIENT-SECRET' not in begin.text
    pending=oauth.load(case['id'],account['id'])['pending']
    monkeypatch.setattr(oauth,'exchange',lambda *_:{'access_token':'SYNTHETIC-ACCESS','refresh_token':'SYNTHETIC-REFRESH','expires_in':3600})
    data={'case_id':case['id'],'account_id':account['id'],'state':pending['state'],'code':'SYNTHETIC-CODE'}
    assert bob.post('/api/oauth/complete',json=data).status_code==404
    assert c.post('/api/oauth/complete',json=data).status_code==200
    assert c.post('/api/oauth/complete',json=data).status_code==409
    assert c.get(url).json()[0]['can_acquire']
    events=c.get('/api/cases/'+case['id']+'/audit').text
    for secret in ['SYNTHETIC-ACCESS','SYNTHETIC-REFRESH','SYNTHETIC-CLIENT-SECRET','SYNTHETIC-CODE',pending['state']]:assert secret not in events


def test_disk_reserve_is_enforced_before_and_during_write(monkeypatch):
    from collections import namedtuple
    usage=namedtuple('usage','total used free')
    monkeypatch.setattr(evidence.shutil,'disk_usage',lambda *_:usage(8*1024**3,6*1024**3,2*1024**3))
    evidence.space(2*1024**3)
    with pytest.raises(evidence.StorageError):evidence.space(2*1024**3,1)


def test_worker_retries_transient_file_and_reduces_next_wave(storage,monkeypatch):
    c=client();case,account,url=setup(c);job=enqueue(c,url)
    class Throttled(Synthetic):
        failed=False
        def download(self,record,*args):
            if record['source_id']=='0' and not self.failed:
                self.failed=True;raise Retryable(1,True)
            super().download(record,*args)
    source=Throttled();adapter(monkeypatch,source)
    acquisitions.run_job(UUID(job['id']));assert row(job)['status']=='completed'
    with connect() as db:
        values=db.execute('SELECT attempts FROM acquisition_files WHERE acquisition_id=%s AND source_id=%s',(job['id'],'0')).fetchone()
    assert values['attempts']==2


def test_microsoft_drive_nested_names_and_linked_containers_are_explicitly_skipped(monkeypatch):
    provider=WebProvider('microsoft',UUID(int=1),UUID(int=2))
    def get(url):
        if '/items/folder/' in url:return {'value':[{'id':'child','name':'report.txt','size':12,'file':{},'eTag':'v1'}]}
        return {'value':[{'id':'folder','name':'Ordner','folder':{}},{'id':'a','name':'same.txt','size':3,'file':{},'eTag':'v1'},{'id':'b','name':'same.txt','size':4,'file':{},'eTag':'v1'},{'id':'linked','name':'Extern','folder':{},'remoteItem':{'id':'other'}},{'id':'package','name':'Paket','folder':{},'package':{}}]}
    monkeypatch.setattr(provider,'json',get)
    records=list(provider.inventory('drive'))
    assert len(records)==4 and len(provider.limits)==2
    assert len({r['path'] for r in records})==4
    child=next(r for r in records if r['id']=='child');assert '/' in child['path']


def test_outlook_calendar_view_uses_explicit_window_and_follows_pagination(monkeypatch):
    provider=WebProvider('microsoft',UUID(int=1),UUID(int=2));calls=[]
    def get(url):
        calls.append(url)
        if 'calendarView' not in url:return {'value':[{'id':'calendar','name':'Testkalender'}]}
        if 'skiptoken' not in url:return {'value':[{'id':'event1','type':'occurrence'}],'@odata.nextLink':'https://graph.microsoft.com/v1.0/me/calendars/calendar/calendarView?$skiptoken=next'}
        return {'value':[{'id':'event2','type':'exception'}]}
    monkeypatch.setattr(provider,'json',get)
    records=list(provider.inventory('calendar','2020-01-01/2021-01-01'))
    assert len(records)==3 and 'occurrence' in records[1]['payload'] and 'exception' in records[2]['payload']
    assert 'startDateTime=2020-01-01T00%3A00%3A00Z' in calls[1]
    assert 'skiptoken=next' in calls[2]
    with pytest.raises(ProviderError):list(provider.inventory('calendar'))


def test_google_workspace_exports_and_unavailable_types_are_recorded(monkeypatch):
    provider=WebProvider('google',UUID(int=1),UUID(int=2))
    monkeypatch.setattr(provider,'json',lambda *_:{'files':[{'id':'doc','name':'Dokument','mimeType':'application/vnd.google-apps.document','version':'1'},{'id':'form','name':'Formular','mimeType':'application/vnd.google-apps.form'}]})
    records=list(provider.inventory('drive'))
    assert len(records)==1 and records[0]['path'].endswith('.docx') and records[0]['size']==-1
    assert records[0]['metadata']['export_mime'].endswith('wordprocessingml.document')
    assert provider.limits==['Nicht exportierbares Google-Objekt: form']


def test_graph_content_redirect_never_forwards_bearer_to_storage(storage,monkeypatch):
    import urllib.error
    import providers.acquisition as transport
    provider=WebProvider('microsoft',UUID(int=1),UUID(int=2));requests=[]
    monkeypatch.setattr(oauth,'token',lambda *_:'SYNTHETIC-BEARER')
    def open_request(request,**kwargs):
        requests.append(request)
        if len(requests)==1:raise urllib.error.HTTPError(request.full_url,302,'',{'Location':'https://synthetic.sharepoint.com/file?temporary=secret'},None)
        return 'synthetic-response'
    monkeypatch.setattr(transport.OPENER,'open',open_request)
    assert provider.request('https://graph.microsoft.com/v1.0/me/drive/items/file/content',download=True)=='synthetic-response'
    assert requests[0].get_header('Authorization')=='Bearer SYNTHETIC-BEARER'
    assert requests[1].get_header('Authorization') is None


def test_unknown_source_size_is_not_a_known_total(storage,monkeypatch):
    c=client();case,account,url=setup(c);job=enqueue(c,url)
    class Unknown(Synthetic):
        def inventory(self,*args):yield {'id':'unknown','path':'export.json','size':-1,'metadata':{}}
        def download(self,record,target,reserve,progress):target.write_bytes(b'export');progress(6)
    source=Unknown();adapter(monkeypatch,source);acquisitions.run_job(UUID(job['id']))
    current=row(job)
    assert current['status']=='completed' and current['bytes_done']==6 and not current['total_known']
    assert c.get('/api/cases/'+case['id']+'/cloud-accounts').json()[0]['acquisition']['total_known'] is False
