"""Default-off, one-use retained pack observation; no ordinary ACK or cleanup."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
import weakref

from maintenance import Maintenance
from media_writer import Writer
from publication_guard import current, scope, remote_unlocked, evidence

ENABLED=False
NATIVE_SOURCE_ROOT='/app/mylar3/mylar'
NATIVE_API_SHA=None  # Root must prove final installed canonical API bytes.
NATIVE_SOURCE_PINS={'native_writers.py': '16a90e8fa1ea0375083caddb548e0c2fa2fb51fa4d7e63f770cdedf2e6d0c388', 'publication_retained_api.py': '41df9fc5214d7bb328261582711cfc3dbe673e40ac5568010cde48c660170c08', 'publication_retained_delivery.py': 'bfbf227b8deff0e37550360ee47a0832019ef1f5cea68e3618d4e0ef0295380b', 'publication_retained_finalize.py': '1ecc57c8797796c109548b56261427746be54e06ad545e99ea8cfa632369acd3'}
# Missing installed api.py source pin keeps operational export consumption held.

_RETURN=Maintenance.retained_pack_return
_RETURN_CODE=_RETURN.__code__
_REQUEST=_RETURN.__globals__['request']
_REQUEST_CODE=_REQUEST.__code__
_CORES=weakref.WeakKeyDictionary()
_SELECTED={}
_LIMIT=4*1024**2
_MARKERS=('normalizer-v1.pending','tagger-v2.pending','release-v1.pending','tagger-publication-v1.json',
 'nested-derivative-v1.json','tagger-recovery-v1.pending','negative-retirement-v1.pending',
 'negative-retirement-v1.terminal-pending','archive-repair-v1.pending','archive-repair-v1.terminal-pending')


def compact(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def native_compact(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def nine(z):return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
def five(z):return (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
def check(value,reason):
    if not value:raise ValueError(reason)


def _transport(m):
    check(getattr(m.retained_pack_return,'__func__',None) is _RETURN and _RETURN.__code__ is _RETURN_CODE
          and _RETURN.__globals__.get('request') is _REQUEST and _REQUEST.__code__ is _REQUEST_CODE,
          'retained-original-transport')


def _binding(m):
    return (m.state,m.worker,tuple(m.worker.roots),m.worker.config['writer_state'],m.settings.get('ddl_cache'),m.settings.get('mylar_ddl_cache'),
            m.worker.config['mylar'].get('url'),m.worker.config['mylar'].get('config_dir','/mylar'),
            tuple((row['native'],row['worker']) for row in m.worker.config['publication_roots']))


def _read(path,stamp,limit=256*1024**2):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        check(nine(os.fstat(fd))==tuple(stamp),'retained-original-FD')
        data=bytearray()
        while block:=os.read(fd,1024**2):
            data.extend(block);check(len(data)<=limit,'retained-read-bound')
        check(nine(os.fstat(fd))==tuple(stamp) and nine(os.lstat(path))==tuple(stamp),'retained-original-read')
        return bytes(data)
    finally:os.close(fd)


def _nodes(frame,path):
    for p in (Path(path).parent,*Path(path).parents):
        z=os.lstat(p);v=five(z);check(v[2]&0o170000==0o040000,'retained-directory')
        check(str(p) not in frame['nodes'] or tuple(frame['nodes'][str(p)])==v,'retained-node-conflict')
        frame['nodes'].setdefault(str(p),v)


def _detached(f):
    return json.loads(compact(f))


def _capture(paths,absent=(),trees=(),stream_trees=(),originals=None):
    # Known leaf/ancestor originals precede the first tree enumeration callback.
    explicit=tuple(dict.fromkeys(map(str,paths)))
    prior_files={} if originals is None else {p:tuple(v) for p,v in originals['files'].items()}
    prior_nodes={} if originals is None else {p:tuple(v) for p,v in originals['nodes'].items()}
    prior_names={} if originals is None else {p:tuple(v) for p,v in originals['names'].items()}
    prior=None if originals is None else {'files':prior_files,'nodes':prior_nodes,'names':prior_names,
        'absent':tuple(originals['absent']),'claims':{p:None if v is None else tuple(v) for p,v in originals['claims'].items()},
        'attrs':{p:dict(v) for p,v in originals['attrs'].items()}}
    f={'files':{},'nodes':{},'absent':tuple(map(str,absent)),'names':{},'claims':{},'hashes':{},'attrs':{}}
    streams=set(explicit)
    for p in explicit:
        z=os.lstat(p);v=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
        f['files'][p]=v
    for p in (*explicit,*f['absent'],*(str(Path(p)/'.capture-original') for p in (*trees,*stream_trees))):
        for parent in Path(p).parents:
            z=os.lstat(parent);v=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
            if v[2]&0o170000!=0o040000:raise ValueError('retained-directory')
            if str(parent) in f['nodes'] and f['nodes'][str(parent)]!=v:raise ValueError('retained-node-conflict')
            f['nodes'].setdefault(str(parent),v)
    pending=[(Path(p),False) for p in trees]+[(Path(p),True) for p in stream_trees]
    seen=set()
    while pending:
        p,stream=pending.pop();key=(str(p),stream)
        if key in seen:continue
        seen.add(key)
        if len(f['files'])+len(f['names'])+len(pending)>8192:raise ValueError('retained-tree-bound')
        z=os.lstat(p)
        if z.st_mode&0o170000==0o040000:
            v=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
            if str(p) in f['nodes'] and f['nodes'][str(p)]!=v:raise ValueError('retained-tree-node-conflict')
            f['nodes'].setdefault(str(p),v)
            names=tuple(sorted(os.listdir(p)))
            if str(p) in f['names'] and f['names'][str(p)]!=names:raise ValueError('retained-tree-namespace-conflict')
            f['names'].setdefault(str(p),names);pending.extend((p/n,stream) for n in names)
        else:
            v=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
            if str(p) in f['files'] and f['files'][str(p)]!=v:raise ValueError('retained-file-conflict')
            f['files'].setdefault(str(p),v)
            if stream:streams.add(str(p))
    # Complete raw census retains foreign links/nonregular entries without reading them.
    # Selected sources/targets/controls retain exclusive regular-file requirements.
    for p,v in f['files'].items():
        if p in prior_files and prior_files[p]!=v:raise ValueError('retained-original-file-conflict')
    for p,v in f['nodes'].items():
        if p in prior_nodes and prior_nodes[p]!=v:raise ValueError('retained-original-node-conflict')
    for p,v in f['names'].items():
        if p in prior_names and prior_names[p]!=v:raise ValueError('retained-original-namespace-conflict')
    for p in streams:
        v=f['files'][p]
        if v[5]&0o170000!=0o100000 or v[8]!=1:raise ValueError('retained-exclusive-file')
    if sum(f['files'][p][2] for p in streams)>32*1024**3:raise ValueError('retained-affected-byte-bound')
    # Revalidate prior complete originals before the first selected content/xattr read.
    if prior is not None:_raw(_detached(prior))
    _raw(_detached(f))
    for p in sorted(streams):
        names=os.listxattr(p,follow_symlinks=False);check(len(names)<=64 and sum(len(n.encode()) for n in names)<=16384,'retained-xattr-bound')
        attrs={};size=0
        for n in names:
            v=os.getxattr(p,n,follow_symlinks=False);size+=len(n.encode())+2*len(v);check(size<=1048576,'retained-xattr-bound');attrs[n]=v.hex()
        f['attrs'][p]=attrs
    for p in sorted(streams):f['hashes'][p]=hashlib.sha256(_read(p,f['files'][p])).hexdigest()
    if prior is not None:_raw(_detached(prior))
    _raw(_detached(f));return f


def _raw(f):
    for p,expected in f.get('attrs',{}).items():
        names=os.listxattr(p,follow_symlinks=False)
        if len(names)>64 or set(names)!=set(expected) or any(os.getxattr(p,n,follow_symlinks=False).hex()!=expected[n] for n in names):raise ValueError('retained-original-xattrs')
    for p,n in f['names'].items():
        if tuple(sorted(os.listdir(p)))!=tuple(n):raise ValueError('retained-namespace')
    for p,v in f['nodes'].items():
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(v):raise ValueError('retained-node')
    for p,v in f['files'].items():
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(v):raise ValueError('retained-file')
    for p in f['absent']:
        try:os.lstat(p)
        except FileNotFoundError:continue
        raise ValueError('retained-absence')
    for p,v in f['claims'].items():
        try:z=os.lstat(p)
        except FileNotFoundError:
            if v is None:continue
            raise ValueError('retained-claim')
        actual=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)
        if actual!=(None if v is None else tuple(v)):raise ValueError('retained-claim')


def _sql(path,stamp):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        check(nine(os.fstat(fd))==tuple(stamp),'retained-SQL-FD')
        with closing(sqlite3.connect('file:/proc/self/fd/'+str(fd)+'?mode=ro&immutable=1',uri=True)) as db:
            check(db.execute('PRAGMA quick_check').fetchall()==[('ok',)],'retained-SQL-integrity')
            schema=db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').fetchall()
            check(len(schema)<=128,'retained-schema-bound');rows={};count=0;size=0
            for kind,name,_,_ in schema:
                if kind!='table':continue
                check(re.fullmatch('[a-zA-Z_][a-zA-Z0-9_]*',name),'retained-SQL-name')
                values=[]
                for row in db.execute('SELECT * FROM "'+name+'"'):
                    encoded=native_compact([{'blob':v.hex()} if type(v) is bytes else v for v in row]);count+=1;size+=len(encoded)
                    check(count<=100000 and size<=64*1024**2,'retained-SQL-bound');values.append(encoded.decode())
                rows[name]=sorted(values)
        check(nine(os.fstat(fd))==tuple(stamp) and nine(os.lstat(path))==tuple(stamp),'retained-SQL-original')
        return {'schema':[list(r) for r in schema],'rows':rows}
    finally:os.close(fd)


def initialize(maintenance):
    """Explicit preparation ONLY, before protected proof/backup lifetime."""
    check(type(maintenance) is Maintenance,'retained-maintenance-type')
    p=maintenance.state/'retained-pack-handoffs'
    check(not any(q.is_symlink() for q in (p,*p.parents)),'retained-linked-journal')
    p.mkdir(mode=0o700,exist_ok=True);z=os.lstat(p)
    check(z.st_mode&0o170000==0o040000 and z.st_mode&0o7777==0o700 and z.st_uid==os.geteuid() and z.st_gid==os.getegid(),'retained-private-journal')
    fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def select(maintenance,pack_id,member_id):
    if not ENABLED:raise ValueError('Retained worker disabled')
    check(type(maintenance) is Maintenance and all(type(v) is str and re.fullmatch('[a-f0-9]{64}',v) for v in (pack_id,member_id)),'retained-exact-selector')
    check(id(maintenance) not in _SELECTED,'retained-one-selected-action')
    _SELECTED[id(maintenance)]=(maintenance,os.getpid(),threading.get_ident(),pack_id,member_id)


class RetainedPackAction:
    __slots__=('__weakref__',)
    def __init__(self,*a,**k):raise ValueError('Retained action owning factory only')


def _journal_write(path,data,parent,attrs=None):
    d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        check(five(os.fstat(d))==tuple(parent) and five(os.lstat(path.parent))==tuple(parent),'retained-admitted-output-parent')
        fd=os.open(path.name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=d)
        try:
            z=os.fstat(fd);first=nine(z)
            check(first[5]&0o7777==0o600 and first[8]==1 and first[6:8]==(os.geteuid(),os.getegid()),'retained-created-output')
            for name,value in (attrs or {}).items():os.setxattr(fd,name,bytes.fromhex(value))
            view=memoryview(data)
            while view:n=os.write(fd,view);check(n>0,'retained-output-write');view=view[n:]
            os.fsync(fd);z=os.fstat(fd);final=nine(z)
            check(final[:2]==first[:2] and final[5:]==first[5:] and final[2]==len(data),'retained-output-attributes')
            os.lseek(fd,0,os.SEEK_SET);check(os.read(fd,len(data)+1)==data,'retained-output-readback')
            check(nine(os.stat(path.name,dir_fd=d,follow_symlinks=False))==final,'retained-output-path')
            os.fsync(d)
        finally:os.close(fd)
        check(five(os.lstat(path.parent))==tuple(parent),'retained-output-parent-final')
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=final:raise ValueError('retained-output-final')
        return final
    finally:os.close(d)


def _core(action,phase):
    check(type(action) is RetainedPackAction,'retained-owning-action-type')
    c=_CORES.get(action)
    check(type(action) is RetainedPackAction and c is not None and c['phase']==phase
          and c['pid']==os.getpid() and c['thread']==threading.get_ident() and time.monotonic()<c['deadline'],'retained-live-action')
    return c


def prepare(maintenance,pack_id,member_id):
    check(ENABLED and type(maintenance) is Maintenance,'retained-default-disabled')
    check(type(NATIVE_API_SHA) is str and re.fullmatch('[a-f0-9]{64}',NATIVE_API_SHA),'retained-installed-API-pin-unproven')
    check(all(type(v) is str and re.fullmatch('[a-f0-9]{64}',v) for v in (pack_id,member_id)),'retained-selected-identities')
    _transport(maintenance);maintenance_binding=_binding(maintenance)
    a=current(maintenance.worker)
    receipt=maintenance.state/'packs'/pack_id/'receipt.json';journal=maintenance.state/'retained-pack-handoffs'
    z=os.lstat(journal);check(z.st_mode&0o7777==0o700 and z.st_uid==os.geteuid() and z.st_gid==os.getegid(),'retained-preinitialized-journal')
    # Capture all existing root/control/receipt leaves before receipt decoding.
    controls=[a.database,a.catalog,a.writer.lock,a.writer.root/'publication-v1.json',receipt,Path(__file__),Path(_RETURN_CODE.co_filename),Path(_REQUEST_CODE.co_filename),a.config/'config.ini']
    absent=[str(p)+s for p in (a.database,a.catalog) for s in ('-journal','-wal','-shm')]+[str(a.writer.root/n) for n in _MARKERS]
    first=_capture(controls,absent,trees=[receipt.parent,journal,*maintenance.worker.roots,Path(maintenance.settings['ddl_cache'])]);raw=_read(receipt,first['files'][str(receipt)],_LIMIT);local=evidence.decode_json(raw)
    evidence.ordinary_purpose(a.writer);a.admission()
    check(first['files'][str(receipt)][5]&0o7777==0o600,'retained-private-original-receipt')
    check(local.get('id')==pack_id and local.get('inventory_complete') is True and not local.get('cleaned_at') and not local.get('cleanup_verified_at'),'retained-original-local-pack')
    members=[m for m in local['members'] if m.get('id')==member_id];check(len(members)==1,'retained-unique-local-member');member=members[0]
    check(member.get('phase') in ('review','ready','submitted','confirmed') and not member.get('ordinary_import_token') and not member.get('retained_finalization'),'retained-local-member-phase')
    target=Path(member['destination']);source=Path(member['source'])
    from maintenance import scoped_file
    check(scoped_file(target,maintenance.worker.roots) and scoped_file(source,[Path(maintenance.settings['ddl_cache']),receipt.parent/'extracted']),'retained-selected-source-scope')
    from normalize import identity
    check(identity(source)==member['identity'],'retained-original-member-identity')
    capture_source=Path(local['capture_source'])
    additional=_capture([source,target],stream_trees=[capture_source],originals=first);_merge(first,additional)
    workflow=_sql(a.database,first['files'][str(a.database)]);catalog=_sql(a.catalog,first['files'][str(a.catalog)])
    rows=[json.loads(r) for r in workflow['rows']['records'] if json.loads(r)[:2]==['pack',pack_id]]
    check(len(rows)==1,'retained-original-native-row');row=rows[0];pack=evidence.decode_json(row[2])
    selected=[m for m in pack['members'] if m.get('id')==member_id];check(len(selected)==1,'retained-original-native-member');native_member=selected[0]
    check(pack.get('source_generation')==local['source_generation'] and not pack.get('cleanup_started') and not pack.get('cleanup_complete'),'retained-original-generation')
    from native_handoff import native_path
    check(native_path(maintenance,capture_source)==pack['source'],'retained-original-source-mapping')
    match={'issueid':member['issueid'],'comicid':member['comicid']}
    proof=a.confirmation_check(source,target,match);owner=proof['target']['authority']['owner']
    check(native_member.get('kind')==('annual' if owner['table']=='annuals' else 'issue') and native_member.get('issueid')==owner['issueid']
          and native_member.get('comicid')==owner['parentcomicid'] and native_member.get('releasecomicid')==owner['releasecomicid'],'retained-original-native-owner')
    from pack_recovery import source_state
    check(source_state(capture_source,content=True)==local['source_generation'],'retained-generation-current')
    request=dict(version=1,kind='retained-ddl-existing-target-v1',ddl_id=pack['ddl_id'],pack_id=pack_id,member_id=member_id,
        source_generation=local['source_generation'],source_sha256=member['sha256'],target_sha256=member['destination_sha256'],owner=owner,
        review_sha256=hashlib.sha256(compact({'receipt_sha256':hashlib.sha256(raw).hexdigest(),'pack_before':row,'owner':owner})).hexdigest())
    check(first['hashes'][str(target)]==request['target_sha256'] and first['hashes'][str(source)]==request['source_sha256'],'retained-payload-original')
    token=hashlib.sha256((request['ddl_id']+'\0'+pack_id+'\0'+member_id).encode()).hexdigest()
    intent=journal/(token+'.intent.json');done=journal/(token+'.done.json')
    _nodes(first,intent);first['absent']+=tuple(map(str,(intent,done)));first['nodes'][str(journal)]=five(z)
    census=a.admission();_raw(_detached(first))
    body=compact(dict(version=1,kind='retained-pack-dispatch-intent',request=request,receipt_sha256=hashlib.sha256(raw).hexdigest(),historical_import_ack=False,cleanup_grant=False))
    stamp=_journal_write(intent,body,first['nodes'][str(journal)])
    first['absent']=tuple(p for p in first['absent'] if p!=str(intent));first['files'][str(intent)]=stamp;first['hashes'][str(intent)]=hashlib.sha256(body).hexdigest();first['names'][str(journal)]=tuple(sorted((*first['names'][str(journal)],intent.name)))
    c=dict(maintenance=maintenance,maintenance_binding=maintenance_binding,authority=a,writer=a.writer,frame_bytes=compact(first),request_bytes=compact(request),request=request,token=token,
           native_target=native_path(maintenance,target),native_source=native_path(maintenance,source),receipt=receipt,receipt_bytes=raw,local_bytes=compact(local),workflow=workflow,catalog=catalog,census=census,
           intent=intent,done=done,writer_binding=(a.writer.root,a.writer.lock,a.writer.pending,a.writer.tagger_pending,a.writer.release_pending,tuple(a.writer.lock_identity),tuple(a.writer.root_identity),a.writer.local),pid=os.getpid(),thread=threading.get_ident(),deadline=time.monotonic()+90,phase='prepared')
    action=object.__new__(RetainedPackAction);_CORES[action]=c
    _transport(maintenance);check(_binding(maintenance)==maintenance_binding,'retained-original-Maintenance')
    # Final direct original closure follows registry/copy/serialization helpers.
    _raw(_detached(first))
    for p,n in first['names'].items():
        if tuple(sorted(os.listdir(p)))!=tuple(n):raise ValueError('retained-namespace')
    for p,v in first['nodes'].items():
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(v):raise ValueError('retained-node')
    for p,v in first['files'].items():
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(v):raise ValueError('retained-file')
    for p in first['absent']:
        try:os.lstat(p)
        except FileNotFoundError:continue
        raise ValueError('retained-absence')
    for p,v in first['claims'].items():
        try:z=os.lstat(p)
        except FileNotFoundError:
            if v is None:continue
            raise ValueError('retained-claim')
        actual=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)
        if actual!=(None if v is None else tuple(v)):raise ValueError('retained-claim')

    return action


def _merge(first,other):
    for key in ('files','nodes','hashes','claims','names','attrs'):
        for p,v in other[key].items():
            check(p not in first[key] or first[key][p]==v,'retained-original-conflict');first[key].setdefault(p,v)
    first['absent']=tuple(dict.fromkeys((*first['absent'],*other['absent'])))


def dispatch(action):
    c=_core(action,'prepared');m=c['maintenance'];remote_unlocked(m.worker)
    _transport(m);check(_binding(m)==c['maintenance_binding'],'retained-original-Maintenance')
    _raw(json.loads(c['frame_bytes']));c['phase']='dispatching'  # Uncertain attempts cannot finalize again.
    reply=m.retained_pack_return('retainedDeliveryFinalize',c['request_bytes'])
    _transport(m);check(_binding(m)==c['maintenance_binding'],'retained-original-Maintenance')
    check(type(reply) is bytes and 0<len(reply)<=_LIMIT,'retained-original-response')
    c['reply_bytes']=bytes(reply);c['phase']='returned'
    return action


def _map(c,data,path):
    a=current(c['maintenance'].worker);p=Path(path);root=Path(data)
    check(p.is_absolute() and '..' not in p.parts and root.is_absolute() and root!=Path('/'),'retained-native-path')
    if p.is_relative_to(root/'media-writer'):return a.writer.root/p.relative_to(root/'media-writer')
    if p.is_relative_to(root):return a.config/p.relative_to(root)
    m=c['maintenance'];cache=Path(m.settings['mylar_ddl_cache'])
    if p.is_relative_to(cache):return Path(m.settings['ddl_cache'])/p.relative_to(cache)
    if p==root:return a.config
    # No same-path fallback or fixture alias can admit producer sources.
    return a.mapped(str(p))


def _transition(c,answer):
    request=c['request'];t=answer['transition'];check(type(t) is dict and set(t)=={'version','kind','request','native_data_root','record_bytes','pack_before_row','pack_after_row','workflow_before','original_vectors','committed_vectors','committed_hashes','native_source_root','native_sources'},'retained-export-schema')
    check(type(t['version']) is int and t['version']==1 and t['kind']=='retained-pack-two-row-transition' and compact(t['request'])==c['request_bytes'],'retained-export-request')
    check(compact(t['workflow_before'])==compact(c['workflow']),'retained-original-allSQL')
    before=t['pack_before_row'];after=t['pack_after_row'];check(type(before) is list and len(before)==4 and type(after) is list and len(after)==4 and after[:2]==before[:2] and compact(after[3])==compact(before[3]),'retained-exact-pack-row')
    pack=evidence.decode_json(before[2]);wanted=json.loads(compact(pack));found=[m for m in wanted['members'] if m.get('id')==request['member_id']];check(len(found)==1,'retained-exact-member')
    original=evidence.decode_json(t['record_bytes'])
    record_keys={'version','kind','token','request','source','target','original_event','original_vectors','pack_before','pack_after','historical_import_ack','ordinary_import_grant','cleanup_grant','mutation_authority','publication_acceptance','reader_index_acceptance','automatic_replay'}
    check(type(original) is dict and set(original)==record_keys and type(original['version']) is int and original['version']==1 and original['kind']=='fresh-retained-backend-finalization','retained-original-record-schema')
    check(compact(original['request'])==c['request_bytes'] and compact(original['original_vectors'])==compact(t['original_vectors']),'retained-original-record-types')
    target=original['target'];check(target==c['native_target'],'retained-exact-current-target')
    journal=Path(t['native_data_root'])/'retained-delivery-v1'/c['token']
    check(original['source']==c['native_source'] or (Path(original['source']).parent==journal and Path(original['source']).name.startswith('source.')),'retained-owning-source-copy')
    committed=dict(t['committed_vectors']['files9'])
    check(set(original['original_event'])=={'ack','intent','issued'},'retained-original-event-schema')
    for role,name in (('ack','accepted.json'),('intent','intent.json'),('issued','issued.json')):
        ref=original['original_event'][role];check(type(ref) is list and len(ref)==3 and ref[0]==str(journal/name) and type(ref[1]) is str and re.fullmatch('[a-f0-9]{64}',ref[1]) and type(ref[2]) is list and len(ref[2])==9 and all(type(n) is int for n in ref[2]) and committed.get(ref[0])==ref[2] and t['committed_hashes'].get(ref[0])==ref[1],'retained-original-event-reference')
    found[0].update(phase='retained-accepted',retained_finalization=c['token'],destination=target,destination_sha256=request['target_sha256']);wanted['phase']='review'
    check(after==[before[0],before[1],native_compact(wanted).decode(),before[3]],'retained-only-member-change')
    check(original['request']==request and original['token']==c['token'] and compact(original['pack_before'])==compact(pack) and compact(original['pack_after'])==compact(wanted),'retained-record-join')
    rights=('historical_import_ack','ordinary_import_grant','cleanup_grant','mutation_authority','publication_acceptance','reader_index_acceptance','automatic_replay')
    check(all(answer[k] is False and original[k] is False for k in rights),'retained-false-rights')
    check(hashlib.sha256(t['record_bytes'].encode()).hexdigest()==answer['record_sha256'],'retained-record-bytes')
    expected=json.loads(compact(c['workflow']));rows=expected['rows']['records'];old=native_compact(before).decode();check(rows.count(old)==1,'retained-original-row')
    rows.remove(old);rows.extend((native_compact(after).decode(),native_compact(['retained_delivery_final',c['token'],t['record_bytes'],0.0]).decode()));rows.sort()
    return t,expected,target


def consume(action):
    c=_core(action,'returned');c['phase']='consuming';_transport(c['maintenance']);check(_binding(c['maintenance'])==c['maintenance_binding'],'retained-original-Maintenance');a=current(c['maintenance'].worker)
    check(a.writer.local is c['writer'].local,'retained-same-Writer');evidence.ordinary_purpose(a.writer)
    envelope=evidence.decode_json(c['reply_bytes']);check(type(envelope) is dict and set(envelope)=={'success','data'} and envelope['success'] is True,'retained-exact-envelope')
    answer=envelope['data'];check(type(answer) is dict and set(answer)=={'version','outcome','token','record_kind','record_sha256','committed','historical_import_ack','ordinary_import_grant','cleanup_grant','mutation_authority','publication_acceptance','reader_index_acceptance','automatic_replay','transition'} and type(answer['version']) is int and answer['version']==1,'retained-answer-schema')
    check(answer['token']==c['token'] and answer['outcome']=='fresh-retained-backend-finalized' and answer['record_kind']=='retained_delivery_final','retained-exact-answer')
    t,expected,target=_transition(c,answer)
    current_db=tuple(answer['committed']['signature9']);check(str(a.database)==str(_map(c,t['native_data_root'],answer['committed']['path'])),'retained-committed-path')
    check(_sql(a.database,current_db)==expected,'retained-exact-two-row-SQL')
    original_frame=json.loads(c['frame_bytes'])
    original_db=original_frame['files'][str(a.database)];check(current_db[:2]==tuple(original_db[:2]) and current_db[5:]==tuple(original_db[5:]),'retained-workflow-incarnation')
    # Native same-value catalog CAS may change only its physical write signature.
    native_now=tuple(nine(os.lstat(a.catalog)));check(native_now[:2]==tuple(original_frame['files'][str(a.catalog)][:2]) and native_now[5:]==tuple(original_frame['files'][str(a.catalog)][5:]) and _sql(a.catalog,native_now)==c['catalog'],'retained-catalog-preserved')
    frame={k:(dict(v) if type(v) is dict else tuple(v)) for k,v in original_frame.items()}
    for p,v in ((str(a.database),current_db),(str(a.catalog),native_now)):frame['files'][p]=v
    check(a.admission()==c['census'],'retained-census-preserved')
    check(type(NATIVE_API_SHA) is str and re.fullmatch('[a-f0-9]{64}',NATIVE_API_SHA),'retained-installed-API-pin-unproven')
    source_pins=dict(NATIVE_SOURCE_PINS,**{'api.py':NATIVE_API_SHA})
    image_rows=t['native_sources'];source_root=Path(t['native_source_root'])
    check(str(source_root)==NATIVE_SOURCE_ROOT and type(image_rows) is list and {Path(r['path']).name for r in image_rows}==set(source_pins) and len(image_rows)==5,'retained-exact-installed-source-graph')
    image_files={};image_nodes=set(map(str,(source_root,*source_root.parents)))
    for row in image_rows:
        path=Path(row['path']);check(path.parent==source_root and row['sha256']==source_pins[path.name] and len(row['signature9'])==9 and all(type(n) is int for n in row['signature9']),'retained-installed-source-original')
        image_files[str(path)]=tuple(row['signature9'])
    producer=t['committed_vectors'];check(type(producer) is dict and set(producer)=={'files9','nodes5','absent','namespaces','claims'},'retained-producer-vectors')
    for raw,v in producer['files9']:
        if raw in image_files:
            check(tuple(v)==image_files[raw] and t['committed_hashes'][raw]==source_pins[Path(raw).name],'retained-immutable-image-source');continue
        p=str(_map(c,t['native_data_root'],raw));v=tuple(v);check(len(v)==9 and all(type(n) is int for n in v),'retained-vector-types')
        check(p not in frame['files'] or tuple(frame['files'][p])==v,'retained-producer-original-conflict');frame['files'][p]=v
        digest=t['committed_hashes'][raw];check(type(digest) is str and re.fullmatch('[a-f0-9]{64}',digest),'retained-producer-digest')
        # Known untouched library entries keep only original raw facts; do not re-stream them.
        if p in original_frame['hashes'] or p not in original_frame['files']:
            check(hashlib.sha256(_read(p,v)).hexdigest()==digest,'retained-producer-bytes');frame['hashes'][p]=digest
    for raw,v in producer['nodes5']:
        if raw in image_nodes:
            check(type(v) is list and len(v)==5 and all(type(n) is int for n in v) and v[2]&0o170000==0o040000,'retained-image-node-original');continue
        p=str(_map(c,t['native_data_root'],raw));v=tuple(v);check(len(v)==5 and all(type(n) is int for n in v),'retained-node-types')
        check(p not in frame['nodes'] or tuple(frame['nodes'][p])==v,'retained-original-node-conflict');frame['nodes'][p]=v
    for raw,names in producer['namespaces']:
        p=str(_map(c,t['native_data_root'],raw));names=tuple(names);check(p not in frame['names'] or tuple(frame['names'][p])==names,'retained-original-census-conflict');frame['names'][p]=names
    for raw,v in producer['claims']:
        p=str(_map(c,t['native_data_root'],raw));v=None if v is None else tuple(v);check(p not in frame['claims'] or (None if frame['claims'][p] is None else tuple(frame['claims'][p]))==v,'retained-original-claim-conflict');frame['claims'][p]=v
    frame['absent']=tuple(dict.fromkeys((*frame['absent'],*(str(_map(c,t['native_data_root'],p)) for p in producer['absent']))))
    local=json.loads(c['local_bytes']);found=[m for m in local['members'] if m.get('id')==c['request']['member_id']];check(len(found)==1,'retained-local-CAS-member')
    found[0].update(phase='retained-accepted',retained_finalization=c['token'],destination=str(_map(c,t['native_data_root'],target)),destination_sha256=c['request']['target_sha256']);local['phase']='review'
    encoded=compact(local);report=compact(dict(version=1,kind='retained-pack-worker-observation',token=c['token'],request=c['request'],reply_sha256=hashlib.sha256(c['reply_bytes']).hexdigest(),historical_import_ack=False,cleanup_grant=False,reader_index_acceptance=False))
    # Bind originals and final values BEFORE any output callback.
    receipt=c['receipt'];temp=receipt.with_name('.retained-'+c['token']+'.new');_nodes(frame,temp)
    check(not os.path.lexists(temp),'retained-exclusive-CAS-temp');frame['absent']+=tuple([str(temp)])
    _raw(_detached(frame));stamp=_journal_write(temp,encoded,frame['nodes'][str(receipt.parent)],frame['attrs'][str(receipt)])
    frame['absent']=tuple(p for p in frame['absent'] if p!=str(temp));frame['files'][str(temp)]=stamp;frame['attrs'][str(temp)]=frame['attrs'][str(receipt)];frame['names'][str(receipt.parent)]=tuple(sorted((*frame['names'][str(receipt.parent)],temp.name)))
    _raw(_detached(frame))
    w=a.writer
    if (w.root,w.lock,w.pending,w.tagger_pending,w.release_pending,tuple(w.lock_identity),tuple(w.root_identity),w.local)!=c['writer_binding'] or getattr(w.local[1],'depth',0)<=0 or any(getattr(w.local[1],k,False) for k in ('allow_pending','allow_tagger_pending','allow_release_pending')):raise ValueError('retained-final-Writer')
    d=os.open(receipt.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        check(five(os.fstat(d))==tuple(frame['nodes'][str(receipt.parent)]),'retained-receipt-parent-FD');_raw(_detached(frame))
        _transport(c['maintenance']);check(_binding(c['maintenance'])==c['maintenance_binding'],'retained-original-Maintenance')
        for p,n in frame['names'].items():
            if tuple(sorted(os.listdir(p)))!=tuple(n):raise ValueError('retained-namespace')
        for p,v in frame['nodes'].items():
            z=os.lstat(p)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(v):raise ValueError('retained-node')
        for p,v in frame['files'].items():
            z=os.lstat(p)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(v):raise ValueError('retained-file')
        for p in frame['absent']:
            try:os.lstat(p)
            except FileNotFoundError:continue
            raise ValueError('retained-absence')
        for p,v in frame['claims'].items():
            try:z=os.lstat(p)
            except FileNotFoundError:
                if v is None:continue
                raise ValueError('retained-claim')
            actual=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)
            if actual!=(None if v is None else tuple(v)):raise ValueError('retained-claim')
        w=a.writer
        if (w.root,w.lock,w.pending,w.tagger_pending,w.release_pending,tuple(w.lock_identity),tuple(w.root_identity),w.local)!=c['writer_binding'] or getattr(w.local[1],'depth',0)<=0 or any(getattr(w.local[1],k,False) for k in ('allow_pending','allow_tagger_pending','allow_release_pending')):raise ValueError('retained-final-Writer')
        os.replace(temp.name,receipt.name,src_dir_fd=d,dst_dir_fd=d);os.fsync(d)
        z=os.stat(receipt.name,dir_fd=d,follow_symlinks=False)
        actual=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
        if actual[:4]!=stamp[:4] or actual[5:]!=stamp[5:]:raise ValueError('retained-owned-rename-incarnation')
        stamp=actual  # Sole owned rename ctime transition; all other fields unchanged.
    finally:os.close(d)
    frame['files'].pop(str(temp));frame['attrs'].pop(str(temp));frame['names'][str(receipt.parent)]=tuple(n for n in frame['names'][str(receipt.parent)] if n!=temp.name);frame['files'][str(receipt)]=stamp;frame['hashes'][str(receipt)]=hashlib.sha256(encoded).hexdigest();frame['absent']+=tuple([str(temp)])
    done_stamp=_journal_write(c['done'],report,frame['nodes'][str(c['done'].parent)])
    frame['absent']=tuple(p for p in frame['absent'] if p!=str(c['done']));frame['files'][str(c['done'])]=done_stamp;frame['names'][str(c['done'].parent)]=tuple(sorted((*frame['names'][str(c['done'].parent)],c['done'].name)))
    check(_read(receipt,stamp,_LIMIT)==encoded,'retained-receipt-readback')
    _transport(c['maintenance']);check(_binding(c['maintenance'])==c['maintenance_binding'],'retained-original-Maintenance')
    # Final copied physical closure after ALL write/SQL/serialization helpers.
    _raw(_detached(frame))
    for p,n in frame['names'].items():
        if tuple(sorted(os.listdir(p)))!=tuple(n):raise ValueError('retained-namespace')
    for p,v in frame['nodes'].items():
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(v):raise ValueError('retained-node')
    for p,v in frame['files'].items():
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(v):raise ValueError('retained-file')
    for p in frame['absent']:
        try:os.lstat(p)
        except FileNotFoundError:continue
        raise ValueError('retained-absence')
    for p,v in frame['claims'].items():
        try:z=os.lstat(p)
        except FileNotFoundError:
            if v is None:continue
            raise ValueError('retained-claim')
        actual=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)
        if actual!=(None if v is None else tuple(v)):raise ValueError('retained-claim')

    w=a.writer
    if (w.root,w.lock,w.pending,w.tagger_pending,w.release_pending,tuple(w.lock_identity),tuple(w.root_identity),w.local)!=c['writer_binding'] or getattr(w.local[1],'depth',0)<=0 or any(getattr(w.local[1],k,False) for k in ('allow_pending','allow_tagger_pending','allow_release_pending')):raise ValueError('retained-final-Writer')
    # Final physical callbacks cannot change the original configuration/transport.
    m=c['maintenance']
    if (m.state,m.worker,tuple(m.worker.roots),m.worker.config['writer_state'],m.settings.get('ddl_cache'),m.settings.get('mylar_ddl_cache'),
            m.worker.config['mylar'].get('url'),m.worker.config['mylar'].get('config_dir','/mylar'),
            tuple((row['native'],row['worker']) for row in m.worker.config['publication_roots']))!=c['maintenance_binding']:
        raise ValueError('retained-final-Maintenance')
    if (getattr(m.retained_pack_return,'__func__',None) is not _RETURN or _RETURN.__code__ is not _RETURN_CODE
            or _RETURN.__globals__.get('request') is not _REQUEST or _REQUEST.__code__ is not _REQUEST_CODE):
        raise ValueError('retained-final-transport')
    c['phase']='consumed'
    return {'outcome':'retained-observed','cleanup_grant':False,'ordinary_import_grant':False,'reader_index_acceptance':False}


def run_selected(maintenance):
    if not ENABLED:return 0
    selected=_SELECTED.pop(id(maintenance),None)
    if selected is None:return 0
    check(selected[:3]==(maintenance,os.getpid(),threading.get_ident()),'retained-selected-lifetime')
    writer=Writer(maintenance.worker.config['writer_state'],create=False)
    with writer.hold(timeout=0),scope(maintenance.worker,writer):action=prepare(maintenance,*selected[3:])
    dispatch(action)
    with writer.hold(timeout=0),scope(maintenance.worker,writer):consume(action)
    return 1
