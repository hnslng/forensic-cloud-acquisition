"""Durable PostgreSQL queue. One worker coordinator, at most two account tasks."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import json
import os
from pathlib import Path
import signal
import threading
import time
from uuid import UUID, uuid4
from psycopg.types.json import Jsonb

from backend.db import connect, audit
from backend import evidence
from backend.runtime_limits import ceilings
from providers.acquisition import open_provider, Retryable, AuthenticationRequired
from providers.apple.adapter import ProviderError

STOP=threading.Event()
CATEGORIES={'apple':('drive','photos','both'),'google':('drive','calendar'),'microsoft':('drive','calendar')}
LABELS={'queued':'Wartet','running':'Läuft','pausing':'Wird pausiert','paused':'Pausiert','failed':'Fehlgeschlagen','incomplete':'Unvollständig','completed':'Abgeschlossen'}
PUBLIC="id,case_id,account_id,category,scope_path,status,created_at,started_at,ended_at,bytes_done,bytes_total,files_done,speed,reason,inventory_complete,total_known,(SELECT count(*) FROM acquisition_files f WHERE f.acquisition_id=acquisitions.id) AS files_discovered,(SELECT count(*) FROM acquisition_files f WHERE f.acquisition_id=acquisitions.id AND f.status='completed' AND f.md5 IS NOT NULL) AS md5_done,(SELECT count(*) FROM acquisition_files f WHERE f.acquisition_id=acquisitions.id AND f.status='running') AS files_active,(SELECT file_parallelism FROM acquisition_settings WHERE singleton) AS configured_limit,coalesce((resource_observations->>'transfer_limit')::integer,(SELECT file_parallelism FROM acquisition_settings WHERE singleton)) AS transfer_limit"

def resources():
    data={}
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemAvailable:'): data['available_memory_bytes']=int(line.split()[1])*1024
        data['process_rss_pages']=int(Path('/proc/self/statm').read_text().split()[1])
        data['free_disk_bytes']=__import__('shutil').disk_usage(evidence.root()).free
        data['load_average']=list(os.getloadavg())
        stat=Path('/sys/fs/cgroup/memory.stat')
        if stat.is_file():
            counters=dict(line.split() for line in stat.read_text().splitlines())
            data['container_inactive_file_bytes']=int(counters.get('inactive_file',0))
        maximum=Path('/sys/fs/cgroup/memory.max')
        if maximum.is_file() and maximum.read_text().strip().isdigit():
            data['container_limit_bytes']=int(maximum.read_text())
            data['container_memory_bytes']=int(Path('/sys/fs/cgroup/memory.current').read_text())
    except (OSError,ValueError): pass
    return data

def memory_pressure(value=None):
    value=resources() if value is None else value
    return (value.get('available_memory_bytes',1024**3)<150*1024**2
            or max(0,value.get('container_memory_bytes',0)-value.get('container_inactive_file_bytes',0))>value.get('container_limit_bytes',1024**3)*.85)

def require_memory():
    value=resources()
    if memory_pressure(value):
        error=evidence.StorageError('Arbeitsspeicher knapp. Sicherung pausiert.')
        error.resource_observation=value
        raise error

def settings(conn):
    value=conn.execute('SELECT * FROM acquisition_settings WHERE singleton').fetchone()
    for key,maximum in ceilings().items():value[key]=min(maximum,value[key])
    return value

def enqueue(conn,case,account,user,category,scope):
    if category not in CATEGORIES[account['provider']]: raise ProviderError('Dieser Datenbereich ist nicht verfügbar.')
    config=settings(conn); evidence.space(config['reserve_bytes'])
    path=evidence.ensure_account(conn,case,account,category)
    identifier=uuid4(); relative=path+'/Lauf_'+str(identifier)
    evidence.directory(relative+'/Daten'); evidence.directory(relative+'/_FCA')
    row=conn.execute('INSERT INTO acquisitions(id,case_id,account_id,category,scope_path,requested_by,operator_initials,directory) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING '+PUBLIC,
                     (identifier,case['id'],account['id'],category,scope,user['id'],case['operator_initials'],relative)).fetchone()
    audit(conn,user,'acquisition_queued',case['id'],details={'acquisition_id':str(identifier),'category':category,'account_id':str(account['id'])})
    return row

def allowed(conn,job):
    return conn.execute("SELECT u.id FROM users u WHERE u.id=%s AND u.active AND (u.role='admin' OR EXISTS(SELECT 1 FROM case_members m WHERE m.case_id=%s AND m.user_id=u.id AND access='editor'))",(job['requested_by'],job['case_id'])).fetchone() is not None

def job_active(identifier):
    with connect() as conn:
        row=conn.execute('SELECT * FROM acquisitions WHERE id=%s',(identifier,)).fetchone()
        return row['status']=='running' and allowed(conn,row)

def run_file(job, row, adapter, reserve, cancel):
    base=evidence.directory(job['directory']+'/Daten')
    final=evidence.file_path(base,row['relative_path'])
    temporary=evidence.file_path(evidence.directory(job['directory']+'/_FCA/temporär'),str(row['id'])+'.part')
    progress_time=[0]
    def progress(count):
        if STOP.is_set() or cancel.is_set(): raise evidence.StorageError('Sicherung unterbrochen; Wiederaufnahme möglich.')
        now=time.monotonic()
        if now-progress_time[0]>=1:
            require_memory()
            if not job_active(job['id']): raise evidence.StorageError('Sicherung pausiert oder Berechtigung entzogen.')
            with connect() as conn: conn.execute('UPDATE acquisition_files SET bytes_done=%s WHERE id=%s',(count,row['id']))
            progress_time[0]=now
    # Never trust a previously completed file without rechecking its recorded hash.
    if final.exists():
        if row['sha256'] and evidence.sha256(final)==row['sha256'] and final.stat().st_size==row['bytes_done']:
            with connect() as conn: conn.execute("UPDATE acquisition_files SET status='completed',md5=%s WHERE id=%s",(evidence.file_hashes(final)[1],row['id']))
            return
        raise ProviderError('Vorhandene Zieldatei stimmt nicht mit dem Prüfprotokoll überein. Kein Überschreiben.')
    for attempt in range(1,6):
        progress(0)
        with connect() as conn:
            if not allowed(conn,job): raise evidence.StorageError('Fallberechtigung wurde entzogen.')
            conn.execute("UPDATE acquisition_files SET status='running',attempts=attempts+1,bytes_done=0 WHERE id=%s",(row['id'],))
        try:
            evidence.space(reserve,max(0,row['size']))
            record={**row,'category':row['metadata'].get('_fca_category',job['category']),'source_id':row['metadata'].get('_fca_source_id',row['source_id'])}
            # Incomplete files are restarted safely. Completed files are retained across restarts.
            adapter.download(record,temporary,reserve,progress)
            progress(temporary.stat().st_size)
            size=temporary.stat().st_size
            if row['size']>=0 and size!=row['size']: raise Retryable()
            checksum,md5=evidence.file_hashes(temporary)
            with open(temporary,'rb') as handle: os.fsync(handle.fileno())
            # Journal hash before publication, allowing recovery after a crash between link/commit.
            with connect() as conn: conn.execute('UPDATE acquisition_files SET sha256=%s,md5=%s,bytes_done=%s WHERE id=%s',(checksum,md5,size,row['id']))
            if evidence.sha256(temporary)!=checksum: raise ProviderError('Prüfsummenprüfung fehlgeschlagen.')
            os.link(temporary,final) # atomic no-clobber publication on the same evidence filesystem
            temporary.unlink()
            fd=os.open(final.parent,os.O_RDONLY|os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
            record['metadata'].pop('_fca_outcome',None)
            with connect() as conn: conn.execute("UPDATE acquisition_files SET status='completed',reason=NULL,metadata=%s WHERE id=%s",(Jsonb(record['metadata']),row['id']))
            return
        except Retryable as error:
            # Reduce the next wave to one transfer after throttling/transient errors.
            cancel.throttled_until=max(cancel.throttled_until,time.monotonic()+max(30,error.delay))
            if attempt==5: raise ProviderError('Übertragung nach fünf Versuchen fehlgeschlagen. Wiederaufnahme möglich.') from None
            deadline=time.monotonic()+max(error.delay,min(120,2**attempt))
            while time.monotonic()<deadline:
                progress(temporary.stat().st_size if temporary.exists() else 0)
                if STOP.wait(.5): raise evidence.StorageError('Sicherung unterbrochen.')

def totals(conn,identifier,last):
    row=conn.execute("SELECT coalesce(sum(bytes_done),0) AS done,coalesce(sum(greatest(size,0)),0) AS total,count(*) FILTER(WHERE status='completed') AS files FROM acquisition_files WHERE acquisition_id=%s",(identifier,)).fetchone()
    now=time.monotonic();done=int(row['done'])
    if not last: last.append((now,done))
    last.append((now,done))
    while len(last)>2 and last[1][0]<now-4: last.popleft()
    elapsed=max(.1,now-last[0][0]);speed=max(0,int((done-last[0][1])/elapsed))
    conn.execute('UPDATE acquisitions SET bytes_done=%s,bytes_total=%s,files_done=%s,speed=%s,heartbeat=now() WHERE id=%s',(row['done'],row['total'],row['files'],speed,identifier))

def report(job,status,reason=None):
    directory=evidence.directory(job['directory']+'/_FCA')
    with connect() as conn:
        case=conn.execute('SELECT business_number,name FROM cases WHERE id=%s',(job['case_id'],)).fetchone()
        account=conn.execute('SELECT provider,label FROM cloud_accounts WHERE id=%s',(job['account_id'],)).fetchone()
        current=conn.execute('SELECT * FROM acquisitions WHERE id=%s',(job['id'],)).fetchone()
        ledger=conn.execute("SELECT count(*) AS discovered,coalesce(sum(greatest(size,0)),0) AS discovered_known_bytes,count(*) FILTER (WHERE status='completed') AS completed,coalesce(sum(bytes_done) FILTER (WHERE status='completed'),0) AS secured_bytes,count(*) FILTER (WHERE status='failed' AND coalesce(metadata->>'_fca_outcome','')!='inaccessible') AS failed,coalesce(sum(greatest(size,0)) FILTER (WHERE status='failed' AND coalesce(metadata->>'_fca_outcome','')!='inaccessible'),0) AS failed_known_bytes,count(*) FILTER (WHERE metadata->>'_fca_outcome'='inaccessible' AND status!='completed') AS inaccessible,coalesce(sum(greatest(size,0)) FILTER (WHERE metadata->>'_fca_outcome'='inaccessible' AND status!='completed'),0) AS inaccessible_known_bytes,count(*) FILTER (WHERE status IN ('queued','running','pausing')) AS pending,count(*) FILTER (WHERE size<0) AS unknown_size FROM acquisition_files WHERE acquisition_id=%s",(job['id'],)).fetchone()
        ledger={key:int(value) for key,value in ledger.items()}
        manifest=directory/'Dateien.jsonl'; temp=directory/'Dateien.jsonl.tmp'
        if temp.is_symlink(): raise evidence.StorageError('Unsicheres Prüfprotokoll.')
        with open(temp,'w',encoding='utf-8') as handle:
            with conn.cursor(name='manifest') as cursor:
                cursor.itersize=1
                cursor.execute('SELECT source_id,relative_path,size,bytes_done,status,md5,sha256,attempts,reason,metadata FROM acquisition_files WHERE acquisition_id=%s ORDER BY id',(job['id'],))
                for row in cursor:
                    metadata=dict(row['metadata']); metadata.pop('payload',None); row['metadata']=metadata
                    metadata.setdefault('_fca_source_verification',{'status':'not_recorded','algorithms':[],
                                        'note':'Kein Quellhashvergleich für diesen Datensatz dokumentiert.'})
                    handle.write(json.dumps(row,ensure_ascii=False,default=str)+'\n')
            handle.flush(); os.fsync(handle.fileno())
        os.replace(temp,manifest)
        value={'sicherungs_id':str(job['id']),'fall':case,'bearbeiter':job['operator_initials'],
               'konto':dict(account,account_id=str(job['account_id']),kennung=current['account_identity']), 'ressourcen':current['resource_observations'], 'beginn':current['started_at'],'ende':current['ended_at'],
               'methode':('Rclone v1.75.2 iCloud-Webschnittstelle (nicht öffentliche Apple-API)' if account['provider']=='apple' else ('Offizielle Kalender-REST-API und OAuth 2.0 (lesend)' if job['category']=='calendar' else 'Offizielle REST-Inventarisierung, FCA OAuth 2.0/PKCE, Rclone v1.75.2 Dateitransport (lesend)')),
               'kategorien':['drive','photos'] if job['category']=='both' else [job['category']],'kategorie':job['category'],'umfang':job['scope_path'] or 'zugänglicher Standardbereich laut Anbieterdefinition',
               'status':status,'grund':reason,'dateien':ledger['completed'],'bytes':ledger['secured_bytes'],
               'uebertragene_bytes_einschliesslich_teiluebertragungen':current['bytes_done'],
               'umfangsbilanz':dict(ledger,inventory_complete=current['inventory_complete'],entire_account_complete=False,
                                    provider_inventory=current['resource_observations'].get('provider_inventory',{})),
               'datenbereiche':coverage(account['provider'],job['category'],current['inventory_complete']),
               'inventar_abgeschlossen':current['inventory_complete'],'einschraenkungen':current['limitations'],
               'manifest_sha256':evidence.sha256(manifest),'pruefung':'MD5 und SHA-256 lokal (historische Dateien ohne MD5 bis zur erneuten Prüfung gekennzeichnet), Größenprüfung; Anbieterprüfsumme sofern verfügbar. Keine kryptografische Herkunftsbestätigung.',
               'hinweis':'Lebendes Cloud-System, keine atomare Momentaufnahme. Nicht zugängliche oder außerhalb des gewählten Bereichs liegende Kategorien sind nicht enthalten.'}
        if account['provider']!='apple':
            from backend import oauth
            authorization=oauth.load(job['case_id'],job['account_id'])
            value['zugriffsrechte']={'angefordert':authorization.get('requested_scopes',[]),
                                    'vom_anbieter_gemeldet':authorization.get('scope','Nicht gemeldet; kein Nachweis vollständiger Rechte.')}
        evidence.atomic_json(directory/'Sicherungsbericht.json',value)

def coverage(provider,category,inventory_complete):
    selected='inventar_abgeschlossen' if inventory_complete else 'inventar_offen'
    if category=='calendar': return [{'bereich':'Kalender im gewählten Zeitraum' if provider=='microsoft' else 'Zugängliche Kalender','status':selected}]
    if provider=='google': return [{'bereich':'Meine Ablage','status':selected},{'bereich':'Mit mir geteilt','status':'nicht_untersucht'},{'bereich':'Shared Drives','status':'nicht_untersucht'},{'bereich':'Gelöschte Dateien und Versionshistorie','status':'nicht_unterstuetzt'}]
    if provider=='microsoft': return [{'bereich':'OneDrive-Standardlaufwerk','status':selected},{'bereich':'Weitere Drives und SharePoint-Bibliotheken','status':'nicht_untersucht'},{'bereich':'Verknüpfte und Paketobjekte sowie Versionshistorie','status':'nicht_unterstuetzt'}]
    return [{'bereich':name,'status':selected} for name in (['iCloud Drive','iCloud Fotos'] if category=='both' else ['iCloud Fotos' if category=='photos' else 'iCloud Drive'])]

def discover_files(job, adapter, config, cancel):
    identifier=job['id']
    def entries():
        if job['category']!='both':
            yield from adapter.inventory(job['category'],job['scope_path']);return
        for category,prefix in [('drive','iCloud Drive'),('photos','iCloud Fotos')]:
            for entry in adapter.inventory(category,''):
                yield {**entry,'id':category+':'+entry['id'],'path':prefix+'/'+entry['path'],
                       'metadata':{**entry['metadata'],'_fca_category':category,'_fca_source_id':entry['id']}}
    for entry in entries():
        require_memory()
        evidence.space(config['reserve_bytes'])
        if cancel.is_set() or not job_active(identifier) or STOP.is_set(): raise evidence.StorageError('Sicherung pausiert.')
        if entry.get('directory'):
            evidence.file_path(evidence.directory(job['directory']+'/Daten'),entry['path']+'/.fca-directory-check').parent.mkdir(exist_ok=True)
            # Directory metadata represented by the inventory sidecar below.
            d=evidence.directory(job['directory']+'/_FCA/Ordner')
            evidence.atomic_json(d/(__import__('hashlib').sha256(entry['id'].encode()).hexdigest()+'.json'),{'source_id':entry['id'],'path':entry['path'],'metadata':entry['metadata']})
            continue
        metadata=entry['metadata']
        if 'payload' in entry: metadata={**metadata,'payload':entry['payload']}
        with connect() as conn:
            conn.execute('INSERT INTO acquisition_files(acquisition_id,source_id,relative_path,metadata,size) VALUES (%s,%s,%s,%s,%s) ON CONFLICT(acquisition_id,source_id) DO NOTHING',
                         (identifier,entry['id'],entry['path'],Jsonb(metadata),entry['size']))
    with connect() as conn: conn.execute('UPDATE acquisitions SET inventory_complete=true,total_known=NOT EXISTS(SELECT 1 FROM acquisition_files WHERE acquisition_id=%s AND size<0),limitations=%s WHERE id=%s',(identifier,Jsonb(adapter.limits),identifier))

def run_job(identifier):
    last=deque(); cancel=threading.Event(); cancel.throttled_until=0
    job=None
    try:
        with connect() as conn:
            job=conn.execute('SELECT j.*,a.provider FROM acquisitions j JOIN cloud_accounts a ON a.id=j.account_id WHERE j.id=%s',(identifier,)).fetchone()
            config=settings(conn)
            last.append((time.monotonic(),int(job['bytes_done'])))
            if not allowed(conn,job): raise evidence.StorageError('Fallberechtigung wurde entzogen.')
            claimed=conn.execute("UPDATE acquisitions SET status='running',started_at=coalesce(started_at,now()),ended_at=NULL,reason=NULL,heartbeat=now() WHERE id=%s AND status='queued' RETURNING id",(identifier,)).fetchone()
            if not claimed: return
        evidence.space(config['reserve_bytes'])
        with open_provider(job['provider'],job['case_id'],job['account_id'],job['category']) as adapter:
            identity=adapter.identity()
            with connect() as conn: conn.execute('UPDATE acquisitions SET account_identity=%s,resource_observations=%s WHERE id=%s',(Jsonb(identity),Jsonb(resources()),identifier))
            # Revalidate completed files too: a restart cannot silently skip damaged evidence.
            with connect() as conn:
                conn.execute("UPDATE acquisition_files SET status='queued' WHERE acquisition_id=%s AND status IN ('running','failed')",(identifier,))
            after_id=0
            while True:
                with connect() as conn:
                    completed=conn.execute("SELECT id,relative_path,sha256,md5,bytes_done FROM acquisition_files WHERE acquisition_id=%s AND status='completed' AND id>%s ORDER BY id LIMIT 100",(identifier,after_id)).fetchall()
                if not completed: break
                for row in completed:
                    path=evidence.file_path(evidence.directory(job['directory']+'/Daten'),row['relative_path'])
                    hashes=evidence.file_hashes(path) if path.is_file() else (None,None)
                    if hashes[0]!=row['sha256'] or (row['md5'] and hashes[1]!=row['md5']) or not path.is_file() or path.stat().st_size!=row['bytes_done']:
                        with connect() as conn:
                            conn.execute("UPDATE acquisition_files SET status='failed',reason=%s WHERE id=%s",('Gesicherte Datei fehlt oder Prüfsumme stimmt nicht.',row['id']))
                            totals(conn,identifier,last)
                        raise ProviderError('Bereits gesicherte Datei fehlt oder wurde verändert. Prüflauf erforderlich; keine automatische Überschreibung.')
                    if not row['md5']:
                        with connect() as conn: conn.execute('UPDATE acquisition_files SET md5=%s WHERE id=%s',(hashes[1],row['id']))
                    after_id=row['id']
            # Inventory commits directly to the durable queue while bounded transfers consume it.
            # Exhausting the queue is only final after the producer has succeeded.
            with ThreadPoolExecutor(max_workers=1) as discovery_pool:
                inventory=discovery_pool.submit(discover_files,job,adapter,config,cancel) if not job['inventory_complete'] else None
                with ThreadPoolExecutor(max_workers=16) as transfer_pool:
                    futures={};previous_limit=None
                    try:
                        while True:
                            inventory_finished=inventory is None or inventory.done()
                            if inventory_finished and inventory is not None: inventory.result()
                            if not job_active(identifier) or STOP.is_set(): raise evidence.StorageError('Sicherung unterbrochen.')
                            for future in list(futures):
                                if not future.done(): continue
                                row=futures.pop(future)
                                try: future.result()
                                except evidence.StorageError: raise
                                except AuthenticationRequired: raise
                                except Exception as error:
                                    reason=str(error) if isinstance(error,ProviderError) else 'Datei konnte nicht sicher übernommen werden.'
                                    with connect() as conn: conn.execute("UPDATE acquisition_files SET status='failed',reason=%s,metadata=metadata || %s WHERE id=%s",(reason,Jsonb({'_fca_outcome':getattr(error,'outcome','transfer_failed')}),row['id']))
                            with connect() as conn:
                                config=settings(conn)
                                if hasattr(adapter,'coverage'):
                                    conn.execute('UPDATE acquisitions SET resource_observations=resource_observations || %s WHERE id=%s',(Jsonb({'provider_inventory':adapter.coverage}),identifier))
                                limited=time.monotonic()<max(cancel.throttled_until,getattr(adapter,'throttled_until',0))
                                limit=1 if limited else config['file_parallelism']
                                if limit!=previous_limit:
                                    conn.execute("UPDATE acquisitions SET resource_observations=resource_observations || %s WHERE id=%s",(Jsonb({'transfer_limit':limit}),identifier))
                                    previous_limit=limit
                                slots=max(0,limit-len(futures))
                                pending=[row['id'] for row in futures.values()]
                                rows=conn.execute("SELECT * FROM acquisition_files WHERE acquisition_id=%s AND status='queued' AND NOT (id=ANY(%s)) ORDER BY id LIMIT %s",(identifier,pending,slots)).fetchall() if slots else []
                            for row in rows:
                                futures[transfer_pool.submit(run_file,job,row,adapter,config['reserve_bytes'],cancel)]=row
                            # A large file does not hold up refilling other available slots.
                            if not futures and inventory_finished and not rows: break
                            if futures: wait(futures,timeout=1,return_when=FIRST_COMPLETED)
                            else: cancel.wait(.25)
                            with connect() as conn: totals(conn,identifier,last)
                    finally:
                        cancel.set() # stop sibling transfers and producer before closing the provider
            with connect() as conn:
                failed=conn.execute("SELECT count(*) AS n FROM acquisition_files WHERE acquisition_id=%s AND status!='completed'",(identifier,)).fetchone()['n']
                current=conn.execute('SELECT limitations FROM acquisitions WHERE id=%s',(identifier,)).fetchone()
                status='incomplete' if failed or current['limitations'] else 'completed'
                totals(conn,identifier,last)
                conn.execute('UPDATE acquisitions SET ended_at=now(),speed=0 WHERE id=%s',(identifier,))
            report(job,status)
            with connect() as conn:
                conn.execute('UPDATE acquisitions SET status=%s WHERE id=%s',(status,identifier))
                audit(conn,None,'acquisition_'+status,job['case_id'],job['operator_initials'],{'acquisition_id':str(identifier)})
    except Exception as error:
        if os.environ.get('FCA_TEST_RERAISE')=='1' and os.environ.get('FCA_DB_NAME')=='fca_test_phase1' and not isinstance(error,(evidence.StorageError,ProviderError)):
            raise
        status='paused' if isinstance(error,evidence.StorageError) else 'failed'
        reason=str(error) if isinstance(error,(evidence.StorageError,ProviderError)) else 'Sicherung fehlgeschlagen. Fallprotokoll und Datenträger prüfen.'
        with connect() as conn:
            current=conn.execute('SELECT status FROM acquisitions WHERE id=%s FOR UPDATE',(identifier,)).fetchone()
            if isinstance(error,evidence.StorageError) and current['status']=='pausing':
                reason='Pause vom Benutzer angefordert.'
            if status=='paused' and STOP.is_set() and current['status']=='running' and allowed(conn,job):
                status='queued'
                reason='Wird nach Neustart fortgesetzt.'
            totals(conn,identifier,last)
            if hasattr(error,'resource_observation'):
                conn.execute('UPDATE acquisitions SET resource_observations=resource_observations || %s WHERE id=%s',(Jsonb({'last_memory_pressure':error.resource_observation}),identifier))
            if 'adapter' in locals() and hasattr(adapter,'coverage'):
                conn.execute('UPDATE acquisitions SET resource_observations=resource_observations || %s WHERE id=%s',(Jsonb({'provider_inventory':adapter.coverage}),identifier))
            conn.execute("UPDATE acquisitions SET status=%s,reason=%s,ended_at=CASE WHEN %s='queued' THEN NULL ELSE now() END,speed=0 WHERE id=%s",(status,reason,status,identifier))
            if job: audit(conn,None,'acquisition_'+status,job['case_id'],job['operator_initials'],{'acquisition_id':str(identifier),'reason':reason})
        if job:
            try: report(job,status,reason)
            except Exception: pass # DB records retain all evidence if disk is unavailable/full.

def main():
    os.umask(0o077)
    signal.signal(signal.SIGTERM,lambda *_:STOP.set())
    signal.signal(signal.SIGINT,lambda *_:STOP.set())
    # Session advisory lock means restarting the coordinator cannot duplicate consumers.
    with connect() as leader:
        if not leader.execute('SELECT pg_try_advisory_lock(47203106) AS ok').fetchone()['ok']: return
        leader.commit()
        with connect() as conn:
            conn.execute("UPDATE acquisitions SET status=CASE WHEN status='pausing' THEN 'paused' ELSE 'queued' END,speed=0 WHERE status IN ('running','pausing')")
            conn.execute("UPDATE acquisition_files SET status='queued' WHERE status IN ('running','pausing')")
        with ThreadPoolExecutor(max_workers=8) as pool:
            active={}
            while not STOP.is_set():
                leader.execute('SELECT 1'); leader.commit()
                for identifier,future in list(active.items()):
                    if not future.done():continue
                    # An unexpected task failure must not strand the UI in running/pausing.
                    with connect() as conn:
                        stranded=conn.execute("UPDATE acquisitions SET status=CASE WHEN status='pausing' THEN 'paused' ELSE 'failed' END,reason='Verarbeitung beendet. Fortsetzen ist möglich.',speed=0,ended_at=now() WHERE id=%s AND status IN ('running','pausing') RETURNING case_id,operator_initials,status",(identifier,)).fetchone()
                        if stranded:audit(conn,None,'acquisition_'+stranded['status'],stranded['case_id'],stranded['operator_initials'],{'acquisition_id':str(identifier),'reason':'Auftrag sicher zur Wiederaufnahme freigegeben.'})
                    del active[identifier]
                with connect() as conn:
                    config=settings(conn)
                    if len(active)<config['account_parallelism']:
                        jobs=conn.execute("SELECT id FROM acquisitions WHERE status='queued' ORDER BY created_at LIMIT 20").fetchall()
                        for row in jobs:
                            if row['id'] not in active:
                                active[row['id']]=pool.submit(run_job,row['id'])
                                if len(active)>=config['account_parallelism']: break
                STOP.wait(1)

if __name__=='__main__': main()
