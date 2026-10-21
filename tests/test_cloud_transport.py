"""Synthetic Stage-B contracts; no external accounts or provider connections."""
import base64
import hashlib
import io
import json
import os
import time
from pathlib import Path
from uuid import uuid4
import urllib.error
from unittest.mock import patch

import pytest

from backend import cloud_auth, oauth
from providers.acquisition import WebProvider, Retryable, AccessDenied, AuthenticationRequired, AppleDownload
from providers.apple.adapter import AccountContext, ProviderError
from providers.integrity import QuickXor, verify_source
from providers.rclone_files import RcloneFiles, transfer_error
from scripts.prepare_private_https import prepare


@pytest.fixture
def vault(tmp_path,monkeypatch):
    key=tmp_path/'key';key.write_text('SYNTHETIC-'+('x'*64));key.chmod(0o600)
    auth=tmp_path/'auth';auth.mkdir(mode=0o700)
    monkeypatch.setenv('FCA_CLOUD_MASTER_KEY_FILE',str(key));monkeypatch.setenv('FCA_CLOUD_AUTH_ROOT',str(auth))
    monkeypatch.setenv('FCA_OAUTH_CONFIG_FILE',str(tmp_path/'absent'))
    case,account,user=uuid4(),uuid4(),uuid4()
    for provider in ('google','microsoft'):
        oauth.save_configuration(provider,'SYNTHETIC-CLIENT','SYNTHETIC-SECRET','https://fca.example.org/api/oauth/callback')
    return case,account,user


def test_https_plan_is_parameterized_private_and_injection_safe():
    plan,nginx=prepare('fca.example.org','10.20.0.5',['10.20.0.0/24','10.77.0.0/24'])
    assert plan['redirect_uri']=='https://fca.example.org/api/oauth/callback'
    assert 'listen 10.20.0.5:443 ssl;' in nginx and 'deny all;' in nginx
    assert plan['public_dns']['A_AAAA_required'] is False
    for host,address,networks in [('10.20.0.5','10.20.0.5',['10.0.0.0/8']),('fca.example.org;bad','10.20.0.5',['10.0.0.0/8']),('fca.example.org','0.0.0.0',['10.0.0.0/8']),('fca.example.org','10.20.0.5',['0.0.0.0/0'])]:
        with pytest.raises(ValueError):prepare(host,address,networks)


@pytest.mark.parametrize('provider,status,reason,kind',[
    ('google',403,'insufficientPermissions',AccessDenied),('google',403,'dailyLimitExceeded',AccessDenied),
    ('google',403,'rateLimitExceeded',Retryable),('google',403,'userRateLimitExceeded',Retryable),
    ('microsoft',403,'accessDenied',AccessDenied),('microsoft',401,'InvalidAuthenticationToken',AuthenticationRequired),
    ('google',404,'notFound',AccessDenied),('microsoft',429,'tooManyRequests',Retryable),
    ('microsoft',503,'serviceUnavailable',Retryable),('google',400,'badRequest',ProviderError)])
def test_http_errors_do_not_retry_permissions_or_leak_bodies(provider,status,reason,kind):
    p=WebProvider(provider,uuid4(),uuid4())
    body={'error':{'code':reason,'message':'SYNTHETIC-SECRET','errors':[{'reason':reason}]}}
    error=urllib.error.HTTPError('https://provider.invalid',status,'',{'Retry-After':'7'},io.BytesIO(json.dumps(body).encode()))
    with pytest.raises(kind) as caught:p.error(error)
    assert 'SYNTHETIC-SECRET' not in str(caught.value)
    if kind is Retryable:
        assert caught.value.delay==7
        assert caught.value.throttled == (status==429 or reason in ('rateLimitExceeded','userRateLimitExceeded'))
    else:assert not p.throttled


def test_quickxor_vectors_chunking_and_all_available_source_hashes(tmp_path):
    vectors=[('', 'AAAAAAAAAAAAAAAAAAAAAAAAAAA='),('Sg==','SgAAAAAAAAAAAAAAAQAAAAAAAAA='),('tbQ=','taAFAAAAAAAAAAAAAgAAAAAAAAA='),('0pZP','0rDEEwAAAAAAAAAAAwAAAAAAAAA=')]
    for source,wanted in vectors:
        q=QuickXor()
        for b in base64.b64decode(source):q.update(bytes([b]))
        assert base64.b64encode(q.digest()).decode()==wanted
    data=bytes(range(256))*5003;q=QuickXor();q.update(data)
    split=QuickXor()
    for i in range(0,len(data),1031):split.update(data[i:i+1031])
    assert split.digest()==q.digest()
    target=tmp_path/'file';target.write_bytes(data)
    import zlib
    hashes={'sha1Hash':hashlib.sha1(data).hexdigest(),'crc32Hash':format(zlib.crc32(data)&0xffffffff,'08x'),'quickXorHash':base64.b64encode(q.digest()).decode()}
    assert verify_source(target,{'file':{'hashes':hashes}})['algorithms']==['crc32','quickxor','sha1']
    assert verify_source(target,{})['status']=='unavailable'
    for key in hashes:
        with pytest.raises(ValueError):verify_source(target,{'file':{'hashes':{**hashes,key:'AAAAAAAAAAAAAAAAAAAAAAAAAAA=' if key=='quickXorHash' else '00'*20}}})


def test_oauth_same_user_other_session_replay_and_configuration_change(vault,monkeypatch):
    case,account,user=vault
    exchanges=[]
    monkeypatch.setattr(oauth,'exchange',lambda *args:(exchanges.append(args) or {'access_token':'SYNTHETIC','refresh_token':'SYNTHETIC','expires_in':3600}))
    def begin():
        result=oauth.begin('google',case,account,user,session_id='session-one')
        assert 'code_challenge_method=S256' in result['url']
        return oauth.load(case,account)['pending']['state']
    state=begin()
    with pytest.raises(ProviderError):oauth.complete('google',case,account,user,state,'SYNTHETIC',session_id='session-two')
    assert not exchanges
    oauth.complete('google',case,account,user,state,'SYNTHETIC',session_id='session-one')
    with pytest.raises(ProviderError):oauth.complete('google',case,account,user,state,'SYNTHETIC',session_id='session-one')
    state=begin();oauth.save_configuration('google','NEW-CLIENT','SYNTHETIC','https://fca.example.org/api/oauth/callback')
    with pytest.raises(ProviderError):oauth.complete('google',case,account,user,state,'SYNTHETIC',session_id='session-one')
    assert len(exchanges)==1


@pytest.mark.parametrize('provider',['google','microsoft'])
def test_real_rclone_encrypted_config_and_rotated_token_survive_restart(vault,monkeypatch,provider):
    case,account,user=vault
    oauth.save(case,account,{'access_token':'SYNTHETIC-ACCESS','refresh_token':'SYNTHETIC-REFRESH','expires_at':time.time()+3600,'authorized_at':1})
    monkeypatch.setattr(WebProvider,'json',lambda *a:{'id':'SYNTHETIC-DRIVE','driveType':'business'})
    with RcloneFiles(provider,case,account) as a:
        assert a.current_token()=='SYNTHETIC-ACCESS'
        saved=a._rpc('config/get',{'name':a.remote})
        assert saved['scope']=='drive.readonly' if provider=='google' else saved['access_scopes']=='Files.Read offline_access'
        config_path=a.config_path
        assert b'SYNTHETIC-ACCESS' not in config_path.read_bytes()
        # A refresh owned by Rclone is persisted before a simulated worker crash.
        rotated=json.loads(saved['token']);rotated['access_token']='SYNTHETIC-ROTATED';rotated['refresh_token']='SYNTHETIC-NEW-REFRESH'
        a._rpc('config/update',{'name':a.remote,'parameters':{'token':json.dumps(rotated)},'opt':{'nonInteractive':True}})
        a._ready=False # force termination without graceful vault synchronization
    with RcloneFiles(provider,case,account) as a:
        assert a.current_token()=='SYNTHETIC-ROTATED'
    assert oauth.load(case,account)['refresh_token']=='SYNTHETIC-NEW-REFRESH'


@pytest.mark.parametrize('provider',['google','microsoft'])
def test_rclone_transport_real_copy_with_synthetic_metadata_gateway(vault,tmp_path,monkeypatch,provider):
    from concurrent.futures import ThreadPoolExecutor
    from backend import evidence
    case,account,user=vault
    oauth.save(case,account,{'access_token':'SYNTHETIC','refresh_token':'SYNTHETIC','expires_at':time.time()+3600,'authorized_at':1})
    monkeypatch.setattr(WebProvider,'json',lambda *a:{'id':'SYNTHETIC-DRIVE','driveType':'personal'})
    monkeypatch.setattr(evidence,'space',lambda *_:None)
    source=tmp_path/'source';source.mkdir();destination=tmp_path/'destination';destination.mkdir()
    for index,size in enumerate((0,1,65536,1048576)):(source/str(index)).write_bytes(bytes([index])*size)
    with RcloneFiles(provider,case,account) as a:
        # Only the source endpoint/IDs are synthetic; RC copy, stats, disk and hash checks are real.
        rpc=a._rpc
        def gateway(endpoint,payload):
            payload={**payload}
            if endpoint=='backend/command':
                assert provider=='google' and payload['command']=='copyid'
                source_id,dest=payload['arg']
                endpoint='operations/copyfile'
                payload={'srcFs':str(source),'srcRemote':source_id,'dstFs':str(Path(dest).parent),'dstRemote':Path(dest).name,'_async':True}
            if 'fs' in payload:payload['fs']=str(source)
            if 'srcFs' in payload:payload['srcFs']=str(source)
            result=rpc(endpoint,payload)
            if endpoint=='operations/stat' and payload.get('remote'):
                result['item']['ID']=payload['remote']
            return result
        monkeypatch.setattr(a,'_rpc',gateway)
        monkeypatch.setattr(a.web,'json',lambda *_:{'version':'v1','eTag':'v1'})
        def transfer(index):
            data=(source/str(index)).read_bytes();q=QuickXor();q.update(data)
            meta={'_rclone_path':str(index),'version':'v1','eTag':'v1','md5Checksum':hashlib.md5(data).hexdigest()}
            if provider=='microsoft':meta['file']={'hashes':{'quickXorHash':base64.b64encode(q.digest()).decode()}}
            a.download({'source_id':str(index),'metadata':meta},destination/(str(index)+'.part'),0,lambda _:None)
            assert (destination/(str(index)+'.part')).read_bytes()==data
            assert meta['_fca_source_verification']['status']=='verified'
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(transfer,range(4)))
        with pytest.raises(ProviderError):
            a.download({'source_id':'../wrong' if provider=='google' else 'wrong-id','metadata':{'_rclone_path':'0'}},destination/'wrong.part',0,lambda _:None)
        assert not (destination/'wrong.part').exists()
        if provider=='google':
            a.download({'source_id':'0','metadata':{'_rclone_path':'an ambiguous duplicate name','version':'v1'}},destination/'by-id.part',0,lambda _:None)
            assert (destination/'by-id.part').read_bytes()==b''
        with pytest.raises(Retryable):
            a.download({'source_id':'0','metadata':{'_rclone_path':'0','version':'v1','eTag':'v1','md5Checksum':'00'*16}},destination/'bad-hash.part',0,lambda _:None)
        assert (destination/'bad-hash.part').is_file() # temporary only, never reported complete


def test_rclone_permission_errors_are_permanent_and_sanitized():
    for provider in ('apple','google','microsoft'):
        with pytest.raises(AccessDenied):transfer_error(provider,'403 accessDenied SYNTHETIC-SECRET')
        with pytest.raises(Retryable):transfer_error(provider,'429 too many requests')
        with pytest.raises(AuthenticationRequired):transfer_error(provider,'invalid_grant')
        # Digits in filenames or IDs are not HTTP status codes.
        with pytest.raises(ProviderError) as caught:transfer_error(provider,'failed to copy report401-429-503.txt: unknown error')
        assert type(caught.value) is ProviderError


def test_only_google_copyid_to_local_temporary_files_is_allowed(vault,tmp_path):
    case,account,user=vault
    adapter=RcloneFiles('google',case,account)
    for command,fs,args in [('moveid',adapter.remote+':',['id',str(tmp_path/'x.part')]),('copyid','other:',['id',str(tmp_path/'x.part')]),('copyid',adapter.remote+':',['id','other:remote.part']),('copyid',adapter.remote+':',['../id',str(tmp_path/'x.part')])]:
        with pytest.raises(ProviderError):adapter._rpc('backend/command',{'command':command,'fs':fs,'arg':args})


def test_actual_failed_async_rclone_job_is_classified_without_exposing_its_error(tmp_path,monkeypatch):
    from backend import evidence
    monkeypatch.setattr(evidence,'space',lambda *_:None)
    source=tmp_path/'source';source.mkdir();config=tmp_path/'config';config.mkdir(mode=0o700)
    with AppleDownload(config/'rclone.conf','SYNTHETIC-'+('x'*64),AccountContext(uuid4(),uuid4())) as adapter:
        adapter._rpc('config/create',{'name':adapter.remote,'type':'alias','parameters':{'remote':str(source)},'opt':{'nonInteractive':True}})
        with pytest.raises(AccessDenied) as caught:
            adapter.download({'source_id':'SYNTHETIC-PRIVATE-NAME','category':'drive','metadata':{}},tmp_path/'missing.part',0,lambda _:None)
        assert 'SYNTHETIC-PRIVATE-NAME' not in str(caught.value)
        with pytest.raises(Retryable):adapter._communication_failed(TimeoutError())


def test_two_accounts_with_four_real_transfers_keep_configuration_separate(vault,tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import ExitStack
    import threading
    import subprocess
    from backend import evidence
    case,first,user=vault;accounts=[first,uuid4()]
    source=tmp_path/'source';source.mkdir()
    payload=b's'*(1024*1024)
    for index in range(4):(source/str(index)).write_bytes(payload)
    monkeypatch.setattr(evidence,'space',lambda *_:None)
    popen=subprocess.Popen
    monkeypatch.setattr('providers.apple.adapter.subprocess.Popen',lambda args,*a,**kw:popen(args+['--bwlimit','2M','--disable','Copy'],*a,**kw))
    barrier=threading.Barrier(8);destinations=[]
    with ExitStack() as stack:
        sessions=[]
        for index,account in enumerate(accounts):
            oauth.save(case,account,{'access_token':'SYNTHETIC-'+str(index),'refresh_token':'SYNTHETIC','expires_at':time.time()+3600,'authorized_at':1})
            sessions.append(stack.enter_context(RcloneFiles('google',case,account)))
        assert sessions[0]._socket!=sessions[1]._socket and sessions[0].config_path!=sessions[1].config_path
        assert [s.current_token() for s in sessions]==['SYNTHETIC-0','SYNTHETIC-1']
        def copy(pair):
            account,index=pair;session=sessions[account]
            before=session._rpc('operations/stat',{'fs':str(source),'remote':str(index),'opt':{'showHash':True}})['item']
            target=tmp_path/(str(account)+'-'+str(index)+'.part')
            barrier.wait(timeout=10)
            session._copy_from(str(source),str(index),{'metadata':before},target,0,lambda _:None)
            assert target.read_bytes()==payload
            destinations.append(target.name)
        with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(copy,[(a,f) for a in range(2) for f in range(4)]))
    assert len(set(destinations))==8
