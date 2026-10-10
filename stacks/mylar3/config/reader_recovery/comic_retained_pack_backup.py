"""Source-only neutral retained-operation backup; no receipt hydration or grants."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import threading
import time
import weakref

MAX_SCOPES=3
MAX_DATABASES=16
MAX_NODES=100000
MAX_BYTES=512*1024**3
BACKUP_SECONDS=1800
_ROLES=('native_config','worker_state','reader_config')
_OBS=weakref.WeakKeyDictionary()


def need(v,reason):
    if not v:raise ValueError(reason)


def nine(z):return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
def five(z):return (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def snapshot(roots):
    files={};nodes={};spaces={};total=0
    def walk(p):
        nonlocal total
        z=os.lstat(p);stamp=nine(z);kind=z.st_mode&0o170000
        need(kind in (0o040000,0o100000),'backup-tree-type')
        need(str(p) not in files or files[str(p)]==stamp,'backup-original-conflict');files[str(p)]=stamp
        if kind==0o100000:
            need(z.st_nlink==1,'backup-selected-alias');total+=z.st_size;need(total<=MAX_BYTES,'backup-byte-bound')
        else:
            nodes[str(p)]=five(z);names=tuple(sorted(os.listdir(p)));spaces[str(p)]=names
            for name in names:walk(p/name)
        need(len(files)<=MAX_NODES,'backup-node-bound')
    # Known roots and ancestors precede first enumeration.
    for root in roots:
        for p in (root,*root.parents):
            z=os.lstat(p);value=five(z);need(z.st_mode&0o170000==0o040000,'backup-directory')
            need(str(p) not in nodes or nodes[str(p)]==value,'backup-ancestor-conflict');nodes[str(p)]=value
        files[str(root)]=nine(os.lstat(root))
    for root in roots:walk(root)
    frame=(tuple(sorted(files.items())),tuple(sorted(nodes.items())),tuple(sorted(spaces.items())))
    raw(frame);return frame,total


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
    raw((((str(path),original),),parents,()))
    return module,(((str(path),original),),parents,())


class BackupObservation:
    __slots__=('__weakref__',)
    def __init__(self,*a,**k):raise ValueError('Original backup observation required')
    def close_copies(self):
        c=_OBS.get(self);need(c is not None and c['pid']==os.getpid() and c['thread']==threading.get_ident(),'original-backup-owner')
        need(time.monotonic()<c['deadline'],'backup-deadline');m=c['module']
        for key in ('backup','restore'):
            measured=[]
            for scope in c['scopes']:
                root=c['out']/key/scope['role'];rows,_=m.inventory(root,'tree',detached=True)
                need(m.logical(rows)==c['logical'][scope['role']],'backup-copy-content')
                measured.append(dict(name=scope['role'],path=str(root),kind='tree',records=rows))
            need(m.database_rows(measured,c['required'])==c['databases'],'backup-detached-database')
        result=dict(kind='retained-neutral-backup-observation-v1',scopes=len(c['scopes']),files=len(c['source'][0]),bytes=c['bytes'],digest=c['digest'],mutation_authority=False)
        final_frames=(c['copies'],c['source_code'])
        for frame in final_frames:raw(frame)
        for files,nodes,spaces in final_frames:
            for path,names in spaces:
                if tuple(sorted(os.listdir(path)))!=names:raise ValueError('backup-final-namespace')
            for path,stamp in nodes:
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise ValueError('backup-final-node')
            for path,stamp in files:
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise ValueError('backup-final-file')
        return result
    def close(self):
        c=_OBS.get(self);need(c is not None,'original-backup-observation')
        result=self.close_copies();m=c['module']
        need(m.database_rows(c['source_scopes'],c['required'])==c['databases'],'backup-source-database')
        frames=(c['source'],c['copies'],c['source_code'])
        for frame in frames:raw(frame)
        for files,nodes,spaces in frames:
            for path,names in spaces:
                if tuple(sorted(os.listdir(path)))!=names:raise ValueError('backup-final-namespace')
            for path,stamp in nodes:
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise ValueError('backup-final-node')
            for path,stamp in files:
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise ValueError('backup-final-file')
        return result


def copy_and_verify(scopes,out,primitives_path,primitives_sha):
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
    deadline=time.monotonic()+BACKUP_SECONDS
    primitive=Path(primitives_path);primitive_frame=(((str(primitive),nine(os.lstat(primitive))),),tuple((str(q),five(os.lstat(q))) for q in primitive.parents),())
    original,total=snapshot(roots)  # Complete source frame BEFORE module/hash/database callbacks.
    raw(primitive_frame)
    m,code=source_module(primitives_path,primitives_sha,primitive_frame);logical={}
    for s,p in zip(scopes,roots):
        rows,_=m.inventory(p,'tree');logical[s['role']]=m.logical(rows)
        for row in rows:need(tuple(row['stamp'])==dict(original[0])[str(p if row['path']=='.' else p/row['path'])],'backup-inventory-original')
        initial_scopes.append(dict(name=s['role'],path=str(p),kind='tree',records=rows))
    databases=m.database_rows(initial_scopes,required);need(len(databases)<=MAX_DATABASES,'backup-discovered-database-bound');raw(original);raw(code)
    need(five(os.lstat(out.parent))==out_parent and not os.path.lexists(out),'backup-output-parent-original')
    out.mkdir(mode=0o700);out_node=five(os.lstat(out));(out/'backup').mkdir(mode=0o700);backup_node=five(os.lstat(out/'backup'));(out/'restore').mkdir(mode=0o700);restore_node=five(os.lstat(out/'restore'))
    anchors=(((str(out/'backup'),backup_node),(str(out/'restore'),restore_node),(str(out),out_node)))
    for s in initial_scopes:
        for path,stamp in anchors:need(five(os.lstat(path))==stamp,'backup-created-anchor')
        need(tuple(sorted(os.listdir(out)))==('backup','restore'),'backup-output-namespace')
        need(time.monotonic()<deadline,'backup-deadline');raw(original);raw(code)
        m.copy_scope(Path(s['path']),out/'backup'/s['name'],s['records']);raw(original)
        m.copy_scope(out/'backup'/s['name'],out/'restore'/s['name'],s['records']);raw(original)
    for path,stamp in anchors:need(five(os.lstat(path))==stamp,'backup-created-anchor')
    need(tuple(sorted(os.listdir(out)))==('backup','restore'),'backup-output-namespace')
    need(five(os.lstat(out))==out_node,'backup-created-output-identity')
    copied,_=snapshot([out/'backup',out/'restore'])
    copied=(copied[0],copied[1],copied[2]+((str(out),('backup','restore')),))
    digest=hashlib.sha256(encode(dict(scopes=scopes,logical=logical,databases=databases,source=original,copies=copied))).hexdigest()
    value=object.__new__(BackupObservation);_OBS[value]=dict(scopes=scopes,out=out,source=original,copies=copied,source_code=code,module=m,logical=logical,databases=databases,required=required,source_scopes=initial_scopes,pid=os.getpid(),thread=threading.get_ident(),deadline=deadline,bytes=total,digest=digest)
    value.close();return value
