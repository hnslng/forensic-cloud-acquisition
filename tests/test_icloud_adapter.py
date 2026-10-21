"""Pinned real rclone offline contract tests. Never claim real Apple acceptance."""
from pathlib import Path
import os
import socket
import stat
from uuid import uuid4

import pytest

from providers.apple.adapter import ICloudSession, ProviderError, Scope

KEY = 'Synthetic-Adapter-Key-Only-2026-Long-Enough!'


def scope(service='drive', path='FCA-Synthetic-Test'):
    return Scope(uuid4(), uuid4(), service, path, 'synthetic-test-operator')


def session(tmp_path, approval=None, key=KEY):
    os.chmod(tmp_path, 0o700)
    return ICloudSession(tmp_path / 'rclone.conf', key, approval or scope())


def seed_encrypted_fixture(adapter):
    # In-memory backend has no network. Tests encryption/IPC, not Apple success.
    adapter._rpc('config/create', {'name': adapter.remote, 'type': 'memory',
                 'parameters': {'fixture': 'SYNTHETIC-SECRET-DO-NOT-LOG'},
                 'opt': {'nonInteractive': True}})
    adapter._check_encrypted()


def test_real_pinned_runtime_capabilities_unix_auth_and_cleanup(tmp_path):
    adapter = session(tmp_path)
    with adapter:
        result = adapter.capabilities()
        assert result['runtime_version'] == 'v1.75.2'
        assert result['drive'] and result['photos']
        assert not result['real_account_validated'] and not result['acquisition_available']
        assert stat.S_ISSOCK(adapter._socket.stat().st_mode)
        assert stat.S_IMODE(adapter._socket.parent.stat().st_mode) == 0o700
        # Authentication required even inside the private directory/socket.
        from providers.apple.adapter import _UnixHTTP
        c = _UnixHTTP(adapter._socket, 2)
        c.request('POST', '/config/listremotes', '{}', {'Content-Type': 'application/json'})
        assert c.getresponse().status == 401
        c.close()
        args = Path('/proc/' + str(adapter._process.pid) + '/cmdline').read_bytes()
        assert KEY.encode() not in args
        assert b'--rc-pass' not in args and b'--rc-no-auth' not in args
        runtime = adapter._socket.parent
        process = adapter._process
    assert not runtime.exists() and process.poll() is not None


def test_real_config_encryption_restore_wrong_key_and_context_separation(tmp_path):
    approval = scope()
    with session(tmp_path, approval) as adapter:
        seed_encrypted_fixture(adapter)
    config = tmp_path / 'rclone.conf'
    assert b'SYNTHETIC-SECRET-DO-NOT-LOG' not in config.read_bytes()
    assert stat.S_IMODE(config.stat().st_mode) == 0o600
    with session(tmp_path, approval) as adapter:
        assert adapter._rpc('config/listremotes', {})['remotes'] == [adapter.remote]
        adapter.forget()
    with session(tmp_path, approval) as adapter:
        seed_encrypted_fixture(adapter)
    with pytest.raises(ProviderError):
        with session(tmp_path, approval, key='Another-Synthetic-Key-Only-Long-Enough-2026!'):
            pass
    with pytest.raises(ProviderError, match='another account'):
        with session(tmp_path, scope()):
            pass


def test_scope_rejects_account_root_traversal_and_unapproved_reads(tmp_path):
    for path in ['', '/', '../other', 'folder/../other', 'folder//other', 'other:root', 'folder\\other', 'folder\nother']:
        with pytest.raises(ValueError):
            scope(path=path)
    with pytest.raises(ValueError):
        scope(service='photos', path='PrimarySync')
    scope(service='photos', path='PrimarySync/FCA-Synthetic-Album')
    with session(tmp_path) as adapter:
        with pytest.raises(ProviderError, match='Complete authentication'):
            adapter.list_approved_directory()
        for endpoint in ['sync/copy', 'sync/sync', 'operations/deletefile', 'core/command', 'config/dump']:
            with pytest.raises(ProviderError, match='not permitted'):
                adapter._rpc(endpoint, {})


def test_plaintext_config_and_concurrent_account_session_are_rejected(tmp_path):
    config = tmp_path / 'rclone.conf'
    config.write_text('[synthetic]\npassword=DO-NOT-ACCEPT\n')
    os.chmod(config, 0o600)
    with pytest.raises(ProviderError, match='unencrypted'):
        with session(tmp_path):
            pass
    config.unlink()
    approval = scope()
    with session(tmp_path, approval):
        with pytest.raises(ProviderError, match='Another session'):
            with session(tmp_path, approval):
                pass


def test_challenge_parser_no_raw_errors_and_no_fabricated_success(tmp_path):
    with session(tmp_path) as adapter:
        seed_encrypted_fixture(adapter)
        step = adapter._next_step({'State': '2fa_do', 'Option': {'Name': 'config_2fa'}})
        assert step.status == 'challenge'
        with pytest.raises(ValueError):
            adapter.answer('invalid-code')
        with pytest.raises(ProviderError):
            adapter._next_step({'State': 'unreviewed', 'Option': {'Name': 'unexpected'}})
        with pytest.raises(ProviderError) as error:
            adapter._next_step({'Error': 'SYNTHETIC-UPSTREAM-PASSWORD-TOKEN'})
        assert 'SYNTHETIC-UPSTREAM' not in str(error.value)
        # Provider error responses can echo inputs: never surface raw bodies.
        with pytest.raises(ProviderError) as error:
            adapter._rpc('config/update', {'name': 'nonexistent', 'parameters': {'password': 'SYNTHETIC-UPSTREAM-PASSWORD-TOKEN'}})
        assert 'SYNTHETIC-UPSTREAM' not in str(error.value)


def test_cli_defaults_to_real_runtime_offline_preflight_without_password_prompt(tmp_path, monkeypatch, capsys):
    from providers.apple.cli import main
    key = tmp_path / 'test.key'
    key.write_text(KEY)
    os.chmod(key, 0o600)
    root = tmp_path / 'state'
    root.mkdir(mode=0o700)
    monkeypatch.setattr('sys.argv', ['icloud-test', '--case-id', str(uuid4()), '--account-id', str(uuid4()),
                        '--service', 'drive', '--scope', 'FCA-Synthetic-Test', '--operator', 'QA',
                        '--state-root', str(root), '--key-file', str(key)])
    monkeypatch.setattr('getpass.getpass', lambda *a: pytest.fail('Preflight must not request credentials'))
    assert main() == 0
    output = capsys.readouterr().out
    assert 'Offline preflight only' in output and '"real_account_validated": false' in output
    assert KEY not in output


def test_reauthentication_invalidates_prior_local_auth_state_before_failure(tmp_path, monkeypatch):
    with session(tmp_path) as adapter:
        seed_encrypted_fixture(adapter)
        adapter._next_step({})
        assert adapter._step.status == 'authenticated'
        def refuse(*args):
            raise ProviderError('Synthetic failure; no Apple request')
        monkeypatch.setattr(adapter, '_rpc', refuse)
        with pytest.raises(ProviderError):
            adapter.begin('synthetic@example.invalid', 'Synthetic-password')
        assert adapter._step is None and adapter._state == ''
        with pytest.raises(ProviderError):
            adapter.list_approved_directory()


def test_explicit_browse_rejects_untrusted_paths_and_auth_state_is_reviewed(tmp_path):
    with session(tmp_path) as adapter:
        for path in ['../outside', '/root', 'folder//other', 'other:root', 'folder\\other']:
            with pytest.raises(ValueError):
                adapter.browse('drive', path)
        with pytest.raises(ValueError):
            adapter.browse('unreviewed-provider', '')
        with pytest.raises(ProviderError):
            adapter.resume_challenge('arbitrary-state', 'config_2fa')
        adapter.resume_challenge('2fa_sms_1_sms', 'config_2fa_sms')
        assert adapter._step.status == 'challenge'


def test_actual_async_copy_inventory_and_parallel_files_offline(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from providers.acquisition import AppleDownload
    from backend import evidence
    from providers.apple.adapter import AccountContext
    os.chmod(tmp_path,0o700)
    config=tmp_path/'config';config.mkdir(mode=0o700)
    source=tmp_path/'source';source.mkdir();(source/'folder').mkdir()
    for i,size in enumerate([0,1,65536,1048576]):(source/'folder'/('file'+str(i))).write_bytes(b'z'*size)
    destination=tmp_path/'destination';destination.mkdir()
    monkeypatch.setattr(evidence,'space',lambda *_:None)
    with AppleDownload(config/'rclone.conf',KEY,AccountContext(uuid4(),uuid4())) as adapter:
        adapter._rpc('config/create',{'name':adapter.remote,'type':'alias','parameters':{'remote':str(source)},'opt':{'nonInteractive':True}})
        records=[r for r in adapter.inventory('drive') if not r.get('directory')]
        assert len(records)==4
        def transfer(record):
            target=destination/(str(record['size'])+'.part')
            adapter.download({'source_id':record['id'],'metadata':record['metadata'],'category':'drive'},target,0,lambda _:None)
            assert target.read_bytes()==b'z'*record['size']
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(transfer,records))


def test_real_rclone_live_stats_before_atomic_target_publication(tmp_path,monkeypatch):
    from providers.acquisition import AppleDownload
    from providers.apple.adapter import AccountContext
    from backend import evidence
    os.chmod(tmp_path,0o700)
    config=tmp_path/'config';config.mkdir(mode=0o700)
    source=tmp_path/'source';source.mkdir()
    payload=b'z'*(4*1024*1024);(source/'large').write_bytes(payload)
    destination=tmp_path/'destination';destination.mkdir();target=destination/'large.part'
    monkeypatch.setattr(evidence,'space',lambda *_:None)
    observed=[]
    # Bandwidth limiting is process-wide in rclone; per-request config does not
    # slow a local fixture reliably. Force a real streamed local copy here.
    import subprocess
    popen=subprocess.Popen
    def slow_runtime(args,*a,**kw):
        return popen(args+['--bwlimit','1M','--disable','Copy'],*a,**kw)
    monkeypatch.setattr('providers.apple.adapter.subprocess.Popen',slow_runtime)
    with AppleDownload(config/'rclone.conf',KEY,AccountContext(uuid4(),uuid4())) as adapter:
        adapter._rpc('config/create',{'name':adapter.remote,'type':'alias','parameters':{'remote':str(source)},'opt':{'nonInteractive':True}})
        record=next(adapter.inventory('drive'));rpc=adapter._rpc
        def limited(endpoint,payload):
            if endpoint=='operations/copyfile':payload={**payload,'_config':{**payload['_config'],'BwLimit':'1M'}}
            return rpc(endpoint,payload)
        monkeypatch.setattr(adapter,'_rpc',limited)
        def progress(count):observed.append((count,target.exists()))
        adapter.download({'source_id':record['id'],'metadata':record['metadata'],'category':'drive'},target,0,progress)
    assert any(0<count<len(payload) and not exists for count,exists in observed)
    assert target.read_bytes()==payload
