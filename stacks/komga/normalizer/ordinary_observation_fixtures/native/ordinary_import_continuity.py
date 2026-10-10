"""Owning ordinary import lineage; original completion rows never change.

Only exact native Rename or preserved Tagging instances produce a successor.
This is observational history and supplies no import, publication or replay right.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
import weakref

_PENDING=weakref.WeakKeyDictionary()
_NAME='ordinary-import-continuity-v1'
_LIMIT=256


def _modules():
    import mylar
    from mylar import ordinary_import_history as history, native_writers as writers
    from mylar import publication_guard as guard, publication_native as native
    from mylar import publication_rename as rename, publication_transaction as tagging
    from mylar.media_writer import Writer
    return mylar,history,writers,guard,native,rename,tagging,Writer


def _bytes(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def _writer(writer):
    mylar,history,writers,guard,native,rename,tagging,Writer=_modules()
    if type(writer) is not Writer or not writers.publication_mode() or not writers.active() or not writer.local[1].depth:
        raise ValueError('Owning native Writer required')
    writers.admission(writer)
    fresh=writers.owner()
    if (fresh.root!=writer.root or fresh.local is not writer.local or fresh.root_identity!=writer.root_identity
            or fresh.lock_identity!=writer.lock_identity or any(getattr(fresh,key)!=getattr(writer,key)
                for key in ('lock','pending','tagger_pending','release_pending'))):
        raise ValueError('Native Writer identity changed')
    return mylar,history,writers,guard,native,rename,tagging


def initialize(data):
    """Preparation only: call before the operation backup/protected proof baseline."""
    root=Path(data)/_NAME
    if not root.exists():
        root.mkdir(mode=0o700)
        fd=os.open(root.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)
    info=root.lstat()
    if info.st_mode&0o170000!=0o040000 or info.st_mode&0o777!=0o700 or info.st_uid!=os.geteuid():
        raise ValueError('Private import lineage directory required')
    return root


def _root(mylar):
    root=Path(mylar.DATA_DIR)/_NAME;info=root.lstat()
    if info.st_mode&0o170000!=0o040000 or info.st_mode&0o777!=0o700 or info.st_uid!=os.geteuid():
        raise ValueError('Import lineage preparation required')
    return root


def _read(history,path):
    fact,nodes=history._file(path)
    if fact['signature'][5]&0o777!=0o600:raise ValueError('Private lineage record required')
    raw=Path(path).read_bytes()
    if len(raw)>1024*1024 or hashlib.sha256(raw).hexdigest()!=fact['sha256']:
        raise ValueError('Lineage bytes changed')
    value=json.loads(raw)
    if _bytes(value)!=raw:raise ValueError('Canonical lineage record required')
    identity=value.pop('_created',None)
    signature=fact['signature']
    if type(identity) is not list or len(identity)!=6 or any(type(n) is not int for n in identity) or identity!=[signature[0],signature[1],*signature[5:]]:raise ValueError('Original lineage record incarnation changed')
    return value,fact,nodes


def _write(history,path,value,*,expected_nodes=None):
    raw=_bytes(value)
    if len(raw)>1024*1024:raise ValueError('Lineage exceeds bound')
    nodes=history._nodes(path)
    if expected_nodes is not None:
        initial=dict(expected_nodes)
        for parent,vector in nodes:
            if parent in initial and tuple(vector)!=tuple(initial[parent]):raise ValueError('Original lineage parent changed')
        nodes=list(initial.items())+[(p,v) for p,v in nodes if p not in initial]
    handles=[]
    try:
        parent=Path(path).parent
        expected=dict(nodes)
        current=Path('/')
        directory=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);handles.append(directory)
        info=os.fstat(directory)
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=tuple(expected['/']):raise ValueError('Lineage root FD changed')
        for part in parent.parts[1:]:
            current=current/part
            directory=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory);handles.append(directory)
            info=os.fstat(directory)
            if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=expected[str(current)]:raise ValueError('Lineage directory FD changed')
        fd=os.open(path.name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory);handles.append(fd)
        info=os.fstat(fd)
        created=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)
        if created[2]&0o170000!=0o100000 or created[2]&0o7777!=0o600 or created[3:]!=(os.geteuid(),os.getegid(),1):raise ValueError('Intended lineage created metadata required')
        if '_created' in value:raise ValueError('Caller record identity refused')
        raw=_bytes(dict(value,_created=list(created)))
        if len(raw)>1024*1024:raise ValueError('Lineage exceeds bound')
        position=0
        while position<len(raw):
            count=os.write(fd,raw[position:])
            if count<=0:raise ValueError('Lineage short write')
            position+=count
        os.fsync(fd);os.lseek(fd,0,os.SEEK_SET)
        if os.read(fd,len(raw)+1)!=raw:raise ValueError('Lineage readback failed')
        info=os.fstat(fd)
        result=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)
        if (result[0],result[1],*result[5:])!=created:raise ValueError('Original lineage created metadata changed')
        os.fsync(directory)
        answer={'signature':list(result),'sha256':hashlib.sha256(raw).hexdigest()}
        history._close(nodes,[(str(path),result)])
        # The created FD/path identity survives every readback/fsync/helper.
        for parent,vector in nodes:
            info=os.lstat(parent)
            if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=tuple(vector):raise ValueError('Original lineage output parent changed')
        info=os.fstat(fd)
        if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=result:raise ValueError('Original lineage output FD changed')
        info=os.lstat(path)
        if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=result:raise ValueError('Original lineage output leaf changed')
        return answer
    finally:
        for fd in reversed(handles):os.close(fd)


def _original(history,token):
    with history._database() as db:
        rows=db.execute('SELECT attempt,ack FROM completions WHERE token=?',(token,)).fetchall()
    if len(rows)!=1 or rows[0][1] is None:raise ValueError('Original import ACK required')
    raw,ack=rows[0]
    value=json.loads(raw);done=json.loads(ack)
    if (type(value.get('version')) is not int or value['version']!=1 or value.get('token')!=token
            or type(done.get('version')) is not int or done['version']!=1
            or value['owner']!=done['owner'] or value['payload']!=done['payload']):
        raise ValueError('Original import ACK changed')
    return {'token':token,'attempt':raw,'ack':ack},value,done


def _terminal(writer,record):
    mylar,history,writers,guard,native,rename,tagging=_writer(writer)
    if record['kind']=='rename':
        job=record['job'];witness=rename.terminal(writer,job)
        if (job['phase'] not in ('committed','rejected') or witness['intent']['owner']!=record['owner'] or witness['intent']['payload']!=record['payload']
                or job['request']['source']!=record['source'] or job['request']['sha256']!=record['before']['sha256']
                or list(witness['intent']['observed'][0]['signature'])!=record['before']['signature']):
            raise ValueError('Exact closed rename required')
        path=writer.root/'release-completed-v1'/(job['key']+'.json')
    elif record['kind']=='preserved-metadata':
        job=record['job'];policy=job['policy']
        if job['source']!=record['source'] or job['source_sha256']!=record['before']['sha256'] or job['source_signature']!=record['before']['signature']:raise ValueError('Metadata original preimage changed')
        tagging.closed_supplement(writer,token=job['token'],source=Path(record['destination']),
            before_sha256=job['source_sha256'],owner=record['owner'],payload=record['payload'],
            census=job['census'],preservation=policy['preservation'],policy=policy['supplement'])
        path=writer.root/'tagger-completed-v1'/(job['token']+'.json')
    else:raise ValueError('Unsupported lineage kind')
    fact,nodes=history._file(path)
    if fact!=record['terminal']:raise ValueError('Original owning terminal changed')
    proof=native.require(Path(record['destination']),issueid=record['owner']['issueid'],comicid=record['owner']['parentcomicid'])
    if proof['owner']!=record['owner'] or proof['inventory']['payload']!=record['payload']:
        raise ValueError('Current owner or payload changed')
    return str(path),fact,nodes


def _controls(mylar,writer):
    paths=(Path(mylar.DATA_DIR)/'mylar.db',Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json',writer.lock)
    files=[];nodes={}
    for path in paths:
        info=os.lstat(path)
        files.append((str(path),(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)))
        for parent in path.parents:
            info=os.lstat(parent);value=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)
            if str(parent) in nodes and nodes[str(parent)]!=value:raise ValueError('Conflicting original authority ancestor')
            nodes[str(parent)]=value
    return files,list(nodes.items())


def _observe(writer,token,owner,destination,*,export=False):
    mylar,history,writers,guard,native,rename,tagging,_=_modules()
    controls,control_nodes=_controls(mylar,writer)
    root=Path(mylar.DATA_DIR)/_NAME
    info=os.lstat(root);root_original=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)
    _writer(writer)
    from mylar import publication_api,publication_archive_owned
    controller=publication_api.Controller(mylar.DATA_DIR,[mylar.CONFIG.DESTINATION_DIR])
    _,claims,claim_nodes=publication_archive_owned.catalog(controller,owner,guard,time.monotonic()+guard.TIMEOUT)
    claim_originals=tuple((str(path),None if value is None else tuple(value)) for path,value in claims.items())
    if _root(mylar)!=root:raise ValueError('Lineage root changed')
    root_nodes=history._nodes(root/'record')
    root_nodes.append((str(root),root_original))
    history_path=Path(mylar.DATA_DIR)/history._NAME
    history_fact,history_nodes=history._file(history_path)
    original,attempt,ack=_original(history,token)
    namespace=tuple(sorted(x.name for x in root.iterdir()))
    if any(re.fullmatch(r'(?:rename|preserved-metadata)-[0-9a-f]{32,64}\.(?:pending|done)\.json',name) is None for name in namespace):raise ValueError('Foreign lineage namespace')
    paths=sorted(root.glob('*.done.json'))
    if len(paths)>_LIMIT or len(namespace)>_LIMIT*2:raise ValueError('Lineage count exceeds bound')
    journal_originals=[]
    for name in namespace:
        path=root/name;info=os.lstat(path)
        vector=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)
        if vector[5]&0o170000!=0o100000 or vector[5]&0o7777!=0o600 or vector[6:9]!=(os.geteuid(),os.getegid(),1):raise ValueError('Private original lineage leaf required')
        journal_originals.append((str(path),vector))
    records=[];files=journal_originals+controls+[(str(history_path),history_fact['signature'])];nodes=control_nodes+root_nodes+history_nodes+[(str(path),tuple(value)) for path,value in claim_nodes.items()]
    for path in paths:
        value,fact,parents=_read(history,path);files.append((str(path),fact['signature']));nodes+=parents
        if type(value.get('version')) is not int or value['version']!=1 or set(value)!={'version','kind','operation','original','previous','owner','payload','source','before','job','destination','after','terminal','intent'}:raise ValueError('Exact lineage schema required')
        pending=path.with_name(path.name.replace('.done.json','.pending.json'))
        pending_value,pending_fact,pending_nodes=_read(history,pending)
        if pending_fact!=value['intent'] or pending_value!={key:value[key] for key in ('version','kind','operation','original','previous','owner','payload','source','before')}:raise ValueError('Original lineage pending receipt changed')
        files.append((str(pending),tuple(value['intent']['signature'])));nodes+=pending_nodes
        if value['original']['token']==token:
            if value['original']!=original:raise ValueError('Original ACK bytes changed')
            records.append(value)
    matches=[v for v in records if v['owner']==owner and v['destination']==destination]
    parents={v['previous'] for v in matches}
    matches=[v for v in matches if v['operation'] not in parents]
    if len(matches)!=1:raise ValueError('Unique exact import successor required')
    selected=matches[0];cursor=selected;seen=set()
    for _ in range(16):
        key=cursor['operation']
        if key in seen:raise ValueError('Cyclic import lineage')
        seen.add(key)
        if cursor['previous'] is None:
            if cursor['before']!=ack['destination'] or cursor['source']!=attempt['destination']:raise ValueError('Original ACK preimage missing')
            break
        parents=[v for v in records if v['operation']==cursor['previous']]
        if len(parents)!=1 or parents[0]['after']!=cursor['before'] or parents[0]['destination']!=cursor['source']:
            raise ValueError('Lineage preimage changed')
        cursor=parents[0]
    else:raise ValueError('Import lineage depth exceeds bound')
    if selected['owner']!=attempt['owner'] or selected['payload']!=attempt['payload']:raise ValueError('Original import owner/payload changed')
    for record in records:
        if record['kind']=='rename':witness=writer.root/'release-completed-v1'/(record['job']['key']+'.json')
        elif record['kind']=='preserved-metadata':witness=writer.root/'tagger-completed-v1'/(record['job']['token']+'.json')
        else:raise ValueError('Unknown owning terminal')
        original_terminal,parents=history._file(witness)
        if original_terminal!=record['terminal']:raise ValueError('Historical owning terminal changed')
        nodes+=parents;files.append((str(witness),record['terminal']['signature']))
    terminal,terminal_fact,parents=_terminal(writer,selected);nodes+=parents;files.append((terminal,terminal_fact['signature']))
    current,parents=history._file(destination);nodes+=parents;files.append((destination,current['signature']))
    if current!=selected['after']:raise ValueError('Import successor destination changed')
    if history._file(history_path)[0]!=history_fact:raise ValueError('Original ACK history changed')
    absent=[str(history_path)+s for s in ('-journal','-wal','-shm')]
    absent += [str(Path(mylar.DATA_DIR)/name)+s for name in ('mylar.db','workflow.sqlite') for s in ('-journal','-wal','-shm')]
    absent += [str(writer.root/name) for name in ('normalizer-v1.pending','tagger-v2.pending','release-v1.pending','tagger-publication-v1.json','nested-derivative-v1.json','tagger-recovery-v1.pending','negative-retirement-v1.pending','negative-retirement-v1.terminal-pending','archive-repair-v1.pending','archive-repair-v1.terminal-pending')]
    exported=None
    if export:
        # Every hash is bound to the already retained original vector, never
        # adopted from a refreshed read. The outer authenticated exporter owns
        # serialization and another complete raw closure of these same facts.
        original_files={}
        original_nodes={}
        for path,vector in files:
            vector=tuple(vector)
            if path in original_files and original_files[path]!=vector:raise ValueError('Conflicting lineage file')
            original_files[path]=vector
        for path,vector in nodes:
            vector=tuple(vector)
            if path in original_nodes and original_nodes[path]!=vector:raise ValueError('Conflicting lineage node')
            original_nodes[path]=vector
        hashes=[]
        for path,vector in original_files.items():
            fact,_=history._file(path)
            if tuple(fact['signature'])!=vector:raise ValueError('Export original lineage file changed')
            hashes.append(dict(path=path,signature=list(vector),sha256=fact['sha256']))
        exported=dict(files=hashes,nodes=[[path,list(vector)] for path,vector in original_nodes.items()],
            claims=[[path,None if vector is None else list(vector)] for path,vector in claim_originals],
            absent=absent,namespaces=[dict(path=str(root),names=list(namespace))])
    history._close(nodes,files)
    if tuple(sorted(x.name for x in root.iterdir()))!=namespace:raise ValueError('Lineage namespace changed')
    # No replaceable helper after this copied original raw vector closure.
    for path,expected in nodes:
        info=os.lstat(path)
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=tuple(expected):raise ValueError('Lineage ancestor changed')
    for path,expected in files:
        info=os.lstat(path)
        if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=tuple(expected):raise ValueError('Lineage file changed')
    for path,expected in claim_originals:
        try:info=os.lstat(path)
        except FileNotFoundError:
            if expected is not None:raise ValueError('Claim disappeared')
            continue
        actual=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if (info.st_mode&0o170000)==0o040000 else info.st_nlink)
        if actual!=expected:raise ValueError('Original physical claim changed')
    for path in absent:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise ValueError('Lineage companion changed')
    return (selected,exported) if export else selected


def confirmed(token,owner,destination):
    try:
        _,_,writers,_,_,_,_,_=_modules()
        with writers.operation() as writer:_observe(writer,token,owner,destination)
        return True
    except Exception:return False
    except BaseException as error:
        from mylar import publication_guard as guard,publication_native as native
        if not isinstance(error,(native.Review,guard.Unavailable)):raise
        return False


def capture(capability):
    """Called before the exact producer's first intent/file mutation."""
    mylar,history,writers,guard,native,rename,tagging,_=_modules()
    if type(capability) not in (rename.Rename,tagging.Tagging):raise ValueError('Exact native producer required')
    if not os.path.lexists(Path(mylar.DATA_DIR)/history._NAME):return
    writer=capability.writer
    lineage_root=Path(mylar.DATA_DIR)/_NAME
    original_nodes=[]
    if os.path.lexists(lineage_root):
        for parent in (lineage_root,*lineage_root.parents):
            info=os.lstat(parent)
            original_nodes.append((str(parent),(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)))
    original_value=capability.value
    original_source=(original_value['request']['source'] if type(capability) is rename.Rename else original_value['source'])
    info=os.lstat(original_source)
    original9=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)
    _writer(writer);value=json.loads(json.dumps(original_value))
    if type(capability) is rename.Rename:
        source=value['request']['source'];kind='rename';operation=value['token']
    else:
        if value['policy'].get('role')!='preserved-supplement':return
        source=value['source'];kind='preserved-metadata';operation=value['token']
    fact,nodes=history._file(source)
    if not os.path.lexists(Path(mylar.DATA_DIR)/history._NAME):return
    expected_signature=(value['observed'][0]['signature'] if kind=='rename' else value['source_signature'])
    expected_sha=(value['request']['sha256'] if kind=='rename' else value['source_sha256'])
    if tuple(expected_signature)!=original9 or fact!={'signature':list(expected_signature),'sha256':expected_sha}:raise ValueError('Native preimage changed')
    with history._database() as db:
        if db.execute('SELECT count(*) FROM completions').fetchone()[0]>history._LIMIT:raise ValueError('Import ACK bound exceeded')
        rows=db.execute('SELECT token FROM completions WHERE ack IS NOT NULL').fetchall()
    if len(rows)>history._LIMIT:raise ValueError('Import ACK bound exceeded')
    matches=[];relevant=0
    for (token,) in rows:
        original,attempt,ack=_original(history,token)
        if attempt['owner']!=value['owner'] or attempt['payload']!=value['payload']:continue
        relevant+=1
        if attempt['destination']==source and ack['destination']==fact:
            if not history._confirmed_original(token=token,owner=value['owner'],destination=source):raise ValueError('Original ACK changed')
            matches.append((original,None))
        else:
            try:previous=_observe(writer,token,value['owner'],source)
            except (ValueError,OSError):continue
            if previous['after']==fact:matches.append((original,previous['operation']))
    if not matches:
        if relevant:raise ValueError('Original import lineage requires review')
        return
    if len(matches)!=1:raise ValueError('Ambiguous original import ACK')
    if not original_nodes:raise ValueError('Original initialized lineage directory required')
    root=_root(mylar);original,previous=matches[0]
    entry=dict(version=1,kind=kind,operation=operation,original=original,previous=previous,
        owner=value['owner'],payload=value['payload'],source=source,before=fact)
    path=root/(kind+'-'+operation+'.pending.json')
    evidence=_write(history,path,entry,expected_nodes=original_nodes)
    history._close(nodes,[(source,fact['signature'])])
    for parent,vector in original_nodes+nodes:
        info=os.lstat(parent)
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=tuple(vector):raise ValueError('Original lineage capture parent changed')
    for target,vector in ((source,tuple(fact['signature'])),(path,tuple(evidence['signature']))):
        info=os.lstat(target)
        if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=vector:raise ValueError('Original lineage capture leaf changed')
    _PENDING[capability]=(threading.get_ident(),writer,entry,path,evidence,tuple(original_nodes))


def complete(capability):
    """Called only after actual terminal clearance; lost response never replays."""
    pending=_PENDING.pop(capability,None)
    if pending is None:return
    thread,writer,entry,path,evidence,original_nodes=pending
    if thread!=threading.get_ident() or capability.writer is not writer:raise ValueError('Import successor lifetime changed')
    mylar,history,writers,guard,native,rename,tagging=_writer(writer)
    value=capability.value
    if type(capability) is rename.Rename:
        if value['phase']!='terminal':raise ValueError('Rename terminal required')
        job=guard.private_json(capability.history/(entry['operation']+'.json'))['job']
        witness=rename.terminal(writer,job);destination=witness['archive']
        terminal_path=capability.history/(entry['operation']+'.json')
    elif type(capability) is tagging.Tagging:
        if value['phase']!='released' or value['policy'].get('role')!='preserved-supplement':raise ValueError('Preserved metadata terminal required')
        job=guard.private_json(capability.history/(entry['operation']+'.json'))['job']
        destination=job['completion']['target'];terminal_path=capability.history/(entry['operation']+'.json')
    else:raise ValueError('Exact terminal producer required')
    if value['owner']!=entry['owner'] or value['payload']!=entry['payload']:raise ValueError('Import terminal owner changed')
    terminal,_=history._file(terminal_path);after,_=history._file(destination)
    record=dict(entry,job=job,destination=destination,after=after,terminal=terminal,intent=evidence)
    _terminal(writer,record)
    if _read(history,path)[:2]!=(entry,evidence):raise ValueError('Original successor intent changed')
    done=path.with_name(path.name.replace('.pending.json','.done.json'))
    done_fact=_write(history,done,record,expected_nodes=original_nodes)
    controls,control_nodes=_controls(mylar,writer)
    from mylar import publication_api,publication_archive_owned
    controller=publication_api.Controller(mylar.DATA_DIR,[mylar.CONFIG.DESTINATION_DIR])
    _,claims,claim_nodes=publication_archive_owned.catalog(controller,entry['owner'],guard,time.monotonic()+guard.TIMEOUT)
    claims=tuple((str(target),None if vector is None else tuple(vector)) for target,vector in claims.items())
    nodes=tuple(original_nodes)+tuple(control_nodes)+tuple((str(target),tuple(vector)) for target,vector in claim_nodes.items())
    original_history=Path(mylar.DATA_DIR)/history._NAME
    history_fact,history_nodes=history._file(original_history)
    nodes+=tuple(history_nodes)
    controls=tuple((target,tuple(vector)) for target,vector in controls)+((str(original_history),tuple(history_fact['signature'])),)
    absent=tuple(str(original_history)+suffix for suffix in ('-journal','-wal','-shm'))
    absent+=tuple(str(Path(mylar.DATA_DIR)/name)+suffix for name in ('mylar.db','workflow.sqlite') for suffix in ('-journal','-wal','-shm'))
    absent+=tuple(str(writer.root/name) for name in ('normalizer-v1.pending','tagger-v2.pending','release-v1.pending','tagger-publication-v1.json','nested-derivative-v1.json','tagger-recovery-v1.pending','negative-retirement-v1.pending','negative-retirement-v1.terminal-pending','archive-repair-v1.pending','archive-repair-v1.terminal-pending'))
    _observe(writer,entry['original']['token'],entry['owner'],destination)
    # Retain the original pending and just-created done identities through all
    # terminal and passive helpers; a fresh read can never replace either.
    for parent,vector in nodes:
        info=os.lstat(parent)
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=tuple(vector):raise ValueError('Original lineage completion parent changed')
    for target,vector in ((path,tuple(evidence['signature'])),(done,tuple(done_fact['signature'])),(terminal_path,tuple(terminal['signature'])),(destination,tuple(after['signature']))):
        info=os.lstat(target)
        if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=vector:raise ValueError('Original lineage completion leaf changed')

    for target,vector in controls:
        info=os.lstat(target)
        if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=vector:raise ValueError('Original lineage completion control changed')
    for target,vector in claims:
        try:info=os.lstat(target)
        except FileNotFoundError:
            if vector is not None:raise ValueError('Original lineage completion claim disappeared')
            continue
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if (info.st_mode&0o170000)==0o040000 else info.st_nlink)!=vector:raise ValueError('Original lineage completion claim changed')
    for target in absent:
        try:os.lstat(target)
        except FileNotFoundError:continue
        raise ValueError('Original lineage completion companion changed')
