"""One-use live authenticated import observations; disabled by default.

No response is hydrated from disk, and no observation permits source cleanup.
Prepare/consume own Writer; dispatch is always outside it.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import re
import threading
import time
from maintenance import Maintenance as _OWNING_MAINTENANCE

_ORIGINAL_MYlar=_OWNING_MAINTENANCE.mylar
_ORIGINAL_RETURN=_OWNING_MAINTENANCE.mylar_observation

ENABLED=False
_LIMIT=4*1024*1024
_PENDING={}
_LIVE={}
_SELECTORS={}
_RESULTS={}
_MARKERS=('normalizer-v1.pending','tagger-v2.pending','release-v1.pending','tagger-publication-v1.json','nested-derivative-v1.json','tagger-recovery-v1.pending','negative-retirement-v1.pending','negative-retirement-v1.terminal-pending','archive-repair-v1.pending','archive-repair-v1.terminal-pending')


def _bytes(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def current_json(encoded):
    from publication_guard import evidence
    if type(encoded) is not bytes or len(encoded)>_LIMIT:raise ValueError('Bounded original bytes required')
    return evidence.decode_json(encoded)


def _nine(info):return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)


def _capture(paths,absent=(),namespaces=()):
    """Complete first vectors before any hash/read callback; no fresh adoption."""
    files={};nodes={}
    for raw in list(paths)+list(absent):
        path=Path(raw)
        if not path.is_absolute() or '..' in path.parts:raise ValueError('Exact observation path required')
        if str(path) not in set(map(str,absent)):
            vector=_nine(os.lstat(path))
            if vector[5]&0o170000!=0o100000 or vector[8]!=1:raise ValueError('Original regular file required')
            if str(path) in files and files[str(path)]!=vector:raise ValueError('Conflicting observation file')
            files[str(path)]=vector
        for parent in path.parents:
            info=os.lstat(parent);vector=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)
            if vector[2]&0o170000!=0o040000:raise ValueError('Original directory required')
            if str(parent) in nodes and nodes[str(parent)]!=vector:raise ValueError('Conflicting observation node')
            nodes[str(parent)]=vector
    for row in namespaces:
        for parent in (Path(row['path']),*Path(row['path']).parents):
            info=os.lstat(parent);vector=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)
            if vector[2]&0o170000!=0o040000:raise ValueError('Original namespace directory required')
            if str(parent) in nodes and nodes[str(parent)]!=vector:raise ValueError('Conflicting original namespace node')
            nodes[str(parent)]=vector
    for path in absent:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise ValueError('Original observation absence unavailable')
    deadline=time.monotonic()+30
    rows=[]
    for path,vector in files.items():
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            if _nine(os.fstat(fd))!=vector:raise ValueError('Original observation FD changed')
            digest=hashlib.sha256();size=0
            while chunk:=os.read(fd,1024*1024):
                size+=len(chunk)
                if size>256*1024**2 or time.monotonic()>deadline:raise ValueError('Observation file exceeds bound')
                digest.update(chunk)
            if _nine(os.fstat(fd))!=vector:raise ValueError('Original observation FD changed')
            rows.append(dict(path=path,signature=list(vector),sha256=digest.hexdigest()))
        finally:os.close(fd)
    frame=dict(files=rows,nodes=[[p,list(v)] for p,v in nodes.items()],claims=[],absent=list(map(str,absent)),namespaces=list(namespaces))
    _close(frame);return frame


def _claims_close(claims):
    for path,expected in claims:
        try:info=os.lstat(path)
        except FileNotFoundError:
            if expected is not None:raise ValueError('Original native claim disappeared')
            continue
        actual=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode&0o170000==0o040000 else info.st_nlink)
        if expected is None or actual!=tuple(expected):raise ValueError('Original native claim changed')


def _close(frame):
    _claims_close(frame['claims'])
    for row in frame['namespaces']:
        if sorted(os.listdir(row['path']))!=row['names']:raise ValueError('Original observation namespace changed')
    for path,expected in frame['nodes']:
        info=os.lstat(path)
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=tuple(expected):raise ValueError('Original observation node changed')
    for row in frame['files']:
        if _nine(os.lstat(row['path']))!=tuple(row['signature']):raise ValueError('Original observation file changed')
    for path in frame['absent']:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise ValueError('Original observation absence changed')


def defer(maintenance,source,match,target):
    if not ENABLED:return
    from publication_guard import current
    current(maintenance.worker)  # Selector only; never an admission/receipt.
    key=(id(maintenance),str(source),_bytes(match),str(target))
    if len(_SELECTORS)>=4096 and key not in _SELECTORS:raise ValueError('Deferred selector bound exceeded')
    _SELECTORS[key]=(maintenance,str(source),dict(match),str(target),os.getpid(),threading.get_ident())


def originals(maintenance,source,target):
    """Called before receipt/authority/hash helpers by the actual ACK reader."""
    if not ENABLED:return None
    from publication_guard import current
    authority=current(maintenance.worker)
    if os.path.lexists(authority.writer.pending):return None  # No observation proof admitted across owning clear.
    config=Path(maintenance.worker.config['mylar'].get('config_dir','/mylar'))
    writer=Path(maintenance.worker.config['writer_state'])
    imports=maintenance.state/'imports';names=sorted(os.listdir(imports))
    if len(names)>4096 or any(not name.endswith('.json') for name in names):raise ValueError('Import receipt namespace unavailable')
    paths=[config/'config.ini',config/'mylar.db',config/'workflow.sqlite',config/'ordinary-import-v1.sqlite',writer/'writer-v1.lock',Path(target)]
    absent=[Path(str(config/name)+suffix) for name in ('mylar.db','workflow.sqlite','ordinary-import-v1.sqlite') for suffix in ('-journal','-wal','-shm')]
    absent+=[writer/name for name in _MARKERS]
    for path in (Path(source),writer/'publication-v1.json'):
        (paths if os.path.lexists(path) else absent).append(path)
    paths += [imports/name for name in names]
    # Source modules are original local production identities, not caller pins.
    import ordinary_import_ack,native_handoff,publication_guard,maintenance as owning_maintenance,normalize
    paths += [Path(module.__file__) for module in (ordinary_import_ack,native_handoff,publication_guard,owning_maintenance,normalize)]
    paths.append(Path(__file__))
    namespaces=[dict(path=str(imports),names=names)]
    for folder in dict.fromkeys([Path(target).parent,*[Path(row['worker']) for row in maintenance.worker.config.get('publication_roots',[])]]):
        contents=sorted(os.listdir(folder))
        if len(contents)>4096:raise ValueError('Original target namespace exceeds bound')
        namespaces.append(dict(path=str(folder),names=contents))
    return _capture(paths,absent,namespaces)


def _write(path,value):
    data=_bytes(value)
    if len(data)>_LIMIT:raise ValueError('Observation record exceeds bound')
    original_parents=_capture([],absent=[path])['nodes']
    parent=path.parent;names=sorted(os.listdir(parent));info=os.lstat(parent);parent5=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)
    if parent5[2]&0o170000!=0o040000 or parent5[2]&0o7777!=0o700:raise ValueError('Private observation directory required')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    created=_nine(os.fstat(fd));identity=(created[0],created[1],created[5],created[6],created[7],created[8])
    if identity[2:]!=(0o100600,os.geteuid(),os.getegid(),1):raise ValueError('Private original created FD required')
    try:
        view=memoryview(data)
        while view:view=view[os.write(fd,view):]
        os.fsync(fd);final=_nine(os.fstat(fd))
        if (final[0],final[1],final[5],final[6],final[7],final[8])!=identity or final[2]!=len(data):raise ValueError('Original created observation FD changed')
        if _nine(os.lstat(path))!=final:raise ValueError('Original observation output replaced')
        current=os.lstat(parent)
        if (current.st_dev,current.st_ino,current.st_mode,current.st_uid,current.st_gid)!=parent5:raise ValueError('Original output parent changed')
    finally:os.close(fd)
    frame=_capture([path]);row=frame['files'][0]
    if row['signature']!=list(final) or row['sha256']!=hashlib.sha256(data).hexdigest():raise ValueError('Original output bytes changed')
    frame['nodes']=original_parents
    frame['namespaces']=[dict(path=str(parent),names=sorted(names+[path.name]))]
    _close(frame)
    for raw,expected in original_parents:
        info=os.lstat(raw)
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=tuple(expected):raise ValueError('Original output ancestor changed')
    info=os.lstat(path)
    if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=final:raise ValueError('Original output leaf changed')
    return frame


def _merge(left,right):
    files={};nodes={};claims={}
    for frame in (left,right):
        for row in frame['files']:
            if row['path'] in files and files[row['path']]!=row:raise ValueError('Conflicting retained observation file')
            files[row['path']]=row
        for path,vector in frame['nodes']:
            if path in nodes and nodes[path]!=vector:raise ValueError('Conflicting retained observation node')
            nodes[path]=vector
        for path,value in frame['claims']:
            if path in claims and claims[path]!=value:raise ValueError('Conflicting native claim')
            claims[path]=value
    return dict(files=list(files.values()),nodes=list(map(list,nodes.items())),claims=list(map(list,claims.items())),absent=list(dict.fromkeys(left['absent']+right['absent'])),namespaces=left['namespaces']+right['namespaces'])


def request_or_consume(maintenance,request,frame,source,target,match):
    if not ENABLED or frame is None:return None,None
    from publication_guard import current,evidence
    authority=current(maintenance.worker)
    binding=evidence.canonical_digest({key:value for key,value in request.items() if key!='nonce'})
    live=_LIVE.pop((id(maintenance),binding),None)  # refusal spends the actual return too
    if (type(maintenance) is not _OWNING_MAINTENANCE or getattr(maintenance.mylar,'__func__',None) is not _ORIGINAL_MYlar
            or getattr(maintenance.mylar_observation,'__func__',None) is not _ORIGINAL_RETURN):raise ValueError('Original owning transport methods required')
    if live is not None:
        if (live['maintenance'] is not maintenance or live['pid']!=os.getpid() or live['thread']!=threading.get_ident() or time.monotonic()>live['deadline']
                or live['request']!={**request,'nonce':live['request']['nonce']}):raise ValueError('Original live transport witness unavailable')
        envelope=current_json(live['reply_bytes'])
        if type(envelope) is not dict or set(envelope)!={'success','data'} or envelope['success'] is not True:raise ValueError('Exact original API envelope required')
        reply=envelope['data'];request=current_json(live['request_bytes'])
        exact={'version','kind','nonce','request_sha256','token','owner','native_destination','native_data_root','original_attempt_sha256','original_ack_sha256','current_target','native_sources','evidence','rights'}
        if (type(reply) is not dict or set(reply)!=exact or type(reply['version']) is not int or reply['version']!=1
                or reply['kind']!='ordinary-import-current-observation' or reply['nonce']!=request['nonce']
                or reply['request_sha256']!=evidence.canonical_digest(request) or reply['token']!=request['token']
                or reply['owner']!=request['owner'] or reply['native_destination']!=request['destination']
                or reply['original_attempt_sha256']!=request['attempt_sha256'] or reply['original_ack_sha256']!=request['ack_sha256']
                or reply['current_target']!=dict(request['target'],payload=request['payload'])
                or reply['rights']!=dict(mutation=False,replay=False,cleanup=False,index_acceptance=False)):
            raise ValueError('Exact live native response required')
        # Foreign ancestor identities remain in the native owning namespace.
        # Every mutable native leaf is independently compared through existing
        # configured mounts, preserving full9 and never relabelling devices.
        retained=_merge(live['frame'],frame)
        source_names={'ordinary_import_continuity.py','ordinary_import_history.py','publication_rename.py','publication_transaction.py',
            'publication_guard.py','publication_native.py','native_writers.py','media_writer.py','ordinary_import_observation.py','api.py'}
        if (type(reply['native_sources']) is not list or len(reply['native_sources'])!=len(source_names)
                or {Path(row['path']).name for row in reply['native_sources']}!=source_names):raise ValueError('Exact installed native source roles required')
        native_frame=reply['evidence']
        if type(native_frame) is not dict or set(native_frame)!={'files','nodes','claims','absent','namespaces'}:raise ValueError('Exact original native evidence required')
        if not isinstance(native_frame['files'],list) or not 1<=len(native_frame['files'])<=8192:raise ValueError('Original native evidence exceeds bound')
        data=Path(reply['native_data_root'])
        if not data.is_absolute() or data==Path('/') or '..' in data.parts:raise ValueError('Original producer data root required')
        def mapped_native(raw):
            path=Path(raw)
            if not path.is_absolute() or '..' in path.parts:raise ValueError('Exact original native path required')
            if path.is_relative_to(data/'media-writer'):return authority.writer.root/path.relative_to(data/'media-writer')
            if path.is_relative_to(data):return authority.config/path.relative_to(data)
            return authority.mapped(str(path))
        # First copy ALL producer originals. No receiver hash or capture may
        # turn a later pathname fact into the producer's original evidence.
        native_originals={}
        for row in native_frame['files']:
            if (type(row) is not dict or set(row)!={'path','signature','sha256'} or type(row['path']) is not str
                    or type(row['signature']) is not list or len(row['signature'])!=9
                    or any(type(value) is not int for value in row['signature']) or not re.fullmatch('[0-9a-f]{64}',row['sha256'])):
                raise ValueError('Exact native leaf evidence required')
            copied=dict(path=row['path'],signature=list(row['signature']),sha256=row['sha256'])
            if row['path'] in native_originals and native_originals[row['path']]!=copied:raise ValueError('Conflicting native original leaf')
            native_originals[row['path']]=copied
        if any(native_originals.get(row['path'])!=row for row in reply['native_sources']):raise ValueError('Original source references missing from native closure')
        mapped_originals={}
        for row in native_originals.values():
            try:mapped=str(mapped_native(row['path']))
            except Exception:
                if row in reply['native_sources']:continue  # exact native sources stay authenticated producer-owned
                raise
            copied=dict(path=mapped,signature=list(row['signature']),sha256=row['sha256'])
            if mapped in mapped_originals and mapped_originals[mapped]!=copied:raise ValueError('Conflicting mapped native original leaf')
            mapped_originals[mapped]=copied
        retained=_merge(retained,dict(files=list(mapped_originals.values()),nodes=[],claims=[],absent=[],namespaces=[]))
        for row in mapped_originals.values():
            fact=evidence.file_hash(Path(row['path']))
            if fact!=(row['signature'],row['sha256']):raise ValueError('Original native bind leaf differs in worker')
            # Receiver parents may be compared, but the original file vector
            # above must conflict-refuse any post-hash pathname replacement.
            retained=_merge(retained,_capture([Path(row['path'])]))
        if (type(native_frame['absent']) is not list or len(native_frame['absent'])>8192 or
                type(native_frame['namespaces']) is not list or len(native_frame['namespaces'])>512):raise ValueError('Original native namespace exceeds bound')
        mapped_absent=[mapped_native(raw) for raw in native_frame['absent']]
        mapped_names=[]
        for row in native_frame['namespaces']:
            if (type(row) is not dict or set(row)!={'path','names'} or type(row['names']) is not list or len(row['names'])>4096
                    or any(type(name) is not str or '/' in name or name in ('','.','..') for name in row['names'])
                    or row['names']!=sorted(set(row['names']))):raise ValueError('Exact original native namespace required')
            mapped_names.append(dict(path=str(mapped_native(row['path'])),names=row['names']))
        if (type(native_frame['claims']) is not list or len(native_frame['claims'])>8192 or
                type(native_frame['nodes']) is not list or len(native_frame['nodes'])>8192):raise ValueError('Original native claims exceed bound')
        bound_roots=[data,*[Path(row['native']) for row in maintenance.worker.config.get('publication_roots',[])]]
        foreign_ancestors=[Path(row['path']) for row in reply['native_sources']]+bound_roots
        def foreign_directory(raw):
            path=Path(raw)
            return any(original==path or path in original.parents for original in foreign_ancestors)
        mapped_claims={};mapped_nodes={}
        for row in native_frame['claims']:
            if type(row) is not list or len(row)!=2 or type(row[0]) is not str:raise ValueError('Exact native claim row required')
            raw,value=row
            if value is not None:
                if (type(value) is not list or len(value)!=6 or any(type(v) is not int for v in value[:5])
                        or value[2]&0o170000 not in (0o100000,0o040000)
                        or (value[5] is not None if value[2]&0o170000==0o040000 else type(value[5]) is not int or value[5]!=1)):
                    raise ValueError('Exact native physical claim required')
            try:mapped=str(mapped_native(raw))
            except Exception:
                if value is not None and value[2]&0o170000==0o040000 and foreign_directory(raw):continue
                raise ValueError('Unmapped mutable native claim') from None
            if mapped in mapped_claims and mapped_claims[mapped]!=value:raise ValueError('Conflicting mapped native claim')
            mapped_claims[mapped]=value
        for row in native_frame['nodes']:
            if (type(row) is not list or len(row)!=2 or type(row[0]) is not str or type(row[1]) is not list
                    or len(row[1])!=5 or any(type(v) is not int for v in row[1]) or row[1][2]&0o170000!=0o040000):
                raise ValueError('Exact native original node required')
            raw,value=row
            try:mapped=str(mapped_native(raw))
            except Exception:
                if foreign_directory(raw):continue
                raise ValueError('Unmapped mutable native node') from None
            if mapped in mapped_nodes and mapped_nodes[mapped]!=value:raise ValueError('Conflicting mapped native node')
            info=os.lstat(mapped)
            if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=tuple(value):raise ValueError('Original native mapped node changed')
            mapped_nodes[mapped]=value
        native_current=dict(files=[],nodes=list(map(list,mapped_nodes.items())),claims=list(map(list,mapped_claims.items())),absent=[],namespaces=[])
        _claims_close(native_current['claims'])
        retained=_merge(retained,native_current)
        # Namespace/absence facts retain the exact producer originals, then
        # independently compare through already admitted mounts. Receiver node5
        # is current CAS, never a substitute for foreign original ancestors.
        retained=_merge(retained,_capture([],absent=mapped_absent,namespaces=mapped_names))
        _close(retained)
        for row in retained['namespaces']:
            if sorted(os.listdir(row['path']))!=row['names']:raise ValueError('Final observation namespace changed')
        for path,expected in retained['nodes']:
            info=os.lstat(path)
            if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=tuple(expected):raise ValueError('Final observation node changed')
        for row in retained['files']:
            info=os.lstat(row['path'])
            if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=tuple(row['signature']):raise ValueError('Final observation file changed')
        for path,expected in retained['claims']:
            try:info=os.lstat(path)
            except FileNotFoundError:
                if expected is not None:raise ValueError('Final native claim disappeared')
                continue
            actual=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode&0o170000==0o040000 else info.st_nlink)
            if expected is None or actual!=tuple(expected):raise ValueError('Final native claim changed')
        for path in retained['absent']:
            try:os.lstat(path)
            except FileNotFoundError:continue
            raise ValueError('Final observation absence changed')
        return request['token'],retained
    pending=_PENDING.get((id(maintenance),binding))
    if pending is not None:return None,None
    if len(_PENDING)+len(_LIVE)>=4096:raise ValueError('Observation retention exceeds bound')
    request=dict(request,nonce=secrets.token_hex(32))
    directory=maintenance.state/'ordinary-import-observations'
    if not directory.exists():directory.mkdir(mode=0o700)
    path=directory/(request['nonce']+'.request.json')
    entry=dict(request_bytes=_bytes(request),maintenance=maintenance,pid=os.getpid(),thread=threading.get_ident(),request=request,frame=None,
        source=str(source),target=str(target),match=match,binding=binding,path=path,phase='prepared',deadline=time.monotonic()+120,
        transport=dict(maintenance.worker.config['mylar']))
    prepared=_write(path,request);retained=_merge(frame,prepared)
    _close(retained)
    retained['namespaces']=[row for row in retained['namespaces'] if row['path']!=str(directory)]
    entry['frame']=retained
    for row in retained['namespaces']:
        if sorted(os.listdir(row['path']))!=row['names']:raise ValueError('Final observation namespace changed')
    for path,expected in retained['nodes']:
        info=os.lstat(path)
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=tuple(expected):raise ValueError('Final observation node changed')
    for row in retained['files']:
        info=os.lstat(row['path'])
        if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=tuple(row['signature']):raise ValueError('Final observation file changed')
    for path,expected in retained['claims']:
        try:info=os.lstat(path)
        except FileNotFoundError:
            if expected is not None:raise ValueError('Final native claim disappeared')
            continue
        actual=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode&0o170000==0o040000 else info.st_nlink)
        if expected is None or actual!=tuple(expected):raise ValueError('Final native claim changed')
    for path in retained['absent']:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise ValueError('Final observation absence changed')
    _PENDING[(id(maintenance),binding)]=entry
    return None,None


def dispatch(maintenance):
    if not ENABLED:return 0
    from publication_guard import remote_unlocked,scope,current
    from media_writer import Writer
    if type(maintenance) is not _OWNING_MAINTENANCE or getattr(maintenance.mylar,'__func__',None) is not _ORIGINAL_MYlar or getattr(maintenance.mylar_observation,'__func__',None) is not _ORIGINAL_RETURN:return 0
    remote_unlocked(maintenance.worker)
    candidates=[entry for entry in _PENDING.values() if entry['maintenance'] is maintenance and entry['phase']=='prepared']
    if not candidates:return 0
    entry=candidates[0];key=(id(maintenance),entry['binding'])
    # Spend this in-memory observation before any transport callback. Disk can
    # never reconstruct an attempt or a live authenticated-return witness.
    try:
        if entry['pid']!=os.getpid() or time.monotonic()>entry['deadline']:raise ValueError('Original observation expired')
        health=maintenance.mylar('getHealth').get('workflow',{})
        if type(health.get('ordinary_import_observation')) is not int or health['ordinary_import_observation']!=1:return 0
        writer=Writer(maintenance.worker.config['writer_state'],create=False)
        with writer.hold(timeout=0),scope(maintenance.worker,writer):
            authority=current(maintenance.worker)
            checked=authority.confirmation_check(Path(entry['source']) if Path(entry['source']).exists() else Path(entry['target']),Path(entry['target']),entry['match'])
            if checked['target']['authority']['owner']!=entry['request']['owner']:raise ValueError('Original owner changed before transport')
            _close(entry['frame'])
        remote_unlocked(maintenance.worker)
        _close(entry['frame'])
        if entry['transport']!=maintenance.worker.config['mylar']:raise ValueError('Original configured transport changed')
        entry['phase']='uncertain'
        encoded=maintenance.mylar_observation(entry['request_bytes'])
        if entry['transport']!=maintenance.worker.config['mylar']:raise ValueError('Original configured transport changed')
        if type(encoded) is not bytes or len(encoded)>_LIMIT:raise ValueError('Original native observation bytes required')
        envelope=current_json(encoded)
        if type(envelope) is not dict or set(envelope)!={'success','data'} or envelope['success'] is not True:raise ValueError('Exact original API success envelope required')
        with writer.hold(timeout=0),scope(maintenance.worker,writer):
            current(maintenance.worker).confirmation_check(Path(entry['source']) if Path(entry['source']).exists() else Path(entry['target']),Path(entry['target']),entry['match'])
            _close(entry['frame'])
            output=entry['path'].with_name(entry['path'].name.replace('.request.json','.response.json'))
            frame=_merge(entry['frame'],_write(output,dict(version=2,encoded_utf8=encoded.decode('utf-8'))))
            witness=dict(entry,frame=frame,reply_bytes=encoded)
        if time.monotonic()>entry['deadline']:raise ValueError('Original observation expired')
        _close(frame)
        for row in frame['namespaces']:
            if sorted(os.listdir(row['path']))!=row['names']:raise ValueError('Final observation namespace changed')
        for path,expected in frame['nodes']:
            info=os.lstat(path)
            if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=tuple(expected):raise ValueError('Final observation node changed')
        for row in frame['files']:
            info=os.lstat(row['path'])
            if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=tuple(row['signature']):raise ValueError('Final observation file changed')
        for path,expected in frame['claims']:
            try:info=os.lstat(path)
            except FileNotFoundError:
                if expected is not None:raise ValueError('Final native claim disappeared')
                continue
            actual=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode&0o170000==0o040000 else info.st_nlink)
            if expected is None or actual!=tuple(expected):raise ValueError('Final native claim changed')
        for path in frame['absent']:
            try:os.lstat(path)
            except FileNotFoundError:continue
            raise ValueError('Final observation absence changed')
        _LIVE[key]=witness;del _PENDING[key]
        return 1
    except Exception:
        entry['phase']='uncertain'
        return 0


def post_cycle(maintenance):
    """NEW originals after all ordinary cycle effects; no marker continuation.

    Results are process-local observations only. Durable pack receipt/report
    remains held until a separate exact owning generation/member CAS exists.
    """
    if not ENABLED:return 0
    from publication_guard import remote_unlocked,scope
    from media_writer import Writer
    import ordinary_import_ack
    if type(maintenance) is not _OWNING_MAINTENANCE:return 0
    remote_unlocked(maintenance.worker)
    selected=[(key,row) for key,row in _SELECTORS.items() if row[0] is maintenance][:32]
    accepted=0
    for key,row in selected:
        del _SELECTORS[key]  # selector is spent; never an evidence baseline
        if row[4:]!=(os.getpid(),threading.get_ident()):continue
        _,source,match,target,_,_=row
        try:
            writer=Writer(maintenance.worker.config['writer_state'],create=False)
            with writer.hold(timeout=0),scope(maintenance.worker,writer):
                before=ordinary_import_ack.confirmed(maintenance,Path(source),match,Path(target))
            if before is not None:continue  # unchanged ACK has its existing path
            if dispatch(maintenance)!=1:continue
            with writer.hold(timeout=0),scope(maintenance.worker,writer):
                copied=ordinary_import_ack.confirmed(maintenance,Path(source),match,Path(target),_copied=True)
            if copied is None:continue
            token,frame=copied
            result=(maintenance,os.getpid(),threading.get_ident(),token,time.monotonic(),False)
            _close(frame)
            for row in frame['namespaces']:
                if sorted(os.listdir(row['path']))!=row['names']:raise ValueError('Final post-cycle namespace changed')
            for path,expected in frame['nodes']:
                info=os.lstat(path)
                if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=tuple(expected):raise ValueError('Final post-cycle node changed')
            for row in frame['files']:
                info=os.lstat(row['path'])
                if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=tuple(row['signature']):raise ValueError('Final post-cycle file changed')
            for path,expected in frame['claims']:
                try:info=os.lstat(path)
                except FileNotFoundError:
                    if expected is not None:raise ValueError('Final post-cycle claim disappeared')
                    continue
                actual=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode&0o170000==0o040000 else info.st_nlink)
                if expected is None or actual!=tuple(expected):raise ValueError('Final post-cycle claim changed')
            for path in frame['absent']:
                try:os.lstat(path)
                except FileNotFoundError:continue
                raise ValueError('Final post-cycle absence changed')
            _RESULTS[key]=result
            accepted+=1
        except Exception:continue
    return accepted
