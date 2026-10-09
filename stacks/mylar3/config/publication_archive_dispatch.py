"""Durable review queue; authenticated owner/operation keys never mint reader custody.

The root-scoped child consumes exact native/reader objects. HTTP dispatch reports
only a queue result; a saved receipt is never reconstructed into a capability.
"""
import importlib
import json
import os
from pathlib import Path
import re
import time
from mylar import publication_archive_owned as o
from mylar import publication_archive_reader as reader
from mylar import publication_archive_adoption as adoption

KIND='archive_repair_dispatch';MAX_JOBS=256

def _store(controller):
    m=importlib.import_module('mylar.workflow_store')
    o.check(Path(m.__file__)==Path('/app/mylar3/mylar/workflow_store.py'),'installed-workflow-store')
    return m.Store(controller.root,existing_only=True)

def dispatch(controller,writer,value):
    modules=o.sdk();g=modules[2];o.writer_pair(controller,writer,modules)
    o.check(type(value) is dict and set(value)=={'version','action','owner','operation_id'} and type(value['version']) is int and value['version']==1,'repair-request-shape')
    owner=g.exact_owner(value['owner']);key=value['operation_id'];o.check(type(key) is str and re.fullmatch('[0-9a-f]{64}',key),'repair-operation-id')
    o.check(value['action'] in ('request-archive-repair-adoption','archive-repair-adoption-status'),'repair-action')
    deadline=time.monotonic()+g.TIMEOUT;nodes=o.ancestors([controller.database,controller.native_database]);census,records=g.media_snapshot(controller.database,writer.root/'publication-v1.json')
    native,claims,more=o.catalog(controller,owner,g,deadline);o.merge_nodes(nodes,more)
    store=_store(controller);old=store.get(KIND,key)
    if value['action']=='request-archive-repair-adoption':
        o.check(old is None,'repair-queue-exclusive-no-replay');o.check(len(store.all(KIND,MAX_JOBS+1))<MAX_JOBS,'repair-queue-count')
        row={'version':1,'kind':KIND,'operation_id':key,'owner':owner,'phase':'queued-review','census':census,'catalog':native,'reader_custody':None,'mutation_authority':False,'publication_acceptance':False}
        # Source/census/claim revalidation precedes the existing-only transaction.
        o.check(o.catalog(controller,owner,g,deadline)[0]==native and g.media_snapshot(controller.database,writer.root/'publication-v1.json')==(census,records),'repair-queue-current')
        o.check(store.create(KIND,key,row),'repair-queue-exclusive')
        old=row
    else:
        o.check(old is not None and type(old) is dict and old.get('owner')==owner and old.get('operation_id')==key and old.get('kind')==KIND,'repair-queue-exact-status')
    after=o.fact(controller.database,256*1024**2,deadline)
    o.check(store.get(KIND,key)==old and o.fact(controller.database,256*1024**2,deadline)==after,'repair-queue-readback')
    # No arbitrary exception text, source path, or capability leaves this adapter.
    result={'version':1,'operation_id':key,'owner':owner,'outcome':old['phase'],'root_scoped_child_required':True,'reader_preservation_verified':False,'mutation_authority':False,'publication_acceptance':False}
    for p,v in claims.items():o.check(g._claim_identity(p)==v,'repair-queue-claim')
    g.ordinary_purpose(writer)
    for db in (controller.database,controller.native_database):
        for suffix in ('-wal','-shm','-journal'):
            try:os.lstat(str(db)+suffix)
            except FileNotFoundError:continue
            raise o.Held('repair-queue-companion')
    for p,v in claims.items():
        try:s=os.lstat(p)
        except FileNotFoundError:o.check(v is None,'repair-queue-absent-claim');continue
        import stat
        o.check((s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,None if stat.S_ISDIR(s.st_mode) else s.st_nlink)==v,'repair-queue-terminal-claim')
    for name in (*adoption.OTHER_PENDING,adoption.PENDING,adoption.TERMINAL):
        try:os.lstat(writer.root/name)
        except FileNotFoundError:continue
        raise o.Held('repair-queue-terminal-purpose')
    reader.direct({controller.database:after['signature9'],controller.native_database:native['file']['signature9']},nodes,set())
    return result

def consume_existing(preparation,lease,retention_root):
    """Actual root-scoped child: no path or custody is accepted from the API row."""
    cap=adoption.prepare_existing(preparation,lease,retention_root);cap.install();return cap

def verify_existing(cap):
    o.check(type(cap) is adoption.RepairAdoption,'exact-repair-consumer');cap.close();return cap.binding

def reverse_existing(cap):
    o.check(type(cap) is adoption.RepairAdoption,'exact-repair-consumer');return cap.reverse()

def worker_request(worker,owner,operation_id):
    """Network dispatch after public worker's remote-unlocked check, no source input.

    Intent is written before HTTP. Exceptions retain dispatching-review; this
    function refuses a repeated dispatch even if the prior response was lost.
    """
    from conversion_handoff import remote_unlocked,api
    remote_unlocked(worker)
    key=operation_id;o.check(type(key) is str and re.fullmatch('[0-9a-f]{64}',key),'repair-operation-id')
    journal=worker.state/'archive-repair-requests';o.canonical(journal)
    o.check(journal.stat().st_uid==os.geteuid() and (journal.stat().st_mode&0o777)==0o700,'repair-worker-private-journal')
    p=journal/(key+'.json');raw=o.compact({'version':1,'operation_id':key,'owner':owner,'phase':'dispatching-review','mutation_authority':False})
    o.write(p,raw,o.stat5(os.lstat(journal)))
    # A timeout, HTTP success, or response body is never a mutation grant.
    answer=api(worker,'publicationControl',request=json.dumps({'version':1,'action':'request-archive-repair-adoption','owner':owner,'operation_id':key}))
    o.check(type(answer) is dict and answer.get('outcome')=='queued-review' and answer.get('owner')==owner and answer.get('operation_id')==key and answer.get('mutation_authority') is False,'repair-queue-HTTP-ack')
    return {'version':1,'operation_id':key,'outcome':'queued-review','mutation_authority':False,'publication_acceptance':False}


def worker_status(worker,owner,operation_id):
    from conversion_handoff import remote_unlocked,api
    remote_unlocked(worker)
    o.check(type(operation_id) is str and re.fullmatch('[0-9a-f]{64}',operation_id),'repair-operation-id')
    return api(worker,'publicationControl',request=json.dumps({'version':1,'action':'archive-repair-adoption-status','owner':owner,'operation_id':operation_id}))


def complete_existing(cap):
    o.check(type(cap) is adoption.RepairAdoption,'exact-repair-consumer');return cap.complete()
