"""Live retained finalization and factual durable status, without import grants.

Only live owning events finalize. Restart reconciliation can observe exact durable
state; it cannot recreate an event, replay a mutation or authorize reader resume.
Direct kernel entry remains disabled without the authenticated API admission.
"""
from contextlib import closing
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
import weakref

from mylar import publication_archive_owned as o
from mylar import publication_retained_delivery as r

ENABLED=False
RECORD_KIND='retained_delivery_final'
MEMBER_PHASE='retained-accepted'
_FINALS={}
_RECEIPTS=weakref.WeakKeyDictionary()
_RECEIPT_ADMISSIONS=weakref.WeakKeyDictionary()


def _parts(v):
    return (dict(v['files9']),dict(v['nodes5']),tuple(v['absent']),dict(v['namespaces']),dict(v['claims']))


def _checked(packet,files,*,admission):
    o.check(packet.get('api_admission') is admission,'retained-original-packet-admission')
    if admission is not None:
        from mylar import publication_retained_api as api
        api.check_admission(admission,packet['controller'],packet['writer'],packet['request'])
    o.check(time.monotonic()<packet['deadline'],'retained-finalize-deadline')
    try:o.writer_pair(packet['controller'],packet['writer'],packet['modules'])
    except packet['modules'][2].Unavailable:raise o.Held('retained-finalize-Writer-unavailable') from None
    for path,digest in packet['hashes'].items():
        raw=o.read_checked(path,list(files[path]),256*1024**2,packet['deadline'])
        o.check(hashlib.sha256(raw).hexdigest()==digest,'retained-finalize-bytes')
    if admission is not None:
        api.check_admission(admission,packet['controller'],packet['writer'],packet['request'])
    if packet.get('api_admission') is not admission:raise o.Held('retained-final-original-packet-admission')


def _result(packet):
    return {'version':1,'outcome':'fresh-retained-backend-finalized','token':packet['token'],
            'record_kind':RECORD_KIND,'record_sha256':packet['record_sha'],
            'committed':copy.deepcopy(packet['committed']),
            'historical_import_ack':False,'ordinary_import_grant':False,'cleanup_grant':False,
            'mutation_authority':False,'publication_acceptance':False,
            'reader_index_acceptance':False,'automatic_replay':False}


class RetainedFinalization:
    def __init__(self,*args,**kwargs):raise o.Held('retained-finalizer-owning-factory-only')
    def encode(self,handler,source_frame):return _encode_response(self,handler,source_frame)
    def close(self,envelope):return _close_response(self,envelope)
    def finish(self,envelope):return _finish_response(self,envelope)
    def observe(self):
        packet=_RECEIPTS.get(self)
        o.check(type(self) is RetainedFinalization and packet is not None,'retained-finalizer-live-receipt')
        return status_existing(packet['controller'],packet['writer'],packet['request'],admission=_receipt_admission(self,packet))


def _retain_receipt(packet,admission):
    o.check(packet.get('api_admission') is admission,'retained-receipt-original-admission')
    receipt=object.__new__(RetainedFinalization);_RECEIPTS[receipt]=packet
    _RECEIPT_ADMISSIONS[receipt]=(packet,admission,_RECEIPTS,_RECEIPT_ADMISSIONS)
    return receipt


def _receipt_admission(receipt,packet):
    original=_RECEIPT_ADMISSIONS.get(receipt)
    o.check(original is not None and original[0] is packet and _RECEIPTS.get(receipt) is packet
            and original[2] is _RECEIPTS and original[3] is _RECEIPT_ADMISSIONS
            and packet.get('api_admission') is original[1],'retained-receipt-original-admission')
    return original[1]


def finalize(cap,*,response_handler=None,response_frame=None):
    source_files={};source_hashes={};source_nodes={}
    # Capture BOTH original leaves and first ancestors before any source reads.
    # Duplicate ancestors never replace an earlier admitted primitive vector.
    for name in (__file__,r.__file__):
        path=Path(name)
        for parent in path.parents:
            z=os.lstat(parent);stamp=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
            key=str(parent)
            if key in source_nodes and source_nodes[key]!=stamp:raise o.Held('retained-finalize-first-source-node')
            if key not in source_nodes:source_nodes[key]=stamp
        z=os.lstat(path);stamp=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
        key=str(path)
        if key in source_files and source_files[key]!=stamp:raise o.Held('retained-finalize-first-source-file')
        if key not in source_files:source_files[key]=stamp
    for name,stamp in tuple(source_files.items()):
        fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            z=os.fstat(fd)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise o.Held('retained-finalize-source-FD')
            raw=b''
            while block:=os.read(fd,1048576):
                raw+=block
                if len(raw)>1048576:raise o.Held('retained-finalize-source-bound')
            z=os.fstat(fd)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise o.Held('retained-finalize-source-FD-final')
        finally:os.close(fd)
        z=os.lstat(name)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise o.Held('retained-finalize-source-path-final')
        source_hashes[name]=hashlib.sha256(raw).hexdigest()
    # Close the complete original source frame after the last stream/hash.
    for name,stamp in source_files.items():
        z=os.lstat(name)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise o.Held('retained-finalize-source-frame-file')
    for name,stamp in source_nodes.items():
        z=os.lstat(name)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise o.Held('retained-finalize-source-frame-node')
    o.check(type(cap) is r.RetainedDeliveryAcceptance,'retained-finalize-live-type')
    original_core=r._CORES.get(cap)
    admission=None if original_core is None else r._core_admission(original_core)
    if admission is not None:
        from mylar import publication_retained_api as api
        api.consume_admission(admission,original_core['controller'],original_core['writer'],original_core['request'],'finalize')
    else:o.check(ENABLED,'retained-finalizer-default-disabled')
    packet=r._begin_finalization(cap)
    controller=packet['controller'];writer=packet['writer'];event=packet['event']
    wb=event[7];cb=event[8]
    files,nodes,absent,namespaces,claims=_parts(packet['vectors'])
    originals=copy.deepcopy(packet['vectors'])
    for path,stamp in source_files.items():
        if path in files and tuple(files[path])!=stamp:raise o.Held('retained-finalize-source-conflict')
        files[path]=stamp;packet['hashes'][path]=source_hashes[path]
    for path,stamp in source_nodes.items():
        if path in nodes and tuple(nodes[path])!=stamp:raise o.Held('retained-finalize-node-conflict')
        nodes[path]=stamp
    packet['vectors']['files9']=[[p,list(v)] for p,v in files.items()]
    packet['vectors']['nodes5']=[[p,list(v)] for p,v in nodes.items()]
    _checked(packet,dict(files),admission=admission)
    # This verifies the actual producer event before the sole workflow change.
    r.verify_ack(controller,writer,packet['request'],
                 {'path':event[2][0],'sha256':event[2][1],'signature9':list(event[2][2])})
    before=r._sql(controller.database,tuple(files[str(controller.database)]))
    value=packet['request'];token=packet['token']
    key=(str(controller.root),token)
    o.check(key not in _FINALS,'retained-finalizer-no-replay')
    rows=before['rows'].get('records',[])
    selected=[json.loads(row) for row in rows if json.loads(row)[:2]==['pack',value['pack_id']]]
    o.check(len(selected)==1,'retained-finalize-pack-row')
    prior=selected[0];capture=json.loads(prior[2])
    o.check(capture.get('id')==value['pack_id'] and capture.get('ddl_id')==value['ddl_id']
            and capture.get('source_generation')==value['source_generation']
            and not capture.get('cleanup_started') and not capture.get('cleanup_complete'),
            'retained-finalize-original-capture')
    members=capture.get('members')
    o.check(type(members) is list and len(members)<=2000,'retained-finalize-members')
    matching=[m for m in members if m.get('id')==value['member_id']]
    owner=value['owner']
    o.check(len(matching)==1,'retained-finalize-exact-member')
    member=matching[0]
    o.check(member.get('kind')==('annual' if owner['table']=='annuals' else 'issue')
            and member.get('issueid')==owner['issueid']
            and member.get('comicid')==owner['parentcomicid']
            and member.get('releasecomicid')==owner['releasecomicid']
            and member.get('phase') in ('review','ready','submitted','confirmed')
            and not member.get('ordinary_import_token') and not member.get('retained_finalization'),
            'retained-finalize-member-owner')
    ack=json.loads(o.read_checked(event[2][0],list(event[2][2]),16*1024**2,packet['deadline']))
    target=ack['target'];source=ack['source']
    o.check(member.get('destination',target)==target
            and member.get('destination_sha256',value['target_sha256'])==value['target_sha256']
            and member.get('sha256',value['source_sha256'])==value['source_sha256'],
            'retained-finalize-member-original-payload')
    changed=copy.deepcopy(capture)
    fresh=next(m for m in changed['members'] if m['id']==value['member_id'])
    fresh.update(phase=MEMBER_PHASE,retained_finalization=token,
                 destination=target,destination_sha256=value['target_sha256'])
    # Pack remains review; ordinary confirmations and cleanup are unchanged.
    changed['phase']='review'
    record={'version':2,'kind':'fresh-retained-backend-finalization','token':token,
            'request':value,'source':source,'target':target,'original_event':{'ack':list(event[2]),'intent':list(event[3]),'issued':list(event[4])},
            'original_vectors':originals,'pack_before':capture,'pack_after':changed,'pack_before_row':prior,
            'workflow_before_sha256':o.digest(before),
            'historical_import_ack':False,'ordinary_import_grant':False,'cleanup_grant':False,
            'mutation_authority':False,'publication_acceptance':False,
            'reader_index_acceptance':False,'automatic_replay':False}
    raw=o.compact(record).decode();new_value=o.compact(changed).decode()
    # Copies retain the actual owning preimage; never recover from a saved record.
    packet['transition_bytes']=o.compact(dict(version=1,kind='retained-pack-two-row-transition',
        request=value,native_data_root=str(controller.root),record_bytes=raw,
        pack_before_row=prior,pack_after_row=[prior[0],prior[1],new_value,prior[3]],
        workflow_before=before,original_vectors=originals))
    o.check(len(packet['transition_bytes'])<=1024*1024,'retained-worker-export-precommit-bound')
    expected_sql=copy.deepcopy(before)
    replacement=prior.copy();replacement[2]=new_value
    # Preserve updated column: only exact member/value mutation is admitted.
    expected_sql['rows']['records'].remove(o.compact(prior).decode())
    expected_sql['rows']['records'].append(o.compact(replacement).decode())
    expected_sql['rows']['records'].append(o.compact([RECORD_KIND,token,raw,0.0]).decode())
    expected_sql['rows']['records'].sort()
    result_record_sha=hashlib.sha256(raw.encode()).hexdigest()
    # Budget the actual API encoding before the sole workflow transaction.
    if response_handler is not None or response_frame is not None:
        _precommit_response_budget(packet,response_handler,response_frame,result_record_sha,files,nodes)
    # All callbacks precede raw closure and the exact fixed SQL transaction.
    _checked(packet,dict(files),admission=admission)
    for path,names in namespaces.items():
        if tuple(sorted(os.listdir(path)))!=tuple(names):raise o.Held('retained-finalize-census')
    for path,expected in nodes.items():
        s=os.lstat(path)
        if (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid)!=tuple(expected):raise o.Held('retained-finalize-node')
    for path,expected in files.items():
        s=os.lstat(path)
        if (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink)!=tuple(expected):raise o.Held('retained-finalize-file')
    for path in absent:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise o.Held('retained-finalize-absence')
    for path,expected in claims.items():
        try:s=os.lstat(path)
        except FileNotFoundError:
            if expected is not None:raise o.Held('retained-finalize-claim')
            continue
        actual=(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,None if s.st_mode&0o170000==0o040000 else s.st_nlink)
        if actual!=(None if expected is None else tuple(expected)):raise o.Held('retained-finalize-claim')
    if (writer.root,writer.lock,writer.pending,writer.tagger_pending,writer.release_pending,
            tuple(writer.lock_identity),tuple(writer.root_identity),writer.local)!=wb:raise o.Held('retained-finalize-Writer')
    if (controller.root,controller.database,controller.native_database,controller.writer_root,
            tuple(controller.roots),controller.tool_root)!=cb:raise o.Held('retained-finalize-Controller')
    if getattr(writer.local[1],'depth',0)<=0 or any(getattr(writer.local[1],k,False) for k in
            ('allow_pending','allow_tagger_pending','allow_release_pending')):raise o.Held('retained-finalize-purpose')
    with closing(sqlite3.connect(controller.database)) as db:
        db.execute('PRAGMA trusted_schema=OFF');db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
        o.check(db.execute('SELECT kind,key,value,updated FROM records WHERE kind=? AND key=?',
                ('pack',value['pack_id'])).fetchall()==[tuple(prior)],'retained-finalize-CAS')
        o.check(not db.execute('SELECT 1 FROM records WHERE kind=? AND key=?',(RECORD_KIND,token)).fetchall(),
                'retained-finalize-reserved-record')
        count=db.execute('UPDATE records SET value=? WHERE kind=? AND key=? AND value=? AND updated=?',
                         (new_value,'pack',value['pack_id'],prior[2],prior[3])).rowcount
        o.check(count==1,'retained-finalize-CAS')
        db.execute('INSERT INTO records(kind,key,value,updated) VALUES(?,?,?,?)',(RECORD_KIND,token,raw,0.0))
        db.commit()
    # Only this owning SQL diff may advance workflow identity; never event vectors.
    original=tuple(files[str(controller.database)])
    now=tuple(o.signature(controller.database))
    if 'response_stat_ceiling' in packet:
        o.check(all(type(v) is int and abs(v)<=packet['response_stat_ceiling'] for v in now),'retained-committed-stat-wire-width')
    o.check(now[:2]==original[:2] and now[5:]==original[5:],'retained-finalize-workflow-identity')
    o.check(r._sql(controller.database,now)==expected_sql,'retained-finalize-complete-SQL-diff')
    content=o.read_checked(controller.database,list(now),256*1024**2,packet['deadline'])
    digest=hashlib.sha256(content).hexdigest()
    files[str(controller.database)]=now
    packet['hashes'][str(controller.database)]=digest
    packet['vectors']['files9']=[[p,list(s)] for p,s in files.items()]
    packet.update(record_sha=result_record_sha,expected_sql=expected_sql,
                  committed={'path':str(controller.database),'sha256':digest,'signature9':list(now)},
                  producer_pid=os.getpid(),thread=threading.get_ident())
    frozen=dict(packet);frozen['vectors_bytes']=o.compact(packet['vectors'])
    frozen['hashes']=dict(packet['hashes']);frozen['expected_sql_bytes']=o.compact(expected_sql)
    frozen.pop('core',None);frozen.pop('vectors',None);frozen.pop('expected_sql',None)
    _result(packet)  # Serialize/copy before the final raw proof boundary.
    _checked(packet,dict(files),admission=admission)
    for path,names in namespaces.items():
        if tuple(sorted(os.listdir(path)))!=tuple(names):raise o.Held('retained-finalize-census')
    for path,expected in nodes.items():
        s=os.lstat(path)
        if (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid)!=tuple(expected):raise o.Held('retained-finalize-node')
    for path,expected in files.items():
        s=os.lstat(path)
        if (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink)!=tuple(expected):raise o.Held('retained-finalize-file')
    for path in absent:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise o.Held('retained-finalize-absence')
    for path,expected in claims.items():
        try:s=os.lstat(path)
        except FileNotFoundError:
            if expected is not None:raise o.Held('retained-finalize-claim')
            continue
        actual=(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,None if s.st_mode&0o170000==0o040000 else s.st_nlink)
        if actual!=(None if expected is None else tuple(expected)):raise o.Held('retained-finalize-claim')
    if (writer.root,writer.lock,writer.pending,writer.tagger_pending,writer.release_pending,
            tuple(writer.lock_identity),tuple(writer.root_identity),writer.local)!=wb:raise o.Held('retained-finalize-Writer')
    if (controller.root,controller.database,controller.native_database,controller.writer_root,
            tuple(controller.roots),controller.tool_root)!=cb:raise o.Held('retained-finalize-Controller')
    if getattr(writer.local[1],'depth',0)<=0 or any(getattr(writer.local[1],k,False) for k in
            ('allow_pending','allow_tagger_pending','allow_release_pending')):raise o.Held('retained-finalize-purpose')
    # Registry publication occurs only after all exact committed originals close.
    _FINALS[key]=frozen
    packet['core']['phase']='finalized'
    return _retain_receipt(frozen,admission)


def status_existing(controller,writer,value,*,admission=None):
    if admission is not None:
        from mylar import publication_retained_api as api
        api.check_admission(admission,controller,writer,value)
    else:o.check(ENABLED,'retained-finalizer-default-disabled')
    value=r.request(value)
    token=hashlib.sha256((value['ddl_id']+'\0'+value['pack_id']+'\0'+value['member_id']).encode()).hexdigest()
    original=_FINALS.get((str(controller.root),token))
    o.check(original is not None and original['producer_pid']==os.getpid()
            and original['request']==value,
            'retained-finalizer-original-commit-required')
    packet=dict(original);packet['hashes']=dict(original['hashes']);packet['api_admission']=admission
    event=packet['event'];wb=event[7];cb=event[8]
    files,nodes,absent,namespaces,claims=_parts(json.loads(original['vectors_bytes']))
    o.check(r._writer_binding(writer)==wb and r._controller_binding(controller)==cb,'retained-finalizer-bindings')
    packet['controller']=controller;packet['writer']=writer
    _checked(packet,dict(files),admission=admission)
    o.check(o.compact(r._sql(controller.database,tuple(files[str(controller.database)])))
            ==original['expected_sql_bytes'],'retained-finalizer-original-committed-SQL')
    answer=_result(packet)
    for path,names in namespaces.items():
        if tuple(sorted(os.listdir(path)))!=tuple(names):raise o.Held('retained-finalize-census')
    for path,expected in nodes.items():
        s=os.lstat(path)
        if (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid)!=tuple(expected):raise o.Held('retained-finalize-node')
    for path,expected in files.items():
        s=os.lstat(path)
        if (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink)!=tuple(expected):raise o.Held('retained-finalize-file')
    for path in absent:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise o.Held('retained-finalize-absence')
    for path,expected in claims.items():
        try:s=os.lstat(path)
        except FileNotFoundError:
            if expected is not None:raise o.Held('retained-finalize-claim')
            continue
        actual=(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,None if s.st_mode&0o170000==0o040000 else s.st_nlink)
        if actual!=(None if expected is None else tuple(expected)):raise o.Held('retained-finalize-claim')
    if (writer.root,writer.lock,writer.pending,writer.tagger_pending,writer.release_pending,
            tuple(writer.lock_identity),tuple(writer.root_identity),writer.local)!=wb:raise o.Held('retained-finalize-Writer')
    if (controller.root,controller.database,controller.native_database,controller.writer_root,
            tuple(controller.roots),controller.tool_root)!=cb:raise o.Held('retained-finalize-Controller')
    if getattr(writer.local[1],'depth',0)<=0 or any(getattr(writer.local[1],k,False) for k in
            ('allow_pending','allow_tagger_pending','allow_release_pending')):raise o.Held('retained-finalize-purpose')
    return answer


# Typed factual response custody. These registries never hydrate saved JSON.
_SOURCE_FRAMES=weakref.WeakKeyDictionary()
_HTTP=weakref.WeakKeyDictionary()
_HTTP_SEALS=weakref.WeakKeyDictionary()

class ResponseSources:
    def __init__(self,*args,**kwargs):raise o.Held('retained-response-source-factory-only')


def response_sources():
    from mylar import api,native_writers,publication_retained_api
    import mylar
    serializer=api.Api._successResponse;serializer_code=serializer.__code__
    config=(mylar.DATA_DIR,mylar.CONFIG.DESTINATION_DIR,mylar.CONFIG.DDL_LOCATION,mylar.CONFIG.API_ENABLED,mylar.CONFIG.API_KEY)
    paths=[Path(module.__file__) for module in (api,native_writers,publication_retained_api,r)] + [Path(__file__)]
    files={};nodes={};hashes={}
    root=Path(__file__).parent
    for path in paths:
        o.check(path.parent==root,'retained-response-canonical-source')
        for parent in path.parents:
            z=os.lstat(parent);stamp=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
            o.check(stamp[2]&0o170000==0o040000,'retained-response-source-node')
            o.check(str(parent) not in nodes or nodes[str(parent)]==stamp,'retained-response-source-conflict')
            nodes.setdefault(str(parent),stamp)
        z=os.lstat(path);stamp=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
        o.check(stamp[5]&0o170000==0o100000 and stamp[8]==1,'retained-response-source-leaf')
        o.check(str(path) not in files or files[str(path)]==stamp,'retained-response-source-conflict')
        files.setdefault(str(path),stamp)
    deadline=time.monotonic()+120
    for path,stamp in files.items():
        raw=o.read_checked(Path(path),list(stamp),1048576,deadline);hashes[path]=hashlib.sha256(raw).hexdigest()
    frame={'files9':[[p,list(s)] for p,s in files.items()],'nodes5':[[p,list(s)] for p,s in nodes.items()],
           'absent':[],'claims':[],'namespaces':[]}
    encoded=o.compact(frame);obj=object.__new__(ResponseSources)
    _response_raw(frame)
    _SOURCE_FRAMES[obj]=(os.getpid(),threading.get_ident(),deadline,encoded,dict(hashes),config,serializer,serializer_code)
    return obj


def response_existing(controller,writer,value,*,admission=None):
    checked=r.request(value)
    key=(str(controller.root),hashlib.sha256((checked['ddl_id']+'\0'+checked['pack_id']+'\0'+checked['member_id']).encode()).hexdigest())
    if key not in _FINALS:return durable_reconcile(controller,writer,checked,admission=admission)
    status_existing(controller,writer,value,admission=admission)
    value=r.request(value)
    token=hashlib.sha256((value['ddl_id']+'\0'+value['pack_id']+'\0'+value['member_id']).encode()).hexdigest()
    original=_FINALS.get((str(controller.root),token))
    o.check(original is not None and original['producer_pid']==os.getpid() and original['request']==value,
            'retained-response-original-commit')
    # Only an already published original commit can issue this passive receipt.
    packet=dict(original);packet['controller']=controller;packet['writer']=writer;packet['api_admission']=admission
    return _retain_receipt(packet,admission)


def _response_raw(frame):
    for path,names in frame['namespaces']:
        if tuple(sorted(os.listdir(path)))!=tuple(names):raise o.Held('retained-response-namespace')
    for path,expected in frame['nodes5']:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(expected):raise o.Held('retained-response-node')
    for path,expected in frame['files9']:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(expected):raise o.Held('retained-response-file')
    for path in frame['absent']:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise o.Held('retained-response-absence')
    for path,expected in frame['claims']:
        try:z=os.lstat(path)
        except FileNotFoundError:
            if expected is not None:raise o.Held('retained-response-claim')
            continue
        actual=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)
        if actual!=(None if expected is None else tuple(expected)):raise o.Held('retained-response-claim')


def _encode_response(receipt,handler,source_frame):
    from mylar import api,publication_guard as g
    o.check(type(receipt) is RetainedFinalization and type(source_frame) is ResponseSources,'retained-response-exact-types')
    packet=_RECEIPTS.get(receipt);source=_SOURCE_FRAMES.pop(source_frame,None)
    o.check(type(receipt) is RetainedFinalization and packet is not None and receipt not in _HTTP
            and type(source_frame) is ResponseSources and source is not None
            and source[:2]==(os.getpid(),threading.get_ident()) and time.monotonic()<source[2],
            'retained-response-live-source')
    o.check(type(handler) is api.Api and getattr(handler._successResponse,'__func__',None) is api.Api._successResponse,
            'retained-response-owning-serializer')
    o.check(api.Api._successResponse is source[6] and source[6].__code__ is source[7],'retained-response-original-serializer')
    admission=_receipt_admission(receipt,packet)
    answer=status_existing(packet['controller'],packet['writer'],packet['request'],admission=admission)
    transition=json.loads(packet['transition_bytes'])
    source_originals=json.loads(source[3])
    transition.update(native_source_root=str(Path(__file__).parent),
                      native_sources=[dict(path=p,signature9=v,sha256=source[4][p]) for p,v in source_originals['files9']],
                      committed_vectors=json.loads(packet['vectors_bytes']),
                      committed_hashes=dict(packet['hashes']))
    answer=dict(answer,transition=transition)
    raw=handler._successResponse(answer)
    o.check(type(raw) is str and 0<len(raw.encode())<=4*1024**2,'retained-response-envelope-bound')
    decoded=g.decode_json(raw)
    o.check(type(decoded) is dict and set(decoded)=={'success','data'} and decoded['success'] is True
            and g.same_json(decoded['data'],answer),'retained-response-exact-envelope')
    frames=(json.loads(source[3]),json.loads(packet['vectors_bytes']))
    _HTTP[receipt]={'pid':os.getpid(),'thread':threading.get_ident(),'deadline':min(packet['deadline'],source[2]),
            'packet':packet,'frames':tuple(o.compact(frame) for frame in frames),'hashes':source[4],
            'encoded':raw,'phase':'encoded','config':source[5]}
    entry=_HTTP[receipt]
    _HTTP_SEALS[receipt]=(entry,packet,admission,entry['frames'],entry['hashes'],tuple(entry['hashes'].items()),
                         entry['encoded'],entry['config'],entry['pid'],entry['thread'],entry['deadline'],_HTTP,_HTTP_SEALS)
    _response_entry(receipt,'encoded')
    return raw


def _response_entry(receipt,phase):
    entry=_HTTP.get(receipt);seal=_HTTP_SEALS.get(receipt)
    o.check(entry is not None and seal is not None and seal[0] is entry
            and entry['packet'] is seal[1] and _receipt_admission(receipt,seal[1]) is seal[2]
            and entry['frames'] is seal[3] and entry['hashes'] is seal[4]
            and all(type(k) is str and type(v) is str for k,v in entry['hashes'].items())
            and tuple(entry['hashes'].items())==seal[5] and entry['encoded'] is seal[6]
            and entry['config'] is seal[7] and type(entry['pid']) is int and entry['pid']==seal[8]
            and type(entry['thread']) is int and entry['thread']==seal[9]
            and type(entry['deadline']) is type(seal[10]) and entry['deadline']==seal[10]
            and _HTTP is seal[11] and _HTTP_SEALS is seal[12] and entry['phase']==phase,
            'retained-response-original-seal')
    return entry,seal


def _close_response(receipt,envelope):
    o.check(type(receipt) is RetainedFinalization,'retained-response-exact-type')
    entry,seal=_response_entry(receipt,'encoded')
    o.check(type(receipt) is RetainedFinalization and entry is not None and entry['phase']=='encoded'
            and entry['pid']==os.getpid() and entry['thread']==threading.get_ident()
            and time.monotonic()<entry['deadline'] and type(envelope) is str and envelope==entry['encoded'],
            'retained-response-original-envelope')
    entry['phase']='uncertain'
    packet=entry['packet'];writer=packet['writer'];controller=packet['controller']
    status_existing(controller,writer,packet['request'],admission=seal[2])
    frames=tuple(json.loads(raw) for raw in entry['frames'])
    for path,digest in entry['hashes'].items():
        expected=dict(frames[0]['files9'])[path]
        o.check(hashlib.sha256(o.read_checked(Path(path),expected,1048576,entry['deadline'])).hexdigest()==digest,
                'retained-response-source-bytes')
    wb=packet['event'][7];cb=packet['event'][8]
    o.check(r._writer_binding(writer)==wb and r._controller_binding(controller)==cb,'retained-response-bindings')
    o.check(getattr(writer.local[1],'depth',0)>0 and not any(getattr(writer.local[1],k,False) for k in
            ('allow_pending','allow_tagger_pending','allow_release_pending')),'retained-response-ordinary-purpose')
    _response_entry(receipt,'uncertain')
    # No imported proof or refreshed facts after these original raw comparisons.
    for frame in frames:_response_raw(frame)
    if packet.get('api_admission') is not seal[2]:raise o.Held('retained-response-final-admission')
    entry['phase']='closed'


def _finish_response(receipt,envelope):
    o.check(type(receipt) is RetainedFinalization,'retained-response-exact-type')
    entry,seal=_response_entry(receipt,'closed')
    o.check(type(receipt) is RetainedFinalization and entry is not None and entry['phase']=='closed'
            and entry['pid']==os.getpid() and entry['thread']==threading.get_ident()
            and time.monotonic()<entry['deadline'] and type(envelope) is str and envelope==entry['encoded'],
            'retained-response-closed-envelope')
    packet=entry['packet'];writer=packet['writer'];controller=packet['controller']
    frames=tuple(json.loads(raw) for raw in entry['frames'])
    wb=packet['event'][7];cb=packet['event'][8]
    o.check(r._writer_binding(writer)==wb and r._controller_binding(controller)==cb,'retained-response-final-bindings')
    o.check(getattr(writer.local[1],'depth',0)==0 and not any(getattr(writer.local[1],k,False) for k in
            ('allow_pending','allow_tagger_pending','allow_release_pending')),'retained-response-released-purpose')
    import mylar
    o.check(entry['config']==(mylar.DATA_DIR,mylar.CONFIG.DESTINATION_DIR,mylar.CONFIG.DDL_LOCATION,mylar.CONFIG.API_ENABLED,mylar.CONFIG.API_KEY),'retained-response-final-config')
    _response_entry(receipt,'closed')
    if seal[2] is not None:
        from mylar import publication_retained_api as api_gate
        api_gate.check_admission(seal[2],packet['controller'],packet['writer'],packet['request'],held=False)
    # Every replaceable helper precedes this final inline original closure.
    for frame in frames:
        for path,names in frame['namespaces']:
            if tuple(sorted(os.listdir(path)))!=tuple(names):raise o.Held('retained-response-final-namespace')
        for path,expected in frame['nodes5']:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(expected):raise o.Held('retained-response-final-node')
        for path,expected in frame['files9']:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(expected):raise o.Held('retained-response-final-file')
        for path in frame['absent']:
            try:os.lstat(path)
            except FileNotFoundError:continue
            raise o.Held('retained-response-final-absence')
        for path,expected in frame['claims']:
            try:z=os.lstat(path)
            except FileNotFoundError:
                if expected is not None:raise o.Held('retained-response-final-claim')
                continue
            actual=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)
            if actual!=(None if expected is None else tuple(expected)):raise o.Held('retained-response-final-claim')
    if (writer.root,writer.lock,writer.pending,writer.tagger_pending,writer.release_pending,
            tuple(writer.lock_identity),tuple(writer.root_identity),writer.local)!=wb:raise o.Held('retained-response-final-Writer')
    if (controller.root,controller.database,controller.native_database,controller.writer_root,
            tuple(controller.roots),controller.tool_root)!=cb:raise o.Held('retained-response-final-Controller')
    if getattr(writer.local[1],'depth',0)!=0 or any(getattr(writer.local[1],k,False) for k in
            ('allow_pending','allow_tagger_pending','allow_release_pending')):raise o.Held('retained-response-final-purpose')
    if entry['config']!=(mylar.DATA_DIR,mylar.CONFIG.DESTINATION_DIR,mylar.CONFIG.DDL_LOCATION,mylar.CONFIG.API_ENABLED,mylar.CONFIG.API_KEY):raise o.Held('retained-response-final-configuration')
    if (packet.get('api_admission') is not seal[2] or _HTTP.get(receipt) is not entry
            or _HTTP_SEALS.get(receipt) is not seal or _HTTP is not seal[11] or _HTTP_SEALS is not seal[12]):
        raise o.Held('retained-response-final-original-seal')
    del _HTTP[receipt];del _HTTP_SEALS[receipt]
    return envelope


def _precommit_response_budget(packet,handler,source_frame,record_sha,files,nodes):
    """Wire-size bound only. Placeholder stat/hash fields never become evidence."""
    from mylar import api,publication_guard as g
    source=_SOURCE_FRAMES.get(source_frame)
    o.check(type(source_frame) is ResponseSources and source is not None and source[:2]==(os.getpid(),threading.get_ident())
            and time.monotonic()<source[2] and type(handler) is api.Api
            and getattr(handler._successResponse,'__func__',None) is source[6] is api.Api._successResponse
            and source[6].__code__ is source[7],'retained-precommit-response-owner')
    frame=json.loads(source[3])
    for path,stamp in frame['files9']:
        original=tuple(stamp)
        o.check(path not in files or tuple(files[path])==original,'retained-precommit-source-conflict')
        files.setdefault(path,original);packet['hashes'][path]=source[4][path]
    for path,stamp in frame['nodes5']:
        original=tuple(stamp)
        o.check(path not in nodes or tuple(nodes[path])==original,'retained-precommit-node-conflict')
        nodes.setdefault(path,original)
    packet['vectors']['files9']=[[p,list(v)] for p,v in files.items()]
    packet['vectors']['nodes5']=[[p,list(v)] for p,v in nodes.items()]
    # A signed 21-digit field dominates any supported original or postcommit stat.
    ceiling=2**64-1;reserved=[-ceiling]*9
    o.check(all(type(v) is int and abs(v)<=ceiling for stamp in files.values() for v in stamp),'retained-stat-wire-width')
    o.check(all(type(rows) is list and len(rows)<=8192 for rows in packet['vectors'].values()),
            'retained-producer-vector-wire-bound')
    transition=json.loads(packet['transition_bytes'])
    future=json.loads(o.compact(packet['vectors']))
    for row in future['files9']:
        if row[0]==str(packet['controller'].database):row[1]=reserved
    transition.update(native_source_root=str(Path(__file__).parent),
        native_sources=[dict(path=p,signature9=v,sha256=source[4][p]) for p,v in frame['files9']],
        committed_vectors=future,committed_hashes=dict(packet['hashes']))
    transition['committed_hashes'][str(packet['controller'].database)]='0'*64
    preview=dict(packet,record_sha=record_sha,committed=dict(path=str(packet['controller'].database),sha256='0'*64,signature9=reserved))
    answer=dict(_result(preview),transition=transition)
    raw=handler._successResponse(answer)
    o.check(type(raw) is str and 0<len(raw.encode())<=4*1024**2,'retained-response-precommit-wire-bound')
    decoded=g.decode_json(raw)
    o.check(type(decoded) is dict and set(decoded)=={'success','data'} and decoded['success'] is True
            and g.same_json(decoded['data'],answer),'retained-precommit-exact-envelope')
    packet['response_stat_ceiling']=ceiling

# Passive restart observations are a different type from same-live finalization.
# They cannot enter _FINALS/_EVENTS, mint a producer, or finish an action.
_PASSIVE=weakref.WeakKeyDictionary()
_PASSIVE_SEALS=weakref.WeakKeyDictionary()
_PASSIVE_SOURCES=weakref.WeakKeyDictionary()

class RetainedReconciliation:
    def __init__(self,*args,**kwargs):raise o.Held('retained-passive-factory-only')
    def encode(self,handler,source_frame):
        from mylar import api,publication_guard as g
        c=_PASSIVE.get(self);source=_SOURCE_FRAMES.pop(source_frame,None)
        o.check(c is not None and c['phase']=='observed' and source is not None
                and source[:2]==(os.getpid(),threading.get_ident())
                and time.monotonic()<source[2],'retained-passive-source-owner')
        o.check(type(handler) is api.Api and getattr(handler._successResponse,'__func__',None) is source[6]
                and api.Api._successResponse is source[6] and source[6].__code__ is source[7],
                'retained-passive-original-serializer')
        seal=_PASSIVE_SEALS.get(self);o.check(seal is not None and seal[0] is c,'retained-passive-original-seal')
        source_original=(source[:4],tuple(source[4].items()),source[5:])
        o.check(seal[7] is None and _PASSIVE_SOURCES.get(self) is None,'retained-passive-source-once')
        seal=(*seal[:7],source_original,*seal[8:]);_PASSIVE_SEALS[self]=seal
        _PASSIVE_SOURCES[self]=source_original;c['phase']='encoding'
        raw=handler._successResponse(json.loads(seal[5]))
        o.check(_PASSIVE_SOURCES.get(self) is source_original and _PASSIVE_SEALS.get(self) is seal,
                'retained-passive-original-serialization')
        o.check(type(raw) is str and 0<len(raw.encode())<=65536
                and g.same_json(g.decode_json(raw),dict(success=True,data=json.loads(seal[5]))),
                'retained-passive-response')
        c['encoded']=raw;_passive_close(self,held=True);c['phase']='encoded';return raw
    def close(self,envelope):
        c=_PASSIVE.get(self)
        o.check(c is not None and c['phase']=='encoded' and envelope==c['encoded'],
                'retained-passive-original-envelope')
        _passive_close(self,held=True);c['phase']='closed'
    def finish(self,envelope):
        c=_PASSIVE.get(self)
        o.check(c is not None and c['phase']=='closed' and envelope==c['encoded'],
                'retained-passive-closed-envelope')
        _passive_close(self,held=False);c['phase']='finished';return envelope


def _passive_close(observation,*,held,sources_required=True):
    c=_PASSIVE.get(observation);seal=_PASSIVE_SEALS.get(observation)
    o.check(type(observation) is RetainedReconciliation and c is not None and seal is not None
            and seal[0] is c and seal[1][:2]==(os.getpid(),threading.get_ident())
            and time.monotonic()<seal[1][2],'retained-passive-original-lifetime')
    if c.get('api_admission') is not seal[10]:raise o.Held('retained-passive-original-API-admission')
    if seal[10] is not None:
        from mylar import publication_retained_api as api_gate
        api_gate.check_admission(seal[10],c['controller'],c['writer'],api_gate.admission_request(seal[10]),held=held)
    owner,thread,deadline=seal[1];controller,writer,cb,wb=seal[2]
    objects,originals=seal[3:5]
    files,nodes,absent,namespaces,claims,hashes=originals
    o.check(r._controller_binding(controller)==cb and r._writer_binding(writer)==wb,
            'retained-passive-bindings')
    if held:
        o.check(getattr(writer.local[1],'depth',0)>0 and not any(getattr(writer.local[1],k,False)
                for k in ('allow_pending','allow_tagger_pending','allow_release_pending')),
                'retained-passive-ordinary-Writer')
    source=seal[7]
    o.check(_PASSIVE_SOURCES is seal[8][2] and _PASSIVE_SEALS is seal[8][1] and _PASSIVE is seal[8][0]
            and _PASSIVE_SOURCES.get(observation) is source
            and (source is not None if sources_required else source is None),'retained-passive-original-source-seal')
    if source is not None:
        import mylar
        from mylar import api
        prefix,source_hashes,suffix=source
        o.check((mylar.DATA_DIR,mylar.CONFIG.DESTINATION_DIR,mylar.CONFIG.DDL_LOCATION,
                 mylar.CONFIG.API_ENABLED,mylar.CONFIG.API_KEY)==suffix[0]
                and api.Api._successResponse is suffix[1] and suffix[1].__code__ is suffix[2],
                'retained-passive-source-config')
        source_frame=json.loads(prefix[3])
        for path,digest in source_hashes:
            stamp=dict(source_frame['files9'])[path]
            o.check(hashlib.sha256(o.read_checked(path,stamp,1048576,deadline)).hexdigest()==digest,
                    'retained-passive-source-bytes')
    for path,digest in hashes:
        o.check(hashlib.sha256(o.read_checked(path,list(dict(files)[path]),r.MAX_FILE,deadline)).hexdigest()==digest,
                'retained-passive-original-bytes')
    if source is not None:_response_raw(source_frame)
    if seal[10] is not None:
        api_gate.check_admission(seal[10],controller,writer,api_gate.admission_request(seal[10]),held=held)
    if not held:
        o.check(getattr(writer.local[1],'depth',0)==0 and not any(getattr(writer.local[1],k,False)
                for k in ('allow_pending','allow_tagger_pending','allow_release_pending')),
                'retained-passive-released-Writer')
    # All helper callbacks precede raw closure of the immutable original vectors.
    for path,names in namespaces:
        if tuple(sorted(os.listdir(path)))!=names:raise o.Held('retained-passive-final-census')
    for path,stamp in nodes:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise o.Held('retained-passive-final-node')
    for path,stamp in files:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:
            raise o.Held('retained-passive-final-file')
    for path,stamp in claims:
        try:z=os.lstat(path)
        except FileNotFoundError:
            if stamp is None:continue
            raise o.Held('retained-passive-final-claim')
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)!=stamp:
            raise o.Held('retained-passive-final-claim')
    for path in absent:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise o.Held('retained-passive-final-absence')
    if (_PASSIVE.get(observation) is not c or _PASSIVE_SEALS.get(observation) is not seal
            or _PASSIVE_SOURCES.get(observation) is not source
            or (c['controller'],c['writer'],c['controller_binding'],c['writer_binding'])!=(controller,writer,cb,wb)
            or c['owner']!=(owner,thread) or c['deadline']!=deadline):
        raise o.Held('retained-passive-original-registry')
    for key,obj,expected in zip(('files','nodes','absent','namespaces','claims','hashes'),objects,originals):
        actual=c[key]
        if actual is not obj or (tuple(actual) if key=='absent' else tuple(actual.items()))!=expected:
            raise o.Held('retained-passive-original-logical-frame')
    result=c['result']
    if (type(result) is not dict or any(type(key) is not str for key in result)
            or tuple(result)!=tuple(key for key,_ in seal[6])):raise o.Held('retained-passive-original-result')
    for key,wanted in seal[6]:
        actual=result[key]
        if type(actual) is not type(wanted) or (actual is not wanted if type(wanted) is bool else actual!=wanted):
            raise o.Held('retained-passive-original-result')
    if ((controller.root,controller.database,controller.native_database,controller.writer_root,
         tuple(controller.roots),controller.tool_root)!=cb
            or (writer.root,writer.lock,writer.pending,writer.tagger_pending,writer.release_pending,
                tuple(writer.lock_identity),tuple(writer.root_identity),writer.local)!=wb):
        raise o.Held('retained-passive-final-current-bindings')
    if held and (getattr(writer.local[1],'depth',0)<=0 or any(getattr(writer.local[1],k,False) for k in
            ('allow_pending','allow_tagger_pending','allow_release_pending'))):
        raise o.Held('retained-passive-final-purpose')
    if not held and (getattr(writer.local[1],'depth',0)!=0 or any(getattr(writer.local[1],k,False) for k in
            ('allow_pending','allow_tagger_pending','allow_release_pending'))):
        raise o.Held('retained-passive-final-released-purpose')
    if c.get('api_admission') is not seal[10]:raise o.Held('retained-passive-final-API-admission')
    if source is not None:
        if ((mylar.DATA_DIR,mylar.CONFIG.DESTINATION_DIR,mylar.CONFIG.DDL_LOCATION,
              mylar.CONFIG.API_ENABLED,mylar.CONFIG.API_KEY)!=suffix[0]
                or api.Api._successResponse is not suffix[1] or suffix[1].__code__ is not suffix[2]):
            raise o.Held('retained-passive-final-config-serializer')
    if time.monotonic is not seal[9] or seal[9]()>=deadline:raise o.Held('retained-passive-final-deadline')


def durable_reconcile(controller,writer,value,*,admission=None):
    """Read exact durable originals after restart; no action/ACK reconstruction."""
    if admission is not None:
        from mylar import publication_retained_api as api
        api.check_admission(admission,controller,writer,value)
    else:o.check(ENABLED and r.ENABLED,'retained-passive-default-disabled')
    value=r.request(value);modules=o.sdk();o.writer_pair(controller,writer,modules)
    g=modules[2];deadline=time.monotonic()+120
    wb=r._writer_binding(writer);cb=r._controller_binding(controller)
    token=hashlib.sha256((value['ddl_id']+'\0'+value['pack_id']+'\0'+value['member_id']).encode()).hexdigest()
    workflow_stamp,workflow_hash=r._file(controller.database,deadline)
    current=r._sql(controller.database,workflow_stamp)
    rows=current['rows'].get('records',[])
    selected=[json.loads(raw) for raw in rows if json.loads(raw)[:2]==[RECORD_KIND,token]]
    o.check(len(selected)==1 and len(selected[0])==4 and selected[0][3]==0.0,
            'retained-passive-unique-final-record')
    final_row=selected[0];record=g.decode_json(final_row[2])
    rights=('historical_import_ack','ordinary_import_grant','cleanup_grant','mutation_authority',
            'publication_acceptance','reader_index_acceptance','automatic_replay')
    o.check(type(record) is dict and set(record)=={'version','kind','token','request','source','target',
            'original_event','original_vectors','pack_before','pack_after','pack_before_row','workflow_before_sha256',*rights}
            and type(record['version']) is int and record['version']==2
            and record['kind']=='fresh-retained-backend-finalization' and record['token']==token
            and g.same_json(record['request'],value) and all(record[k] is False for k in rights),
            'retained-passive-original-record')
    # Commit the whole preimage without recursively embedding previous final
    # records. Recover it only by reversing these exact two rows in current SQL.
    pack=record['pack_before'];prior=record['pack_before_row'];commitment=record['workflow_before_sha256']
    o.check(type(prior) is list and len(prior)==4 and prior[:2]==['pack',value['pack_id']]
            and type(prior[2]) is str and g.same_json(g.decode_json(prior[2]),pack)
            and type(commitment) is str and len(commitment)==64
            and all(c in '0123456789abcdef' for c in commitment),'retained-passive-original-pack-row')
    before=copy.deepcopy(current);before_rows=before['rows']['records']
    current_pack=[json.loads(raw) for raw in before_rows if json.loads(raw)[:2]==['pack',value['pack_id']]]
    successor=prior.copy();successor[2]=o.compact(record['pack_after']).decode()
    o.check(len(current_pack)==1 and g.same_json(current_pack[0],successor)
            and before_rows.count(o.compact(final_row).decode())==1,'retained-passive-current-pack-row')
    before_rows.remove(o.compact(final_row).decode());before_rows.remove(o.compact(successor).decode())
    before_rows.append(o.compact(prior).decode());before_rows.sort()
    o.check(o.digest(before)==commitment,'retained-passive-complete-preimage-commitment')
    original=[prior]
    o.check(type(pack) is dict and pack.get('id')==value['pack_id'] and pack.get('ddl_id')==value['ddl_id']
            and pack.get('source_generation')==value['source_generation']
            and not pack.get('cleanup_started') and not pack.get('cleanup_complete')
            and type(pack.get('members')) is list and len(pack['members'])<=2000
            and all(type(m) is dict for m in pack['members']),'retained-passive-original-capture')
    wanted=copy.deepcopy(pack);members=[m for m in wanted['members'] if m.get('id')==value['member_id']]
    o.check(len(members)==1,'retained-passive-one-member');member=members[0];owner=value['owner']
    o.check(member.get('kind')==('annual' if owner['table']=='annuals' else 'issue')
            and member.get('issueid')==owner['issueid'] and member.get('comicid')==owner['parentcomicid']
            and member.get('releasecomicid')==owner['releasecomicid']
            and member.get('phase') in ('review','ready','submitted','confirmed')
            and not member.get('ordinary_import_token') and not member.get('retained_finalization')
            and member.get('destination',record['target'])==record['target']
            and member.get('destination_sha256',value['target_sha256'])==value['target_sha256']
            and member.get('sha256',value['source_sha256'])==value['source_sha256'],
            'retained-passive-original-member')
    member.update(phase=MEMBER_PHASE,retained_finalization=token,destination=record['target'],
                  destination_sha256=value['target_sha256']);wanted['phase']='review'
    o.check(g.same_json(wanted,record['pack_after']),'retained-passive-exact-member-delta')
    expected=copy.deepcopy(before);expected_rows=expected['rows']['records']
    expected_rows.remove(o.compact(original[0]).decode())
    successor=original[0].copy();successor[2]=o.compact(wanted).decode()
    expected_rows.extend((o.compact(successor).decode(),o.compact(final_row).decode()));expected_rows.sort()
    o.check(g.same_json(expected,current),'retained-passive-complete-two-row-SQL')
    vectors=record['original_vectors']
    o.check(type(vectors) is dict and set(vectors)=={'files9','nodes5','absent','namespaces','claims'}
            and all(type(v) is list and len(v)<=8192 for v in vectors.values()),'retained-passive-vectors')
    o.check(all(len({p for p,_ in vectors[k]})==len(vectors[k]) for k in ('files9','nodes5','namespaces','claims'))
            and len(set(vectors['absent']))==len(vectors['absent']),'retained-passive-duplicate-vector')
    files,nodes,absent,namespaces,claims=_parts(vectors)
    files={p:tuple(v) for p,v in files.items()};nodes={p:tuple(v) for p,v in nodes.items()}
    namespaces={p:tuple(v) for p,v in namespaces.items()};claims={p:None if v is None else tuple(v) for p,v in claims.items()}
    o.check(all(type(p) is str and Path(p).is_absolute() and '..' not in Path(p).parts
                for p in (*files,*nodes,*absent,*namespaces,*claims))
            and all(len(v)==9 and all(type(n) is int for n in v) for v in files.values())
            and all(len(v)==5 and all(type(n) is int for n in v) for v in nodes.values()),
            'retained-passive-vector-types')
    prior=files[str(controller.database)]
    o.check(workflow_stamp[:2]==prior[:2] and workflow_stamp[5:]==prior[5:],
            'retained-passive-workflow-incarnation')
    files[str(controller.database)]=workflow_stamp;hashes={str(controller.database):workflow_hash}
    folder=Path(controller.root)/r.NAME/token;events=record['original_event']
    o.check(type(events) is dict and set(events)=={'ack','intent','issued'},'retained-passive-event-roles')
    bodies={}
    for role,name in (('ack','accepted.json'),('intent','intent.json'),('issued','issued.json')):
        ref=events[role];path=folder/name
        o.check(type(ref) is list and len(ref)==3 and ref[0]==str(path)
                and tuple(ref[2])==files[str(path)],'retained-passive-exact-event-ref')
        stamp=tuple(ref[2])
        o.check(stamp[5]&0o170000==0o100000 and stamp[5]&0o7777==0o600
                and stamp[6:]==(os.geteuid(),os.getegid(),1),'retained-passive-event-owner-mode')
        raw=o.read_checked(path,ref[2],16*1024**2,deadline)
        o.check(hashlib.sha256(raw).hexdigest()==ref[1],'retained-passive-event-bytes')
        hashes[str(path)]=ref[1];bodies[role]=g.decode_json(raw)
    ack,intent,issued=(bodies[k] for k in ('ack','intent','issued'))
    o.check(ack['request']==value and ack['token']==token and ack['kind']=='fresh-retained-delivery-acceptance'
            and ack['source']==record['source'] and ack['target']==record['target']
            and ack['fresh_catalog_event'] is True and ack['historical_import_ack'] is False
            and intent['request']==value and intent['token']==token and intent['kind']==r.KIND
            and issued['token']==token and issued['request_sha256']==o.digest(value)
            and issued['ack']==dict(path=events['ack'][0],sha256=events['ack'][1],signature9=events['ack'][2])
            and issued['intent']==dict(path=events['intent'][0],sha256=events['intent'][1],signature9=events['intent'][2]),
            'retained-passive-original-event-joins')
    r.validate_ack_body(ack,value,token)
    r.validate_issued_body(issued,value,token,files[str(folder/'issued.json')],
        dict(path=events['ack'][0],sha256=events['ack'][1],signature9=events['ack'][2]),
        dict(path=events['intent'][0],sha256=events['intent'][1],signature9=events['intent'][2]))
    o.check(type(intent) is dict and set(intent)=={'version','kind','request','token','ddl_row_sha256',
            'source','target','original_vectors','historical_import_ack','automatic_replay'}
            and type(intent['version']) is int and intent['version']==1
            and intent['source']==record['source'] and intent['target']==record['target']
            and intent['historical_import_ack'] is False and intent['automatic_replay'] is False,
            'retained-passive-intent-schema')
    catalog,_,_=o.catalog(controller,value['owner'],g,deadline)
    o.check(catalog['owner']['path']==record['target'],'retained-passive-current-owner')
    hashes[str(controller.native_database)]=ack['catalog_before_sha256']
    for role in ('source','target'):
        path=record[role];digest=value[role+'_sha256']
        o.check(g.inventory(Path(path),tool_root=controller.tool_root,deadline=deadline)==ack[role+'_inventory'],
                'retained-passive-current-inventory');hashes[path]=digest
    preservation=ack['target_preservation']
    o.check(type(preservation) is dict and len(preservation)==2,'retained-passive-preservation-pair')
    for name,ref in preservation.items():
        o.check(name in ('target-preserved'+Path(record['target']).suffix.lower(),
                        'target-restored'+Path(record['target']).suffix.lower())
                and ref['path']==str(folder/name) and tuple(ref['signature9'])==files[ref['path']]
                and ref['sha256']==value['target_sha256'],'retained-passive-original-copy')
        hashes[ref['path']]=ref['sha256']
    result=dict(version=1,outcome='retained-durable-state-observed',token=token,
                record_sha256=hashlib.sha256(final_row[2].encode()).hexdigest(),
                **{k:False for k in rights},reader_resume_grant=False,operational_custody_complete=False)
    observation=object.__new__(RetainedReconciliation)
    _PASSIVE[observation]=dict(owner=(os.getpid(),threading.get_ident()),deadline=deadline,
        controller=controller,writer=writer,controller_binding=cb,writer_binding=wb,
        files=files,nodes=nodes,absent=absent,namespaces=namespaces,claims=claims,hashes=hashes,
        result=result,phase='observed',api_admission=admission)
    c=_PASSIVE[observation]
    objects=tuple(c[k] for k in ('files','nodes','absent','namespaces','claims','hashes'))
    originals=tuple(tuple(v) if k=='absent' else tuple(v.items()) for k,v in zip(('files','nodes','absent','namespaces','claims','hashes'),objects))
    _PASSIVE_SEALS[observation]=(c,(*c['owner'],deadline),(controller,writer,cb,wb),objects,originals,o.compact(result),tuple(result.items()),None,(_PASSIVE,_PASSIVE_SEALS,_PASSIVE_SOURCES),time.monotonic,admission)
    _passive_close(observation,held=True,sources_required=False)
    return observation
