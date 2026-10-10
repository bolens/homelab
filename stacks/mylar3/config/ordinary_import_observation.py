"""Source-bound native ordinary-import observation; disabled until reviewed rollout.

Only an authenticated owning API hook may call observe. The result is factual,
never a mutation, replay, index or source-cleanup capability.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
import weakref

ENABLED=False
_LIMIT=4*1024*1024
_LIVE=weakref.WeakKeyDictionary()
_ROLES=('ordinary_import_continuity','ordinary_import_history','publication_rename',
        'publication_transaction','publication_guard','publication_native',
        'native_writers','media_writer','ordinary_import_observation','api')


def _bytes(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def _nine(info):return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)


def _sources():
    import mylar
    root=Path(mylar.__path__[0]);files={};nodes={}
    # Capture ALL original leaves and ancestors before the first read callback.
    for name in _ROLES:
        module=sys.modules.get('mylar.'+name)
        if name=='ordinary_import_observation':module=sys.modules[__name__]
        if name=='api':
            # Authentication hook source is fixed in the same installed package,
            # never a caller path. Direct SDK fixtures may omit importing the
            # upstream application Api dependencies; they still retain its real
            # exact physical source bytes and do not claim HTTP acceptance.
            path=root/'api.py'
            if module is not None and Path(module.__file__)!=path:raise ValueError('Canonical API source required')
        else:
            if module is None:raise ValueError('Installed native observation source required')
            path=Path(module.__file__)
        if path!=root/(name+'.py'):raise ValueError('Canonical installed observation source required')
        vector=_nine(os.lstat(path))
        if vector[5]&0o170000!=0o100000 or vector[8]!=1:raise ValueError('Original source leaf required')
        if str(path) in files and files[str(path)]!=vector:raise ValueError('Conflicting source leaf')
        files[str(path)]=vector
        for parent in path.parents:
            info=os.lstat(parent);value=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)
            if value[2]&0o170000!=0o040000:raise ValueError('Original source ancestor required')
            if str(parent) in nodes and nodes[str(parent)]!=value:raise ValueError('Conflicting source ancestor')
            nodes[str(parent)]=value
    source_paths=set(files)
    # Original native control/journal namespace before source stream, parser,
    # catalog or terminal callbacks. Later owning vectors must conflict-join.
    data=Path(mylar.DATA_DIR);writer_root=data/'media-writer';lineage=data/'ordinary-import-continuity-v1'
    names=sorted(os.listdir(lineage))
    if len(names)>512:raise ValueError('Original lineage namespace exceeds bound')
    controls=[data/'mylar.db',data/'workflow.sqlite',data/'ordinary-import-v1.sqlite',writer_root/'writer-v1.lock',writer_root/'publication-v1.json']
    controls += [lineage/name for name in names]
    absent=[str(data/name)+suffix for name in ('mylar.db','workflow.sqlite','ordinary-import-v1.sqlite') for suffix in ('-journal','-wal','-shm')]
    absent += [str(writer_root/name) for name in ('normalizer-v1.pending','tagger-v2.pending','release-v1.pending','tagger-publication-v1.json','nested-derivative-v1.json','tagger-recovery-v1.pending','negative-retirement-v1.pending','negative-retirement-v1.terminal-pending','archive-repair-v1.pending','archive-repair-v1.terminal-pending')]
    for path in controls:
        value=_nine(os.lstat(path))
        if value[5]&0o170000!=0o100000 or value[8]!=1:raise ValueError('Original native control required')
        if str(path) in files and files[str(path)]!=value:raise ValueError('Conflicting original native control')
        files[str(path)]=value
        for parent in path.parents:
            info=os.lstat(parent);vector=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)
            if vector[2]&0o170000!=0o040000:raise ValueError('Original control ancestor required')
            if str(parent) in nodes and nodes[str(parent)]!=vector:raise ValueError('Conflicting original native node')
            nodes[str(parent)]=vector
    for path in absent:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise ValueError('Original native absence unavailable')
    deadline=time.monotonic()+30
    result=[]
    for path,vector in files.items():
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            if _nine(os.fstat(fd))!=vector:raise ValueError('Original source FD changed')
            digest=hashlib.sha256();size=0
            while chunk:=os.read(fd,1024*1024):
                size+=len(chunk)
                if size>256*1024**2 or time.monotonic()>deadline:raise ValueError('Original file exceeds observation bound')
                digest.update(chunk)
            if _nine(os.fstat(fd))!=vector:raise ValueError('Original source FD changed')
            result.append(dict(path=path,signature=list(vector),sha256=digest.hexdigest()))
        finally:os.close(fd)
    frame=dict(files=result,nodes=[[p,list(v)] for p,v in nodes.items()],claims=[],absent=absent,namespaces=[dict(path=str(lineage),names=names)])
    _close(frame)
    frame['sources']=[row for row in result if row['path'] in source_paths]
    return frame


def _close(frame):
    # No serialization, hashing or imported helper after the last raw closure.
    for row in frame['namespaces']:
        if sorted(os.listdir(row['path']))!=row['names']:raise ValueError('Original observation namespace changed')
    for path,expected in frame['nodes']:
        info=os.lstat(path)
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=tuple(expected):raise ValueError('Original observation ancestor changed')
    for row in frame['files']:
        if _nine(os.lstat(row['path']))!=tuple(row['signature']):raise ValueError('Original observation file changed')
    for path,expected in frame['claims']:
        try:info=os.lstat(path)
        except FileNotFoundError:
            if expected is not None:raise ValueError('Original observation claim disappeared')
            continue
        actual=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode&0o170000==0o040000 else info.st_nlink)
        if actual!=(None if expected is None else tuple(expected)):raise ValueError('Original observation claim changed')
    for path in frame['absent']:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise ValueError('Original observation absence changed')


def _merge(left,right):
    files={};nodes={};claims={}
    for frame in (left,right):
        for row in frame['files']:
            key=row['path']
            if key in files and files[key]!=row:raise ValueError('Conflicting observation file')
            files[key]=row
        for path,value in frame['nodes']:
            if path in nodes and nodes[path]!=value:raise ValueError('Conflicting observation ancestor')
            nodes[path]=value
        for path,value in frame['claims']:
            if path in claims and claims[path]!=value:raise ValueError('Conflicting observation claim')
            claims[path]=value
    return dict(files=list(files.values()),nodes=list(map(list,nodes.items())),claims=list(map(list,claims.items())),
                absent=list(dict.fromkeys(left['absent']+right['absent'])),namespaces=left['namespaces']+right['namespaces'])


def _admit(value,writer,history,guard,native):
    """Finite read-only admission; never calls durable worker_handoff.admit."""
    import mylar
    fields={'version','nonce','token','owner','destination','attempt_sha256','ack_sha256','target','payload','census'}
    if (type(value) is not dict or set(value)!=fields or type(value['version']) is not int or value['version']!=1
            or not re.fullmatch('[0-9a-f]{64}',value['nonce']) or not re.fullmatch('[0-9a-f]{64}',value['token'])
            or any(not re.fullmatch('[0-9a-f]{64}',value[k]) for k in ('attempt_sha256','ack_sha256','payload'))):raise ValueError('Exact ordinary observation request required')
    owner=guard.exact_owner(value['owner'])
    if owner!=value['owner']:raise ValueError('Exact regular or annual owner required')
    path=Path(value['destination']);root=Path(mylar.CONFIG.DESTINATION_DIR)
    if not path.is_absolute() or '..' in path.parts or root==Path('/') or not path.is_relative_to(root):raise ValueError('Configured exact destination required')
    if type(value['target']) is not dict or set(value['target'])!={'signature','sha256'}:raise ValueError('Exact current target required')
    census,_=guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json')
    if guard.census_value(value['census'])!=census:raise ValueError('Original request census changed')
    actual,_=history._file(path)
    if actual!=value['target']:raise ValueError('Original request target changed')
    proof=native.require(path,issueid=owner['issueid'],comicid=owner['parentcomicid'])
    if proof['owner']!=owner or proof['inventory']['payload']!=value['payload']:raise ValueError('Exact current owner/payload required')
    original,attempt,ack=history_module_original(history,value['token'])
    if (hashlib.sha256(original['attempt'].encode()).hexdigest()!=value['attempt_sha256']
            or hashlib.sha256(original['ack'].encode()).hexdigest()!=value['ack_sha256']
            or attempt['owner']!=owner or ack['owner']!=owner or attempt['payload']!=value['payload']):raise ValueError('Original ACK/attempt changed')
    return owner


def history_module_original(history,token):
    from mylar import ordinary_import_continuity
    return ordinary_import_continuity._original(history,token)


class Observation:
    __slots__=('__weakref__',)
    def payload(self):
        entry=_LIVE.get(self)
        if entry is None or entry[0]!=os.getpid() or entry[1]!=threading.get_ident():raise ValueError('Live owning observation required')
        return json.loads(entry[3])
    def close(self,envelope=None):
        entry=_LIVE.pop(self,None)
        if entry is None or entry[0]!=os.getpid() or entry[1]!=threading.get_ident() or time.monotonic()>entry[2]:raise ValueError('Original owning observation unavailable')
        if envelope is not None:
            from mylar import publication_guard as guard
            if not isinstance(envelope,str) or len(envelope.encode())>_LIMIT:raise ValueError('Exact encoded native response required')
            value=guard.decode_json(envelope)
            if type(value) is not dict or set(value)!={'success','data'} or value['success'] is not True or _bytes(value['data'])!=entry[3]:raise ValueError('Original encoded observation payload changed')
        _close(entry[4])
        frame=entry[4]
        for row in frame['namespaces']:
            if sorted(os.listdir(row['path']))!=row['names']:raise ValueError('Final observation namespace changed')
        for path,expected in frame['nodes']:
            info=os.lstat(path)
            if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=tuple(expected):raise ValueError('Final observation node changed')
        for row in frame['files']:
            info=os.lstat(row['path'])
            if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=tuple(row['signature']):raise ValueError('Final observation file changed')
        for path in frame['absent']:
            try:os.lstat(path)
            except FileNotFoundError:continue
            raise ValueError('Final observation absence changed')
        for path,expected in frame['claims']:
            try:info=os.lstat(path)
            except FileNotFoundError:
                if expected is not None:raise ValueError('Final observation claim disappeared')
                continue
            actual=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode&0o170000==0o040000 else info.st_nlink)
            if actual!=(None if expected is None else tuple(expected)):raise ValueError('Final observation claim changed')



def observe(raw):
    if not ENABLED:raise ValueError('Ordinary observation route disabled')
    from mylar import ordinary_import_continuity as continuity,ordinary_import_history as history,native_writers,publication_guard as guard,publication_native as native
    deadline=time.monotonic()+guard.TIMEOUT
    import mylar
    source_frame=_sources()
    if not isinstance(raw,str) or not 0<len(raw.encode())<=_LIMIT:raise ValueError('Observation request exceeds bound')
    value=guard.decode_json(raw)
    with native_writers.operation() as writer:
        owner=_admit(value,writer,history,guard,native)
        selected,frame=continuity._observe(writer,value['token'],owner,value['destination'],export=True)
        frame=_merge(source_frame,frame)
        result=dict(version=1,kind='ordinary-import-current-observation',nonce=value['nonce'],request_sha256=guard.canonical_digest(value),
            token=value['token'],owner=owner,native_destination=value['destination'],native_data_root=str(Path(mylar.DATA_DIR)),original_attempt_sha256=value['attempt_sha256'],original_ack_sha256=value['ack_sha256'],
            current_target=dict(selected['after'],payload=selected['payload']),native_sources=source_frame['sources'],evidence=frame,
            rights=dict(mutation=False,replay=False,cleanup=False,index_acceptance=False))
        encoded=_bytes(result)
        if len(encoded)>_LIMIT:raise ValueError('Observation response exceeds bound')
        frame=json.loads(_bytes(frame));result_object=Observation()
    # Includes admission callbacks made while native operation exits.
    if time.monotonic()>deadline:raise ValueError('Observation deadline elapsed')
    _close(frame)
    for row in frame['namespaces']:
        if sorted(os.listdir(row['path']))!=row['names']:raise ValueError('Final observation namespace changed')
    for path,expected in frame['nodes']:
        info=os.lstat(path)
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=tuple(expected):raise ValueError('Final observation node changed')
    for row in frame['files']:
        info=os.lstat(row['path'])
        if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=tuple(row['signature']):raise ValueError('Final observation file changed')
    for path in frame['absent']:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise ValueError('Final observation absence changed')
    for path,expected in frame['claims']:
        try:info=os.lstat(path)
        except FileNotFoundError:
            if expected is not None:raise ValueError('Final observation claim disappeared')
            continue
        actual=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode&0o170000==0o040000 else info.st_nlink)
        if actual!=(None if expected is None else tuple(expected)):raise ValueError('Final observation claim changed')
    _LIVE[result_object]=(os.getpid(),threading.get_ident(),deadline,encoded,frame)
    return result_object
