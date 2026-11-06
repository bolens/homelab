"""Source-only neutral retained-operation backup; no receipt hydration or grants."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import threading
import tempfile
import time
import weakref

MAX_SCOPES=3
MAX_DATABASES=16
MAX_NODES=100000
MAX_BYTES=512*1024**3
BACKUP_SECONDS=1800
_ROLES=('native_config','worker_state','reader_config')
_OBS=weakref.WeakKeyDictionary()
_SEALS=weakref.WeakKeyDictionary()
_PRIMITIVES=weakref.WeakKeyDictionary()


def need(v,reason):
    if not v:raise ValueError(reason)


def nine(z):return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
def five(z):return (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def snapshot(roots, *, source_links=False, source_nodes=None, deadline=None):
    roots=tuple(roots)
    need(type(source_links) is bool,'backup-link-policy')
    limit=MAX_NODES
    if source_nodes is not None:
        need(type(source_nodes) is int and 0<source_nodes<=MAX_NODES
             and source_links is False and len(roots)==2,'backup-copy-source-count')
        limit=2*source_nodes+len(roots)
    files={};nodes={};spaces={};links={};total=0
    def walk(p):
        nonlocal total
        need(deadline is None or time.monotonic()<deadline,'backup-original-deadline')
        z=os.lstat(p);stamp=nine(z);kind=z.st_mode&0o170000
        need(kind in (0o040000,0o100000,0o120000),'backup-tree-type')
        first=str(p) not in files
        need(first or files[str(p)]==stamp,'backup-original-conflict');files[str(p)]=stamp
        if kind==0o100000:
            if source_links:
                key=(z.st_dev,z.st_ino)
                original,names=links.setdefault(key,(stamp,set()))
                need(stamp==original and z.st_nlink>=1,'backup-source-link-group')
                names.add(str(p))
            else:need(z.st_nlink==1,'backup-selected-alias')
            if first:total+=z.st_size
            need(total<=MAX_BYTES,'backup-byte-bound')
        elif kind==0o040000:
            nodes[str(p)]=five(z);names=tuple(sorted(os.listdir(p)));spaces[str(p)]=names
            for name in names:walk(p/name)
        else:need(z.st_nlink==1,'backup-selected-symlink-alias')
        need(len(files)<=limit,'backup-node-bound')
    # Known roots and ancestors precede first enumeration.
    for root in roots:
        for p in (root,*root.parents):
            z=os.lstat(p);value=five(z);need(z.st_mode&0o170000==0o040000,'backup-directory')
            need(str(p) not in nodes or nodes[str(p)]==value,'backup-ancestor-conflict');nodes[str(p)]=value
        files[str(root)]=nine(os.lstat(root))
    for root in roots:walk(root)
    for stamp,names in links.values():need(len(names)==stamp[8],'backup-source-link-group')
    if source_nodes is not None:need(len(files)==limit,'backup-copy-node-count')
    frame=(tuple(sorted(files.items())),tuple(sorted(nodes.items())),tuple(sorted(spaces.items())))
    raw(frame);return frame,total


def scratch_space(frame):
    largest=max((stamp[2] for _,stamp in frame[0] if stamp[5]&0o170000==0o100000),default=0)
    return 4*largest+1024**2


def required_space(total, frame, *, reflink_restore=False):
    """One materialized copy only for an independently qualified restore clone.

    A SQLite scratch group contains at most a main file, WAL and SHM. Reserve
    four times the largest scoped file plus an index allowance, conservatively
    covering all three inputs and a rebuilt WAL index without guessing DB names.
    """
    need(type(total) is int and total>=0 and type(reflink_restore) is bool,'backup-space-input')
    return (total if reflink_restore else 2*total)+(total+19)//20+1024**2+scratch_space(frame)


def raw(frame):
    files,nodes,spaces=frame
    for p,names in spaces:need(tuple(sorted(os.listdir(p)))==names,'backup-namespace')
    for p,s in nodes:
        z=os.lstat(p);need((z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)==s,'backup-original-node')
    for p,s in files:
        z=os.lstat(p);need((z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)==s,'backup-original-file')


def source_module(path,expected,original_frame=None):
    path=Path(path)
    if original_frame is None:
        original=nine(os.lstat(path));parents=tuple((str(p),five(os.lstat(p))) for p in path.parents)
    else:
        raw(original_frame);original=dict(original_frame[0])[str(path)];parents=original_frame[1]
    need(original[5]&0o170000==0o100000 and original[8]==1,'backup-source-type')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        need(nine(os.fstat(fd))==original,'backup-source-FD');parts=[]
        while chunk:=os.read(fd,1048576):parts.append(chunk)
        data=b''.join(parts);need(len(data)<=1024**2 and hashlib.sha256(data).hexdigest()==expected,'backup-source-pin')
        need(nine(os.fstat(fd))==original,'backup-source-read-drift')
    finally:os.close(fd)
    module=importlib.util.module_from_spec(importlib.util.spec_from_loader('retained_backup_primitives',loader=None));module.__file__=str(path)
    exec(compile(data,str(path),'exec'),module.__dict__)
    methods=tuple((name,function,function.__code__,function.__defaults__,function.__kwdefaults__,
                   None if function.__kwdefaults__ is None else tuple((key,type(value),value) for key,value in sorted(function.__kwdefaults__.items())))
                  for name,function in vars(module).items()
                  if type(function).__name__=='function' and function.__globals__ is vars(module))
    constants=tuple((name,vars(module)[name]) for name in ('MAX_FILES','MAX_MANIFEST','MAX_BYTES','DEADLINE','Held'))
    _PRIMITIVES[module]=(_PRIMITIVES,methods,constants)
    raw((((str(path),original),),parents,()))
    _primitive_original(module)
    return module,(((str(path),original),),parents,())


def _primitive_original(module,expected=None):
    original=_PRIMITIVES.get(module)
    if original is None or original[0] is not _PRIMITIVES or (expected is not None and original is not expected):
        raise ValueError('backup-original-primitive-registry')
    for name,function,code,defaults,kwdict,kwdefaults in original[1]:
        current=vars(module).get(name)
        if (current is not function or current.__code__ is not code or current.__defaults__ is not defaults
                or current.__kwdefaults__ is not kwdict
                or (kwdict is not None and (len(kwdict)!=len(kwdefaults) or any(type(key) is not str for key in kwdict)
                    or any(key not in kwdict or type(kwdict[key]) is not kind or kwdict[key]!=value for key,kind,value in kwdefaults)))):
            raise ValueError('backup-original-primitive-callable')
    for name,wanted in original[2]:
        current=vars(module).get(name)
        if type(current) is not type(wanted) or current!=wanted:raise ValueError('backup-original-primitive-constant')
    return original


def _primitive_call(module,original,name,*args,**kwargs):
    _primitive_original(module,original)
    function=next(function for key,function,*_ in original[1] if key==name)
    result=function(*args,**kwargs)
    _primitive_original(module,original)
    return result


def _json_value(value):
    kind=type(value)
    if kind is dict:
        if any(type(key) is not str for key in value):raise ValueError('backup-original-JSON-key')
        return {key:_json_value(item) for key,item in value.items()}
    if kind in (tuple,list):return [_json_value(item) for item in value]
    if kind in (str,int,float,bool,type(None)):return value
    raise ValueError('backup-original-JSON-type')


def _projection(value):
    pending=[value];result=[]
    while pending:
        item=pending.pop();kind=type(item)
        if kind is dict:
            keys=tuple(sorted(item));result.append(('dict',keys));pending.extend(item[k] for k in reversed(keys))
        elif kind in (list,tuple):
            result.append((kind.__name__,len(item)));pending.extend(reversed(item))
        elif kind in (str,int,float,bool,bytes,type(None)):
            result.append((kind.__name__,item))
        else:result.append(('identity',id(kind),id(item)))
    return tuple(result)


def _original(value,expected=None):
    seal=_SEALS.get(value)
    need(type(value) is BackupObservation and type(seal) is tuple and len(seal)==9,
         'backup-original-seal')
    c,table,seals,logical,owner,deadline,_,_,_=seal
    need((expected is None or seal is expected) and _OBS is table and _SEALS is seals
         and table.get(value) is c and _projection(c)==logical
         and (os.getpid(),threading.get_ident())==owner and time.monotonic()<deadline,
         'backup-original-custody')
    _primitive_original(c['module'],seal[8])
    return c,seal


def _finish(value,c,seal,frames):
    # Every semantic/helper callback precedes the final direct physical and
    # logical closure. Expected frames belong to the original immutable seal.
    _original(value,seal)
    for frame in frames:raw(frame)
    for files,nodes,spaces in frames:
        for path,names in spaces:
            if tuple(sorted(os.listdir(path)))!=tuple(names):raise ValueError('backup-final-namespace')
        for path,stamp in nodes:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(stamp):raise ValueError('backup-final-node')
        for path,stamp in files:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(stamp):raise ValueError('backup-final-file')
    # Inline primitive projection: no replaceable checker/serializer runs after
    # the physical tail and before original-table/entry comparison.
    pending=[c];result=[]
    while pending:
        item=pending.pop();kind=type(item)
        if kind is dict:
            keys=tuple(sorted(item));result.append(('dict',keys));pending.extend(item[k] for k in reversed(keys))
        elif kind in (list,tuple):
            result.append((kind.__name__,len(item)));pending.extend(reversed(item))
        elif kind in (str,int,float,bool,bytes,type(None)):
            result.append((kind.__name__,item))
        else:result.append(('identity',id(kind),id(item)))
    primitive=seal[8]
    if _PRIMITIVES is not primitive[0] or _PRIMITIVES.get(c['module']) is not primitive:
        raise ValueError('backup-original-final-primitive-registry')
    for name,function,code,defaults,kwdict,kwdefaults in primitive[1]:
        current=vars(c['module']).get(name)
        if (current is not function or current.__code__ is not code or current.__defaults__ is not defaults
                or current.__kwdefaults__ is not kwdict
                or (kwdict is not None and (len(kwdict)!=len(kwdefaults) or any(type(key) is not str for key in kwdict)
                    or any(key not in kwdict or type(kwdict[key]) is not kind or kwdict[key]!=value for key,kind,value in kwdefaults)))):
            raise ValueError('backup-original-final-primitive-callable')
    for name,wanted in primitive[2]:
        current=vars(c['module']).get(name)
        if type(current) is not type(wanted) or current!=wanted:raise ValueError('backup-original-final-primitive-constant')
    if (tuple(result)!=seal[3] or _OBS is not seal[1] or _SEALS is not seal[2]
            or _OBS.get(value) is not c or _SEALS.get(value) is not seal
            or (os.getpid(),threading.get_ident())!=seal[4] or time.monotonic()>=seal[5]):
        raise ValueError('backup-original-final-custody')


class BackupObservation:
    __slots__=('__weakref__',)
    def __init__(self,*a,**k):raise ValueError('Original backup observation required')
    def close_copies(self):
        c,seal=_original(self);frames=(seal[7][1],seal[7][2])
        # The factory verifies bytes and SQL before publishing this object.
        # Reuse only that exact proof, while every original copy incarnation,
        # namespace, companion and code witness remains unchanged. Disk JSON
        # cannot construct an observation or refresh any witness.
        result=dict(kind='retained-neutral-backup-observation-v1',scopes=len(c['scopes']),
            files=len(c['source'][0]),bytes=c['bytes'],digest=c['digest'],mutation_authority=False)
        need(_primitive_call(c['module'],seal[8],'attributes_many',tuple(path for path,_ in c['copy_attributes']),deadline=c['deadline'])==c['copy_attributes'],'backup-copy-attributes')
        _finish(self,c,seal,frames)
        return result
    def current_scopes(self, *, deadline=None):
        """Fresh current census; unchanged bytes reuse only this factory's proof.

        There is no baseline/cache argument and no receipt hydration. A cached
        hash belongs to the same sealed observation, and survives only exact
        original full9 and attribute equality. Changed/new files are read anew.
        """
        c,seal=_original(self)
        if deadline is not None:
            need(type(deadline) in (int,float) and math.isfinite(deadline),'backup-current-deadline-type')
        deadline=c['deadline'] if deadline is None else min(c['deadline'],deadline)
        need(time.monotonic()<deadline,'backup-current-original-deadline')
        # Retain detached expected values before the first filesystem/helper
        # callback; a transient rebase of the mutable registry cannot seed reuse.
        projection=_projection;code=projection.__code__
        original={key:_json_value(c[key]) for key in ('source_scopes','databases','required')};original['out']=str(c['out'])
        original_expected=projection(original)
        scopes=original['source_scopes'];roots=[Path(scope['path']) for scope in scopes]
        current,_=snapshot(roots,source_links=True,deadline=deadline)
        measured={}
        attributes=dict(_primitive_call(c['module'],seal[8],'attributes_many',tuple(path for path,_ in current[0]),deadline=deadline))
        for scope,root in zip(scopes,roots):
            baseline={row['path']:row for row in scope['records']};rows=[]
            for text,signature in current[0]:
                path=Path(text)
                if not path.is_relative_to(root):continue
                need(time.monotonic()<deadline,'backup-current-original-deadline')
                relative='.' if path==root else str(path.relative_to(root));kind=signature[5]&0o170000
                attrs=attributes[text]
                old=baseline.get(relative);link=None;digest=None
                if kind==0o100000:
                    form='file'
                    if (old is not None and old['kind']=='file' and tuple(old['stamp'])==signature
                            and old['attributes']==attrs):digest=old['sha256']
                    else:digest=_primitive_call(c['module'],seal[8],'hash_file',path,deadline=deadline)
                elif kind==0o040000:form='directory'
                else:form='symlink';link=os.readlink(path)
                rows.append(dict(path=relative,kind=form,sha256=digest,link=link,attributes=attrs,stamp=list(signature)))
            measured[scope['name']]=rows
        need(projection is _projection and projection.__code__ is code
             and projection(original)==original_expected,'backup-current-baseline-custody')
        expected=projection((original,measured))
        # Close the copy attributes and all original copy/code frames in the
        # same final tail as the fresh census. A nested close_copies() would
        # repeat that complete closure before this identical final check.
        need(_primitive_call(c['module'],seal[8],'attributes_many',tuple(path for path,_ in c['copy_attributes']),deadline=c['deadline'])==c['copy_attributes'],'backup-copy-attributes')
        _finish(self,c,seal,(current,*seal[7][1:]))
        need(projection is _projection and projection.__code__ is code
             and projection((original,measured))==expected,'backup-current-result-custody')
        need(time.monotonic()<deadline,'backup-current-original-deadline')
        return original,measured

    def close(self):
        c,seal=_original(self)
        result=dict(kind='retained-neutral-backup-observation-v1',scopes=len(c['scopes']),
            files=len(c['source'][0]),bytes=c['bytes'],digest=c['digest'],mutation_authority=False)
        need(_primitive_call(c['module'],seal[8],'attributes_many',tuple(path for path,_ in c['copy_attributes']),deadline=c['deadline'])==c['copy_attributes'],'backup-copy-attributes')
        need(_primitive_call(c['module'],seal[8],'attributes_many',tuple(path for path,_ in c['source_attributes']),deadline=c['deadline'])==c['source_attributes'],'backup-source-attributes')
        _finish(self,c,seal,seal[7])
        return result


def copy_and_verify(scopes,out,primitives_path,primitives_sha,*,deadline=None,reflink_restore=False):
    """Mechanism only. Parent continuously owns quiescence; this cannot mint BackupReady."""
    need(type(scopes) is list and len(scopes)==MAX_SCOPES and tuple(s['role'] for s in scopes)==_ROLES,'backup-exact-roles')
    scopes=[{'role':row['role'],'root':row['root'],'databases':list(tuple(row['databases']))} for row in scopes]
    roots=[];required=[];initial_scopes=[]
    for s in scopes:
        need(type(s) is dict and set(s)=={'role','root','databases'} and type(s['databases']) is list,'backup-scope-schema')
        p=Path(s['root']);need(p.is_absolute() and str(p)==s['root'] and not p.is_symlink(),'backup-root')
        roots.append(p)
        for relative in s['databases']:
            q=Path(relative);need(type(relative) is str and not q.is_absolute() and '..' not in q.parts and str(q)==relative,'backup-database-relative')
            required.append(s['role']+':'+relative)
    need(1<=len(required)<=MAX_DATABASES and len(set(required))==len(required),'backup-database-bound')
    need(len(set(roots))==len(roots) and all(not a.is_relative_to(b) for a in roots for b in roots if a!=b),'backup-scope-overlap')
    out=Path(out);need(out.is_absolute() and not os.path.lexists(out),'backup-exclusive-output')
    need(all(not out.is_relative_to(r) and not r.is_relative_to(out) for r in roots),'backup-output-overlap')
    out_parent=five(os.lstat(out.parent));need(out_parent[2]&0o7777==0o700 and out_parent[3]==os.geteuid(),'backup-private-parent')
    need(type(reflink_restore) is bool,'backup-copy-mode')
    local_deadline=time.monotonic()+BACKUP_SECONDS
    if deadline is not None:
        need(type(deadline) in (int,float) and math.isfinite(deadline),'backup-deadline-type')
    deadline=local_deadline if deadline is None else min(deadline,local_deadline)
    need(time.monotonic()<deadline,'backup-original-deadline')
    primitive=Path(primitives_path);primitive_frame=(((str(primitive),nine(os.lstat(primitive))),),tuple((str(q),five(os.lstat(q))) for q in primitive.parents),())
    original,total=snapshot(roots,source_links=True,deadline=deadline)  # Before module/hash/database callbacks.
    need(2*total<=MAX_BYTES,'backup-two-copy-byte-bound')
    space=os.statvfs(out.parent)
    need(space.f_bavail*space.f_frsize>=required_space(total,original,reflink_restore=reflink_restore),
         'backup-data-and-scratch-capacity')
    scratch=os.statvfs(tempfile.gettempdir())
    need(scratch.f_bavail*scratch.f_frsize>=scratch_space(original),'backup-SQL-scratch-capacity')
    raw(primitive_frame)
    m,code=source_module(primitives_path,primitives_sha,primitive_frame);primitive_original=_primitive_original(m);logical={}
    original_files=dict(original[0])
    for s,p in zip(scopes,roots):
        rows,_=_primitive_call(m,primitive_original,'inventory',p,'tree',deadline=deadline);logical[s['role']]=_primitive_call(m,primitive_original,'logical',rows)
        for row in rows:need(tuple(row['stamp'])==original_files[str(p if row['path']=='.' else p/row['path'])],'backup-inventory-original')
        initial_scopes.append(dict(name=s['role'],path=str(p),kind='tree',records=rows))
    database_files={scope['name']+':'+row['path'] for scope in initial_scopes for row in scope['records'] if row['kind']=='file'}
    databases=_primitive_call(m,primitive_original,'database_rows',initial_scopes,required,deadline=deadline)
    need(type(databases) is dict and set(required)<=set(databases)<=database_files,'backup-discovered-database-census')
    raw(original);raw(code)
    need(five(os.lstat(out.parent))==out_parent and not os.path.lexists(out),'backup-output-parent-original')
    out.mkdir(mode=0o700);out_node=five(os.lstat(out));(out/'backup').mkdir(mode=0o700);backup_node=five(os.lstat(out/'backup'));(out/'restore').mkdir(mode=0o700);restore_node=five(os.lstat(out/'restore'))
    anchors=(((str(out/'backup'),backup_node),(str(out/'restore'),restore_node),(str(out),out_node)))
    for s in initial_scopes:
        for path,stamp in anchors:need(five(os.lstat(path))==stamp,'backup-created-anchor')
        need(tuple(sorted(os.listdir(out)))==('backup','restore'),'backup-output-namespace')
        need(time.monotonic()<deadline,'backup-deadline');raw(original);raw(code)
        for path,stamp in anchors:
            if five(os.lstat(path))!=stamp:raise ValueError('backup-created-anchor')
        _primitive_call(m,primitive_original,'copy_scope',Path(s['path']),out/'backup'/s['name'],s['records'],deadline=deadline);raw(original)
        for path,stamp in anchors:
            if five(os.lstat(path))!=stamp:raise ValueError('backup-created-anchor')
        _primitive_call(m,primitive_original,'copy_scope',out/'backup'/s['name'],out/'restore'/s['name'],s['records'],deadline=deadline,reflink=reflink_restore);raw(original)
    for path,stamp in anchors:need(five(os.lstat(path))==stamp,'backup-created-anchor')
    need(tuple(sorted(os.listdir(out)))==('backup','restore'),'backup-output-namespace')
    need(five(os.lstat(out))==out_node,'backup-created-output-identity')
    copied,_=snapshot([out/'backup',out/'restore'],source_nodes=len(original[0]),deadline=deadline)
    copied=(copied[0],copied[1],copied[2]+((str(out),('backup','restore')),))
    # Verify each detached copy and its independent SQLite restoration exactly
    # once. No observation exists until all callbacks close against these same
    # original physical frames, so a caller cannot pre-seed a verified flag.
    copy_attributes=[]
    for key in ('backup','restore'):
        measured=[]
        for scope in scopes:
            root=out/key/scope['role']
            rows,_=_primitive_call(m,primitive_original,'inventory',root,'tree',detached=True,deadline=deadline)
            need(_primitive_call(m,primitive_original,'copied_records_match',rows,logical[scope['role']]),'backup-copy-content')
            measured.append(dict(name=scope['role'],path=str(root),kind='tree',records=rows))
            copy_attributes.extend((str(root if row['path']=='.' else root/row['path']),row['attributes']) for row in rows)
        need(_primitive_call(m,primitive_original,'database_rows',measured,required,deadline=deadline)==databases,'backup-detached-database')
        raw(original);raw(copied);raw(code);_primitive_original(m,primitive_original)
    digest=hashlib.sha256(encode(dict(scopes=scopes,logical=logical,databases=databases,source=original,copies=copied))).hexdigest()
    source_attributes=tuple((str(Path(scope['path']) if row['path']=='.' else Path(scope['path'])/row['path']),row['attributes']) for scope in initial_scopes for row in scope['records'])
    value=object.__new__(BackupObservation);_OBS[value]=dict(scopes=scopes,out=out,source=original,copies=copied,source_code=code,module=m,logical=logical,databases=databases,required=required,source_scopes=initial_scopes,source_attributes=source_attributes,copy_attributes=tuple(copy_attributes),pid=os.getpid(),thread=threading.get_ident(),deadline=deadline,bytes=total,digest=digest)
    c=_OBS[value];table=_OBS;seals=_SEALS;project=_projection;project_code=project.__code__;projection=project(c)
    original_frames=(c['source'],c['copies'],c['source_code']);owner=(c['pid'],c['thread']);original_deadline=c['deadline']
    dto=_json_value(dict({k:v for k,v in c.items() if k not in ('module','out')},out=str(c['out'])))
    dto_projection=project(dto);sealed=encode(dto);decoded=json.loads(sealed)
    if project.__code__ is not project_code:raise ValueError('backup-original-factory-projector')
    if project(decoded)!=dto_projection:raise ValueError('backup-original-factory-encoding')
    _primitive_original(m,primitive_original)
    if _OBS is not table or _SEALS is not seals or table.get(value) is not c or project(c)!=projection or project.__code__ is not project_code:
        raise ValueError('backup-original-factory-custody')
    _SEALS[value]=(c,table,seals,projection,owner,original_deadline,sealed,original_frames,primitive_original)
    value.close();return value
