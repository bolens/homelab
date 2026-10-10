"""Disabled same-daemon retained acceptance finalizer, no historical import grant.

Only live V4 owning events can enter. A saved backend record is insufficient to
create a producer witness; unknown commits and restarts remain Held.
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


def _parts(v):
    return (dict(v['files9']),dict(v['nodes5']),tuple(v['absent']),dict(v['namespaces']),dict(v['claims']))


def _checked(packet,files):
    o.check(time.monotonic()<packet['deadline'],'retained-finalize-deadline')
    try:o.writer_pair(packet['controller'],packet['writer'],packet['modules'])
    except packet['modules'][2].Unavailable:raise o.Held('retained-finalize-Writer-unavailable') from None
    for path,digest in packet['hashes'].items():
        raw=o.read_checked(path,list(files[path]),256*1024**2,packet['deadline'])
        o.check(hashlib.sha256(raw).hexdigest()==digest,'retained-finalize-bytes')


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
        return status_existing(packet['controller'],packet['writer'],packet['request'])


def finalize(cap):
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
    o.check(ENABLED,'retained-finalizer-default-disabled')
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
    _checked(packet,dict(files))
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
    record={'version':1,'kind':'fresh-retained-backend-finalization','token':token,
            'request':value,'source':source,'target':target,'original_event':{'ack':list(event[2]),'intent':list(event[3]),'issued':list(event[4])},
            'original_vectors':originals,'pack_before':capture,'pack_after':changed,
            'historical_import_ack':False,'ordinary_import_grant':False,'cleanup_grant':False,
            'mutation_authority':False,'publication_acceptance':False,
            'reader_index_acceptance':False,'automatic_replay':False}
    raw=o.compact(record).decode();new_value=o.compact(changed).decode()
    expected_sql=copy.deepcopy(before)
    replacement=prior.copy();replacement[2]=new_value
    # Preserve updated column: only exact member/value mutation is admitted.
    expected_sql['rows']['records'].remove(o.compact(prior).decode())
    expected_sql['rows']['records'].append(o.compact(replacement).decode())
    expected_sql['rows']['records'].append(o.compact([RECORD_KIND,token,raw,0.0]).decode())
    expected_sql['rows']['records'].sort()
    result_record_sha=hashlib.sha256(raw.encode()).hexdigest()
    # All callbacks precede raw closure and the exact fixed SQL transaction.
    _checked(packet,dict(files))
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
    _checked(packet,dict(files))
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
    receipt=object.__new__(RetainedFinalization);_RECEIPTS[receipt]=frozen
    return receipt


def status_existing(controller,writer,value):
    o.check(ENABLED,'retained-finalizer-default-disabled')
    value=r.request(value)
    token=hashlib.sha256((value['ddl_id']+'\0'+value['pack_id']+'\0'+value['member_id']).encode()).hexdigest()
    original=_FINALS.get((str(controller.root),token))
    o.check(original is not None and original['producer_pid']==os.getpid()
            and original['request']==value,
            'retained-finalizer-original-commit-required')
    packet=dict(original);packet['hashes']=dict(original['hashes'])
    event=packet['event'];wb=event[7];cb=event[8]
    files,nodes,absent,namespaces,claims=_parts(json.loads(original['vectors_bytes']))
    o.check(r._writer_binding(writer)==wb and r._controller_binding(controller)==cb,'retained-finalizer-bindings')
    packet['controller']=controller;packet['writer']=writer
    _checked(packet,dict(files))
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

class ResponseSources:
    def __init__(self,*args,**kwargs):raise o.Held('retained-response-source-factory-only')


def response_sources():
    from mylar import api,native_writers,publication_retained_api
    import mylar
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
    _SOURCE_FRAMES[obj]=(os.getpid(),threading.get_ident(),deadline,encoded,dict(hashes),config)
    return obj


def response_existing(controller,writer,value):
    status_existing(controller,writer,value)
    value=r.request(value)
    token=hashlib.sha256((value['ddl_id']+'\0'+value['pack_id']+'\0'+value['member_id']).encode()).hexdigest()
    original=_FINALS.get((str(controller.root),token))
    o.check(original is not None and original['producer_pid']==os.getpid() and original['request']==value,
            'retained-response-original-commit')
    # Only an already published original commit can issue this passive receipt.
    packet=dict(original);packet['controller']=controller;packet['writer']=writer
    receipt=object.__new__(RetainedFinalization);_RECEIPTS[receipt]=packet
    return receipt


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
    answer=status_existing(packet['controller'],packet['writer'],packet['request'])
    raw=handler._successResponse(answer)
    o.check(type(raw) is str and 0<len(raw.encode())<=4*1024**2,'retained-response-envelope-bound')
    decoded=g.decode_json(raw)
    o.check(type(decoded) is dict and set(decoded)=={'success','data'} and decoded['success'] is True
            and g.same_json(decoded['data'],_result(packet)),'retained-response-exact-envelope')
    frames=(json.loads(source[3]),json.loads(packet['vectors_bytes']))
    _HTTP[receipt]={'pid':os.getpid(),'thread':threading.get_ident(),'deadline':min(packet['deadline'],source[2]),
            'packet':packet,'frames':tuple(o.compact(frame) for frame in frames),'hashes':source[4],
            'encoded':raw,'phase':'encoded','config':source[5]}
    return raw


def _close_response(receipt,envelope):
    o.check(type(receipt) is RetainedFinalization,'retained-response-exact-type')
    entry=_HTTP.get(receipt)
    o.check(type(receipt) is RetainedFinalization and entry is not None and entry['phase']=='encoded'
            and entry['pid']==os.getpid() and entry['thread']==threading.get_ident()
            and time.monotonic()<entry['deadline'] and type(envelope) is str and envelope==entry['encoded'],
            'retained-response-original-envelope')
    entry['phase']='uncertain'
    packet=entry['packet'];writer=packet['writer'];controller=packet['controller']
    status_existing(controller,writer,packet['request'])
    frames=tuple(json.loads(raw) for raw in entry['frames'])
    for path,digest in entry['hashes'].items():
        expected=dict(frames[0]['files9'])[path]
        o.check(hashlib.sha256(o.read_checked(Path(path),expected,1048576,entry['deadline'])).hexdigest()==digest,
                'retained-response-source-bytes')
    wb=packet['event'][7];cb=packet['event'][8]
    o.check(r._writer_binding(writer)==wb and r._controller_binding(controller)==cb,'retained-response-bindings')
    o.check(getattr(writer.local[1],'depth',0)>0 and not any(getattr(writer.local[1],k,False) for k in
            ('allow_pending','allow_tagger_pending','allow_release_pending')),'retained-response-ordinary-purpose')
    # No imported proof or refreshed facts after these original raw comparisons.
    for frame in frames:_response_raw(frame)
    entry['phase']='closed'


def _finish_response(receipt,envelope):
    o.check(type(receipt) is RetainedFinalization,'retained-response-exact-type')
    entry=_HTTP.pop(receipt,None)
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
    return envelope
