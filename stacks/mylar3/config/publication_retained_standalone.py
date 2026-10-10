"""Disabled standalone existing-target recovery, never a historical import ACK."""
from contextlib import closing
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import threading
import time
import weakref

if __package__:
    from . import publication_archive_owned as o, publication_retained_delivery as r
else:
    import publication_archive_owned as o
    import publication_retained_delivery as r

ENABLED=False
NAME='retained-standalone-v1'
CARRIER='retained-standalone-observations-v1'
BODY_LIMIT=256*1024**2
KIND='standalone-retained-ddl-v1'
RECORD_KIND='retained_standalone'
FIELDS={'version','kind','ddl_id','owner','source_sha256','target_sha256','review_sha256'}
_CORES=weakref.WeakKeyDictionary()
_EVENTS=weakref.WeakKeyDictionary()
_EVENT_SEALS=weakref.WeakKeyDictionary()
_FINALS=weakref.WeakKeyDictionary()
_SEALS=weakref.WeakKeyDictionary()
_OWNERS=weakref.WeakKeyDictionary()
_ARTIFACTS=weakref.WeakKeyDictionary()
_ARTIFACT_SEALS=weakref.WeakKeyDictionary()
_RESERVATIONS=weakref.WeakKeyDictionary()
_DIRS=weakref.WeakKeyDictionary()
_RESOURCES=weakref.WeakKeyDictionary()
MAX_ENTRIES=100000
MAX_FILE=256*1024**2


def request(value):
    o.check(type(value) is dict and set(value)==FIELDS and type(value['version']) is int
            and value['version']==1 and value['kind']==KIND,'standalone-request')
    o.check(type(value['ddl_id']) is str and re.fullmatch(r'[0-9]{1,20}(?:-[0-9]{1,8})?',value['ddl_id']),'standalone-DDL')
    for k in ('source_sha256','target_sha256','review_sha256'):
        o.check(type(value[k]) is str and re.fullmatch('[0-9a-f]{64}',value[k]),'standalone-digest')
    o.check(len(o.compact(value))<4096,'standalone-selector-bound')
    return copy.deepcopy(value)


def _primitive(c):
    return copy.deepcopy({k:c[k] for k in ('request','generation','token','source','target','ddl','catalog_row','files','hashes',
        'nodes','absent','namespaces','claims','observed','sql','workflow_sql','census','source_inventory','target_inventory','source_pins','sql_parents','journal','phase','deadline','pid','thread')})


def _commit(c,changes):
    old=_SEALS.get(c['session'])
    o.check(old is not None and all(c[k]==v for k,v in old.items()),'standalone-original-core-before-successor')
    expected=copy.deepcopy(old)
    for k,v in changes.items():expected[k]=copy.deepcopy(v)
    for k,v in changes.items():c[k]=v
    _SEALS[c['session']]=expected
    return expected


def _append(c,path,stamp,digest):
    old=_SEALS[c['session']]
    files=dict(old['files']);hashes=dict(old['hashes']);names=copy.deepcopy(old['namespaces'])
    key=str(path);o.check(key not in files and Path(key).name not in names[str(c['folder'])],'standalone-exclusive-owned-successor')
    files[key]=stamp;hashes[key]=digest;names[str(c['folder'])]=tuple(sorted((*names[str(c['folder'])],Path(key).name)))
    return _commit(c,{'files':files,'hashes':hashes,'namespaces':names})


def _bindings(c,held):
    import mylar
    if mylar.CONFIG is not c['config'] or str(mylar.CONFIG.DDL_LOCATION)!=c['config_cache']:raise o.Held('standalone-original-config')
    w=c['writer'];p=c['controller']
    if (w.root,w.lock,w.pending,w.tagger_pending,w.release_pending,tuple(w.lock_identity),tuple(w.root_identity),w.local)!=c['wb']:
        raise o.Held('standalone-Writer-identity')
    if (p.root,p.database,p.native_database,p.writer_root,tuple(p.roots),p.tool_root)!=c['cb']:
        raise o.Held('standalone-Controller-identity')
    if (held and getattr(w.local[1],'depth',0)<=0) or any(getattr(w.local[1],k,False) for k in
             ('allow_pending','allow_tagger_pending','allow_release_pending')):raise o.Held('standalone-purpose')



def _fd9(fd):
    z=os.fstat(fd)
    return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)


class _DirectoryResources:
    """Local original file-identity ledger, not an open-file-description grant."""
    __slots__=('rows','session')
    def __init__(self):self.rows=[];self.session=None
    def rollback(self,start=0):
        refused=False
        for fd,identity in reversed(self.rows[start:]):
            try:z=os.fstat(fd)
            except OSError:
                refused=True;continue
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=identity:
                # Never close a foreign reused descriptor. Same-inode OFD
                # reopening remains indistinguishable under these primitives.
                refused=True;continue
            os.close(fd)
        del self.rows[start:]
        if refused:raise o.Held('standalone-directory-resource-identity-unknown')


def _open_directory(path,resources=None):
    local=_DirectoryResources() if resources is None else resources
    start=len(local.rows)
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    # Inline original registration before the first declared helper callback.
    z=os.fstat(fd)
    local.rows.append((fd,(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)))
    try:
        stamp=_fd9(fd);names=tuple(sorted(os.listdir(fd)))
        return fd,stamp,names
    except BaseException:
        local.rollback(start)
        raise


def _register_directory(c,path,fd,stamp):
    old=_DIRS.get(c['session'],())
    o.check(c.get('dir_registry',()) is old,'standalone-directory-original-registry')
    key=str(path);o.check(not any(row[0]==key for row in old),'standalone-directory-exclusive-registry')
    identity=(stamp[0],stamp[1],stamp[5],stamp[6],stamp[7])
    c['dir_registry']=(*old,(key,fd,identity));_DIRS[c['session']]=c['dir_registry']


def _parent_current(row):
    if row['workflow_cas'] is not None:return tuple(row['workflow_cas']['after9']),tuple(row['workflow_cas']['names'])
    if row['native_noop'] is not None:return tuple(row['native_noop']['after9']),tuple(row['native_noop']['names'])
    if row['backup9'] is not None:return tuple(row['backup9']),tuple(row['backup_names'])
    return tuple(row['initialized9']),tuple(row['initialized_names'])


def _directory_expected(c,original):
    expected={row['path']:_parent_current(row) for row in original['sql_parents']}
    j=original['journal']
    if j:
        expected[j['path']]=(tuple(j['after9']),tuple(j['after_names']))
        current=j['accepted'] or (j['preservation'][-1] if j['preservation'] else None)
        expected[j['directory']]=(tuple(current['after9']) if current else tuple(j['initialized9']),
            tuple(current['after_names']) if current else tuple(j['initialized_names']))
    artifacts=_ARTIFACT_SEALS.get(c['session'])
    if artifacts:
        for path,stamp,names in ((artifacts['carrier'],artifacts['carrier_after9'],artifacts['carrier_after_names']),
            (artifacts['directory'],artifacts['directory_after9'],artifacts['bodies'])):
            fact=(tuple(stamp),tuple(names));o.check(path not in expected or expected[path]==fact,'standalone-directory-role-conflict')
            expected.setdefault(path,fact)
    return expected


def _write_owned(c,path,raw):
    """Original dirFD insertion captured BEFORE stream/readback helper callbacks."""
    original=_SEALS[c['session']];before,names=_directory_expected(c,original)[str(path.parent)]
    row=next(row for row in _DIRS[c['session']] if row[0]==str(path.parent));parent=row[1]
    o.check(_fd9(parent)==before and tuple(sorted(os.listdir(parent)))==names,'standalone-output-parent-original')
    digest=hashlib.sha256(raw).hexdigest();o.check(len(raw)<=MAX_FILE,'standalone-output-bound')
    fd=os.open(path.name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
    try:
        # Both births precede external encoding/stream/fsync/readback helpers.
        created=_fd9(fd);after=_fd9(parent)
        identity=(created[0],created[1],*created[5:])
        o.check(created[5]&0o170000==0o100000 and created[5]&0o7777==0o600 and created[6:]==(os.geteuid(),os.getegid(),1),'standalone-output-exclusive-FD')
        o.check(after[:2]==before[:2] and after[5:]==before[5:],'standalone-output-parent-exact-birth')
        view=memoryview(raw)
        while view:
            count=os.write(fd,view);o.check(count>0,'standalone-output-short-write');view=view[count:]
        os.fsync(fd);os.lseek(fd,0,0);remaining=len(raw);h=hashlib.sha256()
        while remaining:
            block=os.read(fd,min(remaining,1024*1024));o.check(block,'standalone-output-readback');h.update(block);remaining-=len(block)
        o.check(not os.read(fd,1) and h.hexdigest()==digest,'standalone-output-intended-bytes')
        stamp=_fd9(fd);o.check((stamp[0],stamp[1],*stamp[5:])==identity,'standalone-output-original-created-FD')
        os.fsync(parent)
        o.check(_fd9(parent)==after,'standalone-output-parent-no-late-refresh')
    finally:os.close(fd)
    after_names=tuple(sorted((*names,path.name)))
    o.check(tuple(sorted(os.listdir(parent)))==after_names,'standalone-output-exact-namespace')
    z=os.lstat(path)
    if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise o.Held('standalone-output-final')
    return stamp,digest,{'name':path.name,'before9':before,'after9':after,'before_names':names,'after_names':after_names,
        'file_ref':{'path':str(path),'signature9':list(stamp),'sha256':digest}}


def _journal_output(c,path,raw,kind):
    j=_SEALS[c['session']]['journal'];o.check(str(path.parent)==j['directory'],'standalone-output-fixed-directory')
    if kind=='initialized':o.check(c['phase']=='initialized' and path.name=='intent.json' and j['initialized_names']==(),'standalone-output-initialized-role')
    elif kind=='preservation':
        count=len(j['preservation']);o.check(c['phase']=='prepared' and count<2 and path.name==('target-preserved' if count==0 else 'target-restored')+Path(c['target']).suffix.lower(),'standalone-output-preservation-role')
    elif kind=='accepted':o.check(c['phase']=='accepted' and path.name=='accepted.json' and len(j['preservation'])==2 and j['accepted'] is None,'standalone-output-accepted-role')
    else:raise o.Held('standalone-output-finite-role')
    stamp,digest,transition=_write_owned(c,path,raw);old=_SEALS[c['session']];j=copy.deepcopy(old['journal'])
    if kind=='initialized':j['initialized9']=transition['after9'];j['initialized_names']=transition['after_names']
    elif kind=='preservation':j['preservation'].append(transition)
    elif kind=='accepted':o.check(j['accepted'] is None,'standalone-exclusive-accepted-transition');j['accepted']=transition
    else:raise o.Held('standalone-output-finite-role')
    files=dict(old['files']);hashes=dict(old['hashes']);names=copy.deepcopy(old['namespaces'])
    key=str(path);o.check(key not in files,'standalone-output-no-existing-leaf');files[key]=stamp;hashes[key]=digest;names[str(path.parent)]=transition['after_names']
    _commit(c,{'journal':j,'files':files,'hashes':hashes,'namespaces':names})
    return stamp,digest


def _sql_parent_successor(c,role,raw_after):
    parents=copy.deepcopy(_SEALS[c['session']]['sql_parents'])
    for row in parents:
        if role not in row['database_roles']:continue
        before,names=_parent_current(row);after=raw_after[row['path']]
        o.check(after[:2]==before[:2] and after[5:]==before[5:],'standalone-SQL-parent-immutable-original')
        o.check(tuple(sorted(os.listdir(row['path'])))==names,'standalone-SQL-parent-exact-names')
        field='native_noop' if role=='native' else 'workflow_cas';o.check(row[field] is None,'standalone-SQL-parent-once')
        row[field]={'before9':before,'after9':after,'names':names}
    return parents


def _raw(c,original,held=True):
    # Replaceable deadline/identity/purpose helpers precede final physical loops.
    directory_expected=_directory_expected(c,original);dir_registry=_DIRS.get(c['session'])
    if dir_registry is not c.get('dir_registry'):raise o.Held('standalone-directory-registry')
    directory_facts={path:_fd9(fd) for path,fd,_ in dir_registry}
    package=sys.modules.get('mylar');pid=os.getpid();thread=threading.get_ident();now=time.monotonic();_bindings(c,held)
    action=c['action'];channel_core=c['channel_core']
    in_stat=os.fstat(channel_core['input_fd']);out_stat=os.fstat(channel_core['output_fd'])
    in9=(in_stat.st_dev,in_stat.st_ino,in_stat.st_size,in_stat.st_mtime_ns,in_stat.st_ctime_ns,in_stat.st_mode,in_stat.st_uid,in_stat.st_gid,in_stat.st_nlink)
    out9=(out_stat.st_dev,out_stat.st_ino,out_stat.st_size,out_stat.st_mtime_ns,out_stat.st_ctime_ns,out_stat.st_mode,out_stat.st_uid,out_stat.st_gid,out_stat.st_nlink)
    if in9!=channel_core['input9'] or out9!=channel_core['output9']:raise o.Held('standalone-original-pipe-FD')
    if (pid,thread)!=(c['pid'],c['thread']) or now>=c['deadline']:raise o.Held('standalone-lifetime')
    for p,names in original['namespaces'].items():
        if tuple(sorted(os.listdir(p)))!=names:raise o.Held('standalone-census')
    for p in original['absent']:
        try:os.lstat(p)
        except FileNotFoundError:continue
        raise o.Held('standalone-absence')
    for p,v in original['claims'].items():
        try:z=os.lstat(p)
        except FileNotFoundError:
            if v is not None:raise o.Held('standalone-claim')
            continue
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)!=v:raise o.Held('standalone-claim')
    for p,v in original['observed'].items():
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise o.Held('standalone-unaffected-original')
    artifacts=_ARTIFACTS.get(c['session']);artifact_original=_ARTIFACT_SEALS.get(c['session'])
    if artifacts != artifact_original:raise o.Held('standalone-publication-original-seal')
    if artifact_original is not None:
        for path,v in ((artifact_original['carrier'],artifact_original['carrier_after9']),(artifact_original['directory'],artifact_original['directory_after9'])):
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise o.Held('standalone-publication-directory-original')
    for path,(stamp,names) in directory_expected.items():
        if directory_facts.get(path)!=stamp or tuple(sorted(os.listdir(path)))!=names:raise o.Held('standalone-directory-FD-original')
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise o.Held('standalone-directory-physical-original')
    for p,v in original['nodes'].items():
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise o.Held('standalone-node')
    for p,v in original['files'].items():
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise o.Held('standalone-file')
    if _ARTIFACTS.get(c['session']) is not artifacts or artifacts!=artifact_original or _ARTIFACT_SEALS.get(c['session']) is not artifact_original:raise o.Held('standalone-publication-registry-final')
    if _DIRS.get(c['session']) is not dir_registry or c.get('dir_registry') is not dir_registry:raise o.Held('standalone-directory-registry-final')
    # Complete primitive core and actual registry checks AFTER physical callbacks.
    if any(c[k]!=v for k,v in original.items()) or _CORES.get(c['session']) is not c or _SEALS.get(c['session'])!=original:raise o.Held('standalone-core')
    own=_OWNERS.get(c['session'])
    if own is None or c['controller'] is not own[0] or c['writer'] is not own[1] or c['modules'] is not own[2] or c['wb']!=own[3] or c['cb']!=own[4] or c['config'] is not own[5] or c['config_cache']!=own[6] or c['channel'] is not own[7] or c['action'] is not own[8] or c['channel_core'] is not own[9] or c['carrier_initial']!=own[10] or c['carrier_original_fd']!=own[11]:raise o.Held('standalone-original-owning-objects')
    if sys.modules.get('mylar') is not package or package.CONFIG is not c['config'] or package.CONFIG.DDL_LOCATION!=c['config_cache']:raise o.Held('standalone-original-config-final')
    w=c['writer'];p=c['controller']
    if (w.root,w.lock,w.pending,w.tagger_pending,w.release_pending,tuple(w.lock_identity),tuple(w.root_identity),w.local)!=c['wb']:
        raise o.Held('standalone-Writer-final')
    if (p.root,p.database,p.native_database,p.writer_root,tuple(p.roots),p.tool_root)!=c['cb']:raise o.Held('standalone-Controller-final')
    if (held and getattr(w.local[1],'depth',0)<=0) or any(getattr(w.local[1],k,False) for k in
             ('allow_pending','allow_tagger_pending','allow_release_pending')):raise o.Held('standalone-purpose-final')
    if action._CHANNELS.get(c['channel']) is not channel_core or channel_core['binding']!=action._ORIGINALS[c['channel']][1] or channel_core['binding']!=(channel_core['input_fd'],channel_core['output_fd'],channel_core['input9'],channel_core['output9'],channel_core['owner'],channel_core['deadline'],channel_core['boot_bytes']):raise o.Held('standalone-original-channel-final')
    if not all(channel_core[k]==v for k,v in action._TRANSPORT[c['channel']].items()):raise o.Held('standalone-original-channel-state-final')
    if c.get('cap') is not None:
        event=_EVENTS.get(c['cap'])
        if event is None or event['core'] is not c or action._READY.get(c['channel']) is not event['ready_original'] or event['ready_original'] is not c['ready_original'] or event['ready_original'][:2]!=(c['session'],c['backup_digest']):raise o.Held('standalone-original-cap-ready-final')
        if event['event'] is not None and event['event']!=_EVENT_SEALS.get(c['cap']):raise o.Held('standalone-original-event-final')
        if event.get('reservation') is not None and _RESERVATIONS.get(c['cap']) is not event['reservation']:raise o.Held('standalone-original-reservation-final')



def _validate(c,held=True):
    original=_SEALS.get(c['session']);o.check(original is not None,'standalone-original-core-seal');g=c['modules'][2]
    o.check(all(c[k]==v for k,v in original.items()),'standalone-original-core-at-entry')
    _bindings(c,held)
    for p,v in original['files'].items():
        raw=o.read_checked(p,list(v),MAX_FILE,c['deadline'])
        o.check(hashlib.sha256(raw).hexdigest()==original['hashes'][p],'standalone-original-hash')
    o.check(r._sql(c['controller'].native_database,original['files'][str(c['controller'].native_database)])==c['sql'],'standalone-SQL')
    o.check(r._sql(c['controller'].database,original['files'][str(c['controller'].database)])==c['workflow_sql'],'standalone-workflow-SQL')
    o.check(g.media_snapshot(c['controller'].database,c['writer'].root/'publication-v1.json')[0]==c['census'],'standalone-authority-census')
    _raw(c,original,held)
    return original


def _sources(controls,trees,absent):
    paths=tuple(dict.fromkeys((__file__,r.__file__,o.__file__,*map(str,controls))))
    files={};nodes={};hashes={};observed={};names={};claims={}
    # ALL known source/control leaves and configured tree facts precede streams/SDK callbacks.
    for name in paths:
        p=Path(name).absolute();z=os.lstat(p);files[str(p)]=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
        for q in p.parents:
            z=os.lstat(q);v=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
            if str(q) in nodes and nodes[str(q)]!=v:raise o.Held('standalone-first-source-node')
            nodes.setdefault(str(q),v)
    for name in absent:
        if os.path.lexists(name):raise o.Held('standalone-first-absence')
    todo=list(map(Path,trees));count=0
    while todo:
        p=todo.pop();z=os.lstat(p);mode=z.st_mode&0o170000
        if mode not in (0o040000,0o100000):raise o.Held('standalone-first-tree-type')
        count+=1
        if count>MAX_ENTRIES:raise o.Held('standalone-first-tree-bound')
        key=str(p);v=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if mode==0o040000 else z.st_nlink)
        if key in claims and claims[key]!=v:raise o.Held('standalone-first-tree-conflict')
        claims.setdefault(key,v)
        if mode==0o040000:
            nv=v[:5]
            if key in nodes and nodes[key]!=nv:raise o.Held('standalone-first-node-conflict')
            nodes.setdefault(key,nv);names[key]=tuple(sorted(os.listdir(p)));todo.extend(p/n for n in names[key])
        else:observed[key]=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
    for p,v in files.items():hashes[p]=hashlib.sha256(o.read_checked(p,list(v),MAX_FILE,time.monotonic()+120)).hexdigest()
    r._raw(files,nodes,absent,names,claims)
    for p,v in observed.items():
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise o.Held('standalone-first-observed')
    return files,hashes,nodes,observed,names,claims



class StandaloneSession:
    __slots__=('__weakref__',)
    def __init__(self):raise o.Held('standalone-owning-factory-required')
    def frame(self):
        c=_CORES.get(self);o.check(c is not None,'standalone-live-session')
        original=_validate(c,held=False)
        value={'generation':c['generation'],'request_sha256':o.digest(c['request']),'original_vectors':original}
        raw=o.compact(value);_raw(c,original,held=False)
        return raw


class StandaloneAcceptance:
    __slots__=('__weakref__',)
    def __init__(self):raise o.Held('standalone-owning-acceptance-required')
    def accept(self,**kwargs):return accept(self,**kwargs)
    def finalize(self,**kwargs):return finalize(self,**kwargs)
    def status(self):return status_existing(self)


def initialize(controller,writer,value,*,conversation):
    resources=_DirectoryResources()
    try:return _initialize(controller,writer,value,conversation=conversation,resources=resources)
    except BaseException:
        session=resources.session
        if session is not None:
            # An internal partial session is not an accepted/replayable handle.
            for registry in (_CORES,_OWNERS,_SEALS,_DIRS,_RESOURCES):registry.pop(session,None)
        resources.rollback()
        raise


def _initialize(controller,writer,value,*,conversation,resources):
    if not ENABLED:
        if __package__:from . import comic_retained_standalone_action as authenticated_action
        else:import comic_retained_standalone_action as authenticated_action
        try:authenticated_action.authorize_initialize(conversation,sys.modules[__name__],controller,writer,value)
        except ValueError:raise o.Held('standalone-default-disabled') from None
    original_wb=(writer.root,writer.lock,writer.pending,writer.tagger_pending,writer.release_pending,tuple(writer.lock_identity),tuple(writer.root_identity),writer.local)
    original_cb=(controller.root,controller.database,controller.native_database,controller.writer_root,tuple(controller.roots),controller.tool_root)
    import mylar
    original_config=mylar.CONFIG;original_cache=Path(original_config.DDL_LOCATION)
    if __package__:from . import comic_retained_standalone_action as action
    else:import comic_retained_standalone_action as action
    parent_capture={}
    for role,path in (('native',controller.native_database),('workflow',controller.database)):
        key=str(path.parent)
        if key not in parent_capture:
            fd,v,names=_open_directory(path.parent,resources);parent_capture[key]=(fd,v,names,[])
        parent_capture[key][3].append(role)
    journal_path=controller.root/NAME
    journal_capture=_open_directory(journal_path,resources) if os.path.lexists(journal_path) else None
    carrier_path=controller.root/CARRIER
    carrier_capture=_open_directory(carrier_path,resources) if os.path.lexists(carrier_path) else None
    controls=(controller.database,controller.native_database,writer.lock,writer.root/'publication-v1.json')
    absent=tuple(str(p)+suffix for p in (controller.database,controller.native_database) for suffix in ('-journal','-wal','-shm'))+tuple(str(writer.root/name) for name in r.PENDING_NAMES)
    journal=controller.root/NAME;original_journal_present=os.path.lexists(journal)
    carrier=controller.root/CARRIER;carrier_present=carrier_capture is not None
    carrier_before9=carrier_capture[1] if carrier_present else None
    carrier_before_names=carrier_capture[2] if carrier_present else ()
    initial_absent=(*absent,*(() if original_journal_present else (str(journal),)),*(() if carrier_present else (str(carrier),)))
    trees=(*map(Path,controller.roots),original_cache,writer.root,*((journal,) if original_journal_present else ()),*((carrier,) if carrier_present else ()))
    sf,sh,sn,observed,names,claims=_sources(controls,trees,initial_absent)
    original_channel=action.initialization_originals(conversation,value)
    modules=o.sdk();roots,_=o.writer_pair(controller,writer,modules);g=modules[2]
    o.check(r._writer_binding(writer)==original_wb and r._controller_binding(controller)==original_cb,'standalone-original-bindings-before-SDK')
    value=request(value);o.check(value==original_channel['request'],'standalone-original-selector-before-SDK');value['owner']=g.exact_owner(value['owner']);owner=value['owner']
    import mylar
    cache=o.canonical(mylar.CONFIG.DDL_LOCATION)
    o.check(cache!=controller.root and not any(cache.is_relative_to(p) or p.is_relative_to(cache) for p in roots),'standalone-cache-separated')
    deadline=time.monotonic()+1800
    c=dict(controller=controller,writer=writer,modules=modules,pid=os.getpid(),thread=threading.get_ident(),deadline=deadline,
        wb=original_wb,cb=original_cb,request=value,phase='initializing',
        config=original_config,config_cache=str(original_cache),channel=conversation,action=action,channel_core=action._CHANNELS[conversation],
        carrier_initial=(str(carrier),carrier_before9,carrier_before_names),carrier_original_fd=None if carrier_capture is None else carrier_capture[0],
        files=dict(sf),hashes=dict(sh),nodes=dict(sn),absent=(),namespaces=names,claims=claims,observed=observed,source_pins={p:sh[p] for p in (__file__,r.__file__,o.__file__)},
        sql_parents=[],journal={},dir_registry=())
    for path,v in original_channel['files'].items():
        if path in c['files'] and c['files'][path]!=v:raise o.Held('standalone-preimport-file-conflict')
        c['files'].setdefault(path,v);c['hashes'][path]=original_channel['hashes'][path]
        claim=(v[0],v[1],v[5],v[6],v[7],v[8])
        if path in c['claims'] and c['claims'][path]!=claim:raise o.Held('standalone-original-control-claim-conflict')
        c['claims'].setdefault(path,claim)
    r._join_nodes(c['nodes'],original_channel['nodes'])
    for p in (controller.database,controller.native_database,writer.lock,writer.root/'publication-v1.json'):
        key=str(p);z=os.lstat(p);v=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
        if key in c['files'] and c['files'][key]!=v:raise o.Held('standalone-control-conflict')
        c['files'][key]=v
    r._join_nodes(c['nodes'],r._nodes(tuple(c['files'])))
    c['absent']=absent
    for p,v in tuple(c['files'].items()):c['hashes'][p]=hashlib.sha256(o.read_checked(p,list(v),MAX_FILE,deadline)).hexdigest()
    r._raw(c['files'],c['nodes'],c['absent'],c['namespaces'],c['claims'])
    c['sql']=r._sql(controller.native_database,c['files'][str(controller.native_database)])
    c['workflow_sql']=r._sql(controller.database,c['files'][str(controller.database)])
    with closing(sqlite3.connect(controller.native_database.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        db.row_factory=sqlite3.Row
        rows=db.execute('SELECT * FROM ddl_info WHERE id=?',(value['ddl_id'],)).fetchall()
        o.check(len(rows)==1,'standalone-unique-DDL');row=dict(rows[0])
        o.check(row['status']=='Completed' and str(row['pack']).lower() in ('0','false') and str(row['issueid'])==owner['issueid']
                and str(row['comicid'])==owner['parentcomicid'],'standalone-DDL-owner')
        name=row['filename'];o.check(type(name) is str and name and Path(name).name==name and name not in ('.','..') and '\\' not in name,'standalone-basename')
        cr=db.execute('SELECT * FROM '+owner['table']+' WHERE IssueID=?',(owner['issueid'],)).fetchall()
        o.check(len(cr)==1,'standalone-catalog-owner');c['catalog_row']=dict(cr[0]);c['ddl']=row
    source=cache/name;o.check(source.suffix.lower() in ('.cbz','.cbr','.zip'),'standalone-format')
    catalog,claims,more=o.catalog(controller,owner,g,deadline)
    for p,v in claims.items():
        key=str(p);v=None if v is None else tuple(v)
        if key in c['claims'] and c['claims'][key]!=v:raise o.Held('standalone-catalog-original-conflict')
        c['claims'].setdefault(key,v)
    r._join_nodes(c['nodes'],{str(p):tuple(v) for p,v in more.items()})
    target=Path(catalog['owner']['path']);c['source']=str(source);c['target']=str(target)
    for p,expected in ((source,value['source_sha256']),(target,value['target_sha256'])):
        original=c['observed'].get(str(p));o.check(original is not None and original[5]&0o170000==0o100000 and original[8]==1,'standalone-original-selected-leaf')
        raw=o.read_checked(p,list(original),MAX_FILE,deadline);h=hashlib.sha256(raw).hexdigest()
        o.check(h==expected,'standalone-reviewed-source-target');c['files'][str(p)]=original;c['hashes'][str(p)]=h
    o.check(c['files'][str(source)][:2]!=c['files'][str(target)][:2],'standalone-independent-source')
    controls_identity={v[:2] for path,v in original_channel['files'].items()}
    o.check(c['files'][str(source)][:2] not in controls_identity and c['files'][str(target)][:2] not in controls_identity,'standalone-selected-control-alias')
    r._join_nodes(c['nodes'],r._nodes([source,target]))
    # Library/cache original9 and censuses were captured before the first stream.
    c['source_inventory']=g.inventory(source,tool_root=controller.tool_root,deadline=deadline)
    c['target_inventory']=g.inventory(target,tool_root=controller.tool_root,deadline=deadline)
    o.check(c['source_inventory']['payload']==c['target_inventory']['payload'] and c['source_inventory']['pages']==c['target_inventory']['pages'],
            'standalone-original-pages')
    # Metadata is explicit: require identical member/payload inventory, not inferred historical delivery.
    o.check(c['source_inventory']['members']==c['target_inventory']['members'],'standalone-original-metadata')
    o.check(controller._check({'owner':owner,'payload':c['source_inventory']['payload']},writer)['decision'] in ('allowed','unknown'),'standalone-policy')
    c['generation']=o.digest({'kind':'fresh-retained-source-generation','ddl':row,'owner':owner,'source':str(source),
        'source9':c['files'][str(source)],'source_sha256':value['source_sha256'],'cache_census':c['namespaces'][str(cache)]})
    c['token']=o.digest({'ddl_id':value['ddl_id'],'owner':owner,'kind':KIND})
    action._close(conversation)
    o.check(value==original_channel['request'],'standalone-original-selector-before-intent')
    journal=controller.root/NAME
    for path,(fd,v,names,roles) in parent_capture.items():
        o.check(_fd9(fd)==v and tuple(sorted(os.listdir(fd)))==names,'standalone-original-SQL-parent-before-birth')
    if journal_capture is not None:
        o.check(_fd9(journal_capture[0])==journal_capture[1] and tuple(sorted(os.listdir(journal_capture[0])))==journal_capture[2],'standalone-original-journal-before-birth')
    if not original_journal_present:
        o.check(not os.path.lexists(journal),'standalone-original-journal-absence');os.mkdir(journal,0o700)
        journal_fd,journal_birth9,journal_birth_names=_open_directory(journal,resources)
        o.check(journal_birth9[5]&0o7777==0o700 and journal_birth9[6:]==(os.geteuid(),os.getegid(),2) and journal_birth_names==(),'standalone-journal-exclusive-birth')
    elif tuple(sorted(os.listdir(journal)))!=c['namespaces'][str(journal)]:raise o.Held('standalone-original-journal-census')
    if original_journal_present:journal_fd,journal_birth9,journal_birth_names=journal_capture
    z=os.lstat(journal);jv=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
    o.check(jv[2]&0o7777==0o700 and jv[2]&0o170000==0o040000 and jv[3:]==(os.geteuid(),os.getegid()),'standalone-private-journal')
    names=c['namespaces'][str(journal)] if original_journal_present else ();o.check(len(names)<4096 and all(re.fullmatch('[0-9a-f]{64}',n) for n in names),'standalone-journal-bound')
    folder=journal/c['token'];os.mkdir(folder,0o700);folder_fd,folder_birth9,folder_names=_open_directory(folder,resources)
    journal_after9=_fd9(journal_fd)
    o.check(journal_after9[:2]==journal_birth9[:2] and journal_after9[5:8]==journal_birth9[5:8] and journal_after9[8]==journal_birth9[8]+1,'standalone-journal-sole-token-birth')
    z=os.lstat(folder);fv=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
    r._join_nodes(c['nodes'],{str(journal):jv,str(folder):fv});r._join_nodes(c['nodes'],r._nodes([folder]))
    c['folder']=folder;c['namespaces'][str(journal)]=tuple(sorted((*names,c['token'])));c['namespaces'][str(folder)]=()
    c['census']=g.media_snapshot(controller.database,writer.root/'publication-v1.json')[0]
    c['journal']={'path':str(journal),'before9':None if not original_journal_present else journal_capture[1],
        'before_names':() if not original_journal_present else journal_capture[2],
        'journal_birth9':journal_birth9 if not original_journal_present else None,
        'after9':journal_after9,'after_names':c['namespaces'][str(journal)],'directory':str(folder),
        'birth9':folder_birth9,'initialized9':folder_birth9,'initialized_names':(),'preservation':[],'accepted':None}
    for path,(fd,v,old_names,roles) in sorted(parent_capture.items()):
        after=_fd9(fd);expected_names=tuple(sorted((*old_names,*((NAME,) if not original_journal_present and str(journal.parent)==path else ()))))
        increments=1 if not original_journal_present and str(journal.parent)==path else 0
        o.check(after[:2]==v[:2] and after[5:8]==v[5:8] and after[8]==v[8]+increments and tuple(sorted(os.listdir(fd)))==expected_names,'standalone-SQL-parent-owning-journal-birth')
        c['sql_parents'].append({'path':path,'database_roles':sorted(roles),'pre_initialize9':v,'pre_initialize_names':old_names,
            'initialized9':after,'initialized_names':expected_names,'backup9':None,'backup_names':None,'native_noop':None,'workflow_cas':None})
    c['phase']='initialized'
    session=object.__new__(StandaloneSession);c['session']=session;resources.session=session;_CORES[session]=c;_RESOURCES[session]=resources
    for path,(fd,v,_,_) in sorted(parent_capture.items()):_register_directory(c,path,fd,v)
    _register_directory(c,journal,journal_fd,journal_birth9);_register_directory(c,folder,folder_fd,folder_birth9)
    _OWNERS[session]=(controller,writer,modules,c['wb'],c['cb'],original_config,str(original_cache),conversation,action,c['channel_core'],c['carrier_initial'],c['carrier_original_fd'])
    _SEALS[session]=_primitive(c)
    intent={'version':1,'kind':KIND,'request':value,'generation':c['generation'],'token':c['token'],'historical_import_ack':False}
    v,h=_journal_output(c,folder/'intent.json',o.compact(intent),'initialized')
    _validate(c)
    return session


def publish_body(session,kind,raw):
    resources=_RESOURCES.get(session)
    o.check(type(resources) is _DirectoryResources and resources.session is session,'standalone-body-original-resources')
    start=len(resources.rows)
    try:return _publish_body(session,kind,raw,resources=resources)
    except BaseException:
        # Keep original accepted session resources and all partial files intact.
        # Failed new publication resources alone are closed; no rollback/replay.
        resources.rollback(start)
        raise


def _publish_body(session,kind,raw,*,resources):
    o.check(type(session) is StandaloneSession and session in _CORES and type(raw) is bytes and 0<len(raw)<=BODY_LIMIT,'standalone-body-original-session')
    c=_CORES[session];o.check((kind,c['phase']) in (('initialized','initialized'),('observed','finalized')),'standalone-body-phase')
    original=_validate(c);old=_ARTIFACTS.get(session)
    # Publication may encode only the actual live owning session/event.
    if kind=='initialized':
        expected={'generation':c['generation'],'request_sha256':o.digest(c['request']),'original_vectors':original,
            'input_sha256':c['channel_core']['boot_sha256'],'source_map_sha256':c['channel_core']['boot']['source_map_ref']['sha256']}
    else:
        expected={'request_sha256':o.digest(c['request']),'generation':c['generation'],
            'result':status_existing(c['cap']),'original_vectors':original}
        reservation=_RESERVATIONS.get(c['cap']);o.check(reservation is not None and len(raw)<=reservation[2],'standalone-original-observed-capacity')
    o.check(raw==o.compact(expected),'standalone-body-owning-encoded-facts');_raw(c,original)
    carrier=Path(c['carrier_initial'][0]);directory=carrier/c['token']
    if kind=='initialized':
        o.check(old is None,'standalone-body-initialized-once')
        before9=c['carrier_initial'][1];before_names=c['carrier_initial'][2]
        if before9 is None:
            o.check(not os.path.lexists(carrier),'standalone-body-carrier-original-absence')
            os.mkdir(carrier,0o700);carrier_fd,birth9,_=_open_directory(carrier,resources)
            o.check(birth9[5]&0o170000==0o040000 and birth9[5]&0o7777==0o700 and birth9[6:8]==(os.geteuid(),os.getegid()) and birth9[8]==2,'standalone-body-carrier-private-birth')
        else:
            carrier_fd=c['carrier_original_fd'];birth9=_fd9(carrier_fd);o.check(birth9==before9 and tuple(sorted(os.listdir(carrier)))==before_names,'standalone-body-carrier-original')
            o.check(before9[5]&0o170000==0o040000 and before9[5]&0o7777==0o700 and before9[6:8]==(os.geteuid(),os.getegid()),'standalone-body-carrier-private')
        os.mkdir(directory,0o700);directory_fd,directory_before9,_=_open_directory(directory,resources);carrier_after9=_fd9(carrier_fd)
        o.check(directory_before9[5]&0o170000==0o040000 and directory_before9[5]&0o7777==0o700 and directory_before9[6:8]==(os.geteuid(),os.getegid()) and directory_before9[8]==2,'standalone-body-token-private-birth')
        o.check(carrier_after9[:2]==birth9[:2] and carrier_after9[5:8]==birth9[5:8] and carrier_after9[8]==birth9[8]+1,'standalone-body-carrier-sole-directory')
        before=();after_carrier=tuple(sorted((*before_names,c['token'])))
        o.check(tuple(sorted(os.listdir(carrier)))==after_carrier and tuple(sorted(os.listdir(directory)))==before,'standalone-body-exclusive-names')
        nodes=dict(original['nodes']);r._join_nodes(nodes,{str(carrier):(carrier_after9[0],carrier_after9[1],carrier_after9[5],carrier_after9[6],carrier_after9[7]),str(directory):(directory_before9[0],directory_before9[1],directory_before9[5],directory_before9[6],directory_before9[7])})
        names=copy.deepcopy(original['namespaces']);names[str(carrier)]=after_carrier;names[str(directory)]=before
        parents=copy.deepcopy(original['sql_parents'])
        for row in parents:
            parent_fd=next(v[1] for v in _DIRS[session] if v[0]==row['path']);after_parent=_fd9(parent_fd)
            before_parent=tuple(row['initialized9']);old_names=tuple(row['initialized_names'])
            increment=1 if before9 is None and str(carrier.parent)==row['path'] else 0
            expected_names=tuple(sorted((*old_names,*((CARRIER,) if increment else ()))))
            o.check(after_parent[:2]==before_parent[:2] and after_parent[5:8]==before_parent[5:8] and after_parent[8]==before_parent[8]+increment
                and tuple(sorted(os.listdir(parent_fd)))==expected_names,'standalone-SQL-parent-owning-carrier-birth')
            row['backup9']=after_parent;row['backup_names']=expected_names
        _commit(c,{'nodes':nodes,'namespaces':names,'sql_parents':parents})
        _register_directory(c,carrier,carrier_fd,birth9);_register_directory(c,directory,directory_fd,directory_before9)
        provisional={'carrier':str(carrier),'carrier_after9':carrier_after9,'carrier_after_names':after_carrier,
            'directory':str(directory),'directory_after9':directory_before9,'bodies':()}
        _ARTIFACTS[session]=provisional;_ARTIFACT_SEALS[session]=copy.deepcopy(provisional)
        baseline='absent' if before9 is None else 'existing'
    else:
        o.check(old is not None and old['bodies']==('initialized-body.json',),'standalone-body-observed-once')
        before9=old['carrier_after9'];carrier_after9=before9;before_names=old['carrier_after_names'];after_carrier=before_names
        directory_before9=old['directory_after9'];before=('initialized-body.json',);baseline='existing'
        o.check(tuple(o.signature(carrier))==carrier_after9 and tuple(o.signature(directory))==directory_before9,'standalone-body-original-incarnation')
    path=directory/(kind+'-body.json')
    stamp,digest,body_transition=_write_owned(c,path,raw)
    directory_after9=body_transition['after9']
    o.check(directory_after9[:2]==directory_before9[:2] and directory_after9[5:]==directory_before9[5:] and tuple(o.signature(carrier))==carrier_after9,'standalone-body-file-sole-storage-successor')
    after=tuple(sorted((*before,path.name)));o.check(tuple(sorted(os.listdir(directory)))==after,'standalone-body-file-sole-namespace')
    files=dict(_SEALS[session]['files']);hashes=dict(_SEALS[session]['hashes']);names=copy.deepcopy(_SEALS[session]['namespaces'])
    o.check(str(path) not in files,'standalone-body-exclusive-original-leaf');files[str(path)]=stamp;hashes[str(path)]=digest;names[str(directory)]=after
    _commit(c,{'files':files,'hashes':hashes,'namespaces':names})
    artifact={'carrier':str(carrier),'carrier_after9':carrier_after9,'carrier_after_names':after_carrier,'directory':str(directory),
        'directory_after9':directory_after9,'bodies':after}
    _ARTIFACTS[session]=artifact;_ARTIFACT_SEALS[session]=copy.deepcopy(artifact)
    ref={'path':str(path),'signature9':list(stamp),'sha256':digest}
    publication={'carrier':str(carrier),'carrier_baseline':baseline,'carrier_before9':None if before9 is None else list(before9),
        'carrier_after9':list(carrier_after9),'carrier_before_names':list(before_names),'carrier_after_names':list(after_carrier),
        'directory':str(directory),'directory_before9':list(directory_before9),'directory_after9':list(directory_after9),
        'before_names':list(before),'after_names':list(after),
        'sql_parents_after_publication':[{'path':row['path'],'signature9':list(_parent_current(row)[0]),'names':list(_parent_current(row)[1])} for row in _SEALS[session]['sql_parents']]}
    result={'body_ref':ref,'publication':publication};encoded=o.compact(result);answer=json.loads(encoded)
    final=_validate(c)
    if c.get('cap') in _FINALS:
        e,owner,_,terminal_raw=_FINALS[c['cap']];o.check(owner is c,'standalone-body-original-terminal-registry')
        _FINALS[c['cap']]=(e,c,copy.deepcopy(final),terminal_raw)
    _raw(c,final)
    if _ARTIFACTS.get(session) is not artifact:raise o.Held('standalone-body-final-registry')
    return answer


def prepare_existing(session,backup):
    """Consume actual verification or original finite channel; saved JSON cannot prepare."""
    o.check(type(session) is StandaloneSession and session in _CORES,'standalone-original-session')
    c=_CORES[session];o.check(c['phase']=='initialized','standalone-ready-once')
    original=_validate(c)
    if __package__:from .comic_retained_standalone_action import Conversation
    else:from comic_retained_standalone_action import Conversation
    o.check(type(backup) is Conversation,'standalone-original-channel-required')
    digest=backup.consume_ready(session)
    _raw(c,original)
    # Only this trusted readiness transition starts the finite owning cap budget.
    _commit(c,{'deadline':time.monotonic()+120,'phase':'prepared'})
    c['backup_digest']=digest;c['backup']=backup
    if __package__:from . import comic_retained_standalone_action as action
    else:import comic_retained_standalone_action as action
    original_ready=action._READY.get(backup);o.check(original_ready is not None and original_ready[:2]==(session,digest),'standalone-original-ready-registry')
    c['ready_original']=original_ready
    original=_SEALS[c['session']];target=Path(c['target']);raw=o.read_checked(target,list(c['files'][str(target)]),MAX_FILE,c['deadline'])
    for name in ('target-preserved','target-restored'):
        p=c['folder']/(name+target.suffix.lower());prior_identities={q[:2] for q in c['files'].values()};v,h=_journal_output(c,p,raw,'preservation')
        o.check(v[:2] not in prior_identities and h==c['request']['target_sha256'],'standalone-independent-preservation')
        inv=c['modules'][2].inventory(p,tool_root=c['controller'].tool_root,deadline=c['deadline'])
        o.check({k:inv[k] for k in ('payload','pages','members')}=={k:c['target_inventory'][k] for k in ('payload','pages','members')},'standalone-restore-original-content')
    cap=object.__new__(StandaloneAcceptance);c['cap']=cap
    _EVENTS[cap]={'core':c,'phase':'prepared','event':None,'owner':(c['pid'],c['thread']),'ready_original':original_ready}
    _validate(c)
    o.check(_EVENTS.get(cap)['core'] is c,'standalone-cap-registry')
    return cap


def _cap(cap):
    o.check(type(cap) is StandaloneAcceptance and cap in _EVENTS,'standalone-live-cap')
    event=_EVENTS[cap];c=event['core'];o.check((os.getpid(),threading.get_ident())==event['owner'],'standalone-cap-owner')
    o.check(_CORES.get(c['session']) is c and c.get('cap') is cap and c['writer'] is _OWNERS[c['session']][1],'standalone-cap-original-core')
    if __package__:from . import comic_retained_standalone_action as action
    else:import comic_retained_standalone_action as action
    o.check(c['backup'] is c['channel'] and action._READY.get(c['channel']) is event['ready_original'] and c['ready_original'] is event['ready_original']
        and event['ready_original'][:2]==(c['session'],c['backup_digest']),'standalone-cap-original-ready')
    return c,event



UINT64=(1<<64)-1
SQL_BYTES=64*1024**2


def _future9(stamp,*,new_file=False):
    # Finite source-owned unknown cells: no caller-supplied allocation budget.
    if new_file:return (UINT64,UINT64,MAX_FILE,UINT64,UINT64,0o100600,os.geteuid(),os.getegid(),1)
    return (stamp[0],stamp[1],MAX_FILE,UINT64,UINT64,*stamp[5:])


def _owned9(stamp):
    o.check(len(stamp)==9 and all(type(v) is int and 0<=v<=UINT64 for v in stamp)
        and stamp[2]<=MAX_FILE,'standalone-owned-successor-integer-bound')
    return stamp


def _ack_body(c,original):
    return {'version':1,'kind':'fresh-standalone-retained-acceptance','token':c['token'],'request':c['request'],
        'generation':c['generation'],'source':c['source'],'target':c['target'],'backup_sha256':c['backup_digest'],
        'fresh_catalog_event':True,'historical_import_ack':False,'ordinary_import_grant':False,'cleanup_grant':False,
        'index_grant':False,'resume_grant':False,'original_vectors':original}


def _final_value(c,original,original_event):
    return {'version':1,'kind':'fresh-standalone-retained-finalization','token':c['token'],'generation':c['generation'],
        'request':c['request'],'source':c['source'],'target':c['target'],'original_event':original_event,
        'original_vectors':original,'historical_import_ack':False,'ordinary_import_grant':False,'cleanup_grant':False,
        'index_grant':False,'resume_grant':False,'automatic_replay':False}


def _final_result(c,original_event,stamp,digest,record_digest):
    return {'version':1,'outcome':'fresh-standalone-retained-finalized','token':c['token'],'generation':c['generation'],
        'record_kind':RECORD_KIND,'record_sha256':record_digest,'original_event':original_event,
        'record_ref':{'database':str(c['controller'].database),'signature9':list(stamp),'sha256':digest,
            'kind':RECORD_KIND,'key':c['token'],'value_sha256':record_digest},
        'historical_import_ack':False,'ordinary_import_grant':False,'cleanup_grant':False,'index_grant':False,'resume_grant':False}


def _reserve(c):
    """Encode every future nesting BEFORE the protected catalog event.

    Complete original SQL/rows/claims remain; only source-owned successor scalar
    cells use their fixed unsigned64 maxima and fixed-length hexadecimal hashes.
    JSON escaping is counted by actual canonical encoding at every nesting.
    """
    future=copy.deepcopy(_SEALS[c['session']]);future['phase']='accepted'
    native=str(c['controller'].native_database);workflow=str(c['controller'].database)
    future['files'][native]=_future9(future['files'][native]);future['hashes'][native]='f'*64
    for row in future['sql_parents']:
        if 'native' in row['database_roles']:
            before,names=_parent_current(row);after=(before[0],before[1],UINT64,UINT64,UINT64,*before[5:])
            row['native_noop']={'before9':before,'after9':after,'names':names}
    ack_raw=o.compact(_ack_body(c,future));ack=str(c['folder']/'accepted.json')
    future['files'][ack]=_future9((),new_file=True);future['hashes'][ack]='f'*64
    future['namespaces'][str(c['folder'])]=tuple(sorted((*future['namespaces'][str(c['folder'])],'accepted.json')))
    j=future['journal'];before=tuple(j['preservation'][-1]['after9']);names=tuple(j['preservation'][-1]['after_names'])
    j['accepted']={'name':'accepted.json','before9':before,'after9':(before[0],before[1],UINT64,UINT64,UINT64,*before[5:]),
        'before_names':names,'after_names':future['namespaces'][str(c['folder'])],
        'file_ref':{'path':ack,'signature9':list(future['files'][ack]),'sha256':'f'*64}}
    event={'ack':{'path':ack,'signature9':list(future['files'][ack]),'sha256':'f'*64},
        'intent':{'path':str(c['folder']/'intent.json'),'signature9':list(future['files'][str(c['folder']/'intent.json')]),
            'sha256':future['hashes'][str(c['folder']/'intent.json')]}}
    value_raw=o.compact(_final_value(c,future,event))
    expected=copy.deepcopy(future['workflow_sql'])
    row=o.compact([RECORD_KIND,c['token'],value_raw.decode(),0.0]).decode()
    expected['rows']['records'].append(row);expected['rows']['records'].sort()
    for sql in (future['sql'],expected):
        o.check(sum(len(v.encode()) for rows in sql['rows'].values() for v in rows)<=SQL_BYTES
            and sum(len(rows) for rows in sql['rows'].values())<=100000,'standalone-future-complete-SQL-capacity')
    future['files'][workflow]=_future9(future['files'][workflow]);future['hashes'][workflow]='f'*64
    future['workflow_sql']=expected;future['phase']='finalized'
    for row in future['sql_parents']:
        if 'workflow' in row['database_roles']:
            before,names=_parent_current(row);after=(before[0],before[1],UINT64,UINT64,UINT64,*before[5:])
            row['workflow_cas']={'before9':before,'after9':after,'names':names}
    result=_final_result(c,event,future['files'][workflow],'f'*64,'f'*64)
    body_raw=o.compact({'request_sha256':o.digest(c['request']),'generation':c['generation'],
        'result':result,'original_vectors':future})
    o.check(max(len(ack_raw),len(value_raw),len(body_raw))<=BODY_LIMIT,'standalone-future-body-capacity')
    action=c['action'];channel=c['channel_core'];token=c['token'];carrier=str(c['controller'].root/CARRIER);directory=str(Path(carrier)/token)
    maximum_directory=[UINT64]*9
    carrier_names=list(_ARTIFACT_SEALS[c['session']]['carrier_after_names'])
    publication={'carrier':carrier,'carrier_baseline':'existing','carrier_before9':maximum_directory,
        'carrier_after9':maximum_directory,'carrier_before_names':carrier_names,'carrier_after_names':carrier_names,
        'directory':directory,'directory_before9':maximum_directory,'directory_after9':maximum_directory,
        'before_names':['initialized-body.json'],'after_names':['initialized-body.json','observed-body.json'],
        'sql_parents_after_publication':[{'path':row['path'],'signature9':list(_parent_current(row)[0]),'names':list(_parent_current(row)[1])} for row in future['sql_parents']]}
    payload={'input_sha256':channel['boot_sha256'],'source_map_sha256':channel['boot']['source_map_ref']['sha256'],
        'request_sha256':o.digest(c['request']),'generation':c['generation'],'phase':'finalized',
        'body_ref':{'path':str(Path(directory)/'observed-body.json'),'sha256':'f'*64,'signature9':list(_future9((),new_file=True))},
        'publication':publication}
    outer={'version':action.WIRE_VERSION,'protocol':action.PROTOCOL,'kind':'observed','nonce':channel['nonce'],
        'sequence':3,'challenge':channel['challenge'],'payload':payload}
    o.check(len(o.compact(outer))<=action.LIMIT,'standalone-future-outer-capacity')
    # Frame1/2 were already actually bounded. Frames4/5/6 have the same fixed
    # envelope and one 64-byte digest, shorter than the full observed header.
    return (len(ack_raw),len(value_raw),len(body_raw),len(o.compact(outer)))


def accept(cap,*,response_hook=None):
    c,event=_cap(cap);o.check(c['phase']=='prepared' and event['phase']=='prepared','standalone-accept-once')
    original=_validate(c);p=c['controller'];owner=c['request']['owner'];before=c['files'][str(p.native_database)]
    reservation=_reserve(c);_raw(c,original);_RESERVATIONS[cap]=reservation;event['reservation']=reservation
    original=_commit(c,{'phase':'uncertain'});event['phase']='uncertain'
    with closing(sqlite3.connect(p.native_database)) as db:
        db.execute('PRAGMA trusted_schema=OFF');db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
        columns=[q[1] for q in db.execute('PRAGMA table_info('+owner['table']+')')]
        row=tuple(c['catalog_row'][name] for name in columns);found=db.execute('SELECT * FROM '+owner['table']+' WHERE IssueID=?',(owner['issueid'],)).fetchall()
        o.check(found==[row],'standalone-owner-CAS')
        loc=row[columns.index('Location')];status=row[columns.index('Status')]
        _raw(c,original)
        count=db.execute('UPDATE '+owner['table']+' SET Location=?,Status=? WHERE IssueID=? AND ComicID=? AND Location IS ? AND Status IS ?',
            (loc,status,owner['issueid'],owner['parentcomicid'],loc,status)).rowcount
        o.check(count==1,'standalone-real-catalog-event');db.commit()
        parent_after={path:_fd9(fd) for path,fd,_ in _DIRS[c['session']] if any(row['path']==path and 'native' in row['database_roles'] for row in original['sql_parents'])}
    now=_owned9(tuple(o.signature(p.native_database)))
    o.check(now[:2]==before[:2] and now[5:]==before[5:] and r._sql(p.native_database,now)==c['sql'],'standalone-sole-SQL-successor')
    digest=hashlib.sha256(o.read_checked(p.native_database,list(now),MAX_FILE,c['deadline'])).hexdigest()
    files=dict(original['files']);hashes=dict(original['hashes']);files[str(p.native_database)]=now;hashes[str(p.native_database)]=digest
    parents=_sql_parent_successor(c,'native',parent_after)
    _commit(c,{'files':files,'hashes':hashes,'sql_parents':parents,'phase':'accepted'});event['phase']='accepted'
    original=_validate(c)
    body=_ack_body(c,original);ack_bytes=o.compact(body)
    o.check(len(ack_bytes)<=reservation[0],'standalone-actual-ACK-reservation')
    pth=c['folder']/'accepted.json';v,h=_journal_output(c,pth,ack_bytes,'accepted')
    original=_validate(c)
    actual_event=(c['token'],c['generation'],str(pth),v,h,o.compact(original),c['backup_digest'])
    result={'version':1,'outcome':'fresh-standalone-retained-accepted','token':c['token'],
        'generation':c['generation'],'ack':{'path':str(pth),'signature9':list(v),'sha256':h},
        'historical_import_ack':False,'ordinary_import_grant':False,'cleanup_grant':False,'index_grant':False,'resume_grant':False}
    encoded=o.compact(result);answer=json.loads(encoded);_raw(c,original)
    if _EVENTS.get(cap) is not event or event['event'] is not None:raise o.Held('standalone-event-final')
    event['event']=actual_event;event['seal']=actual_event;_EVENT_SEALS[cap]=actual_event
    if response_hook is not None:
        response_hook(encoded)  # A raised lost return leaves only the actual original event.
        _raw(c,original)
        if _EVENTS.get(cap) is not event or event['event']!=_EVENT_SEALS.get(cap):raise o.Held('standalone-return-event-final')
    return answer


def finalize(cap,*,response_hook=None):
    c,event=_cap(cap);o.check(c['phase']=='accepted' and event['event'] is not None and event['event']==event['seal']==_EVENT_SEALS.get(cap),'standalone-original-event-required')
    original=_validate(c);p=c['controller'];before=c['workflow_sql'];stamp=c['files'][str(p.database)]
    original_event={'ack':{'path':event['event'][2],'signature9':list(event['event'][3]),'sha256':event['event'][4]},
        'intent':{'path':str(c['folder']/'intent.json'),'signature9':list(c['files'][str(c['folder']/'intent.json')]),'sha256':c['hashes'][str(c['folder']/'intent.json')]}}
    value=_final_value(c,original,original_event)
    encoded=o.compact(value).decode();key=c['token']
    reservation=_RESERVATIONS.get(cap);o.check(reservation is event.get('reservation') and reservation is not None and len(encoded.encode())<=reservation[1],'standalone-original-final-capacity')
    expected=copy.deepcopy(before);expected['rows']['records'].append(o.compact([RECORD_KIND,key,encoded,0.0]).decode());expected['rows']['records'].sort()
    o.check(not any(json.loads(row)[:2]==[RECORD_KIND,key] for row in before['rows']['records']),'standalone-no-existing-final-record')
    original=_commit(c,{'phase':'final-uncertain'});event['phase']='final-uncertain'
    with closing(sqlite3.connect(p.database)) as db:
        db.execute('PRAGMA trusted_schema=OFF');db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
        o.check(r._sql(p.database,stamp)==before,'standalone-original-workflow-CAS');_raw(c,original)
        db.execute('INSERT INTO records(kind,key,value,updated) VALUES(?,?,?,?)',(RECORD_KIND,key,encoded,0.0));db.commit()
        parent_after={path:_fd9(fd) for path,fd,_ in _DIRS[c['session']] if any(row['path']==path and 'workflow' in row['database_roles'] for row in original['sql_parents'])}
    now=_owned9(tuple(o.signature(p.database)))
    o.check(now[:2]==stamp[:2] and now[5:]==stamp[5:] and r._sql(p.database,now)==expected,'standalone-complete-workflow-diff')
    digest=hashlib.sha256(o.read_checked(p.database,list(now),MAX_FILE,c['deadline'])).hexdigest()
    files=dict(original['files']);hashes=dict(original['hashes']);files[str(p.database)]=now;hashes[str(p.database)]=digest
    parents=_sql_parent_successor(c,'workflow',parent_after)
    _commit(c,{'files':files,'hashes':hashes,'workflow_sql':expected,'sql_parents':parents})
    # The authority media census intentionally excludes no unknown record kind:
    # this is an exact owning expected successor, not a fresh uncontrolled baseline.
    old_census=c['census'];next_census=c['modules'][2].media_snapshot(p.database,c['writer'].root/'publication-v1.json')[0]
    o.check(next_census==old_census,'standalone-authority-census-preserved')
    _commit(c,{'phase':'finalized'});event['phase']='finalized';original=_validate(c)
    result=_final_result(c,original_event,now,digest,hashlib.sha256(encoded.encode()).hexdigest())
    raw=o.compact(result);answer=json.loads(raw);_raw(c,original)
    o.check(_EVENTS.get(cap) is event and event['event']==event['seal']==_EVENT_SEALS.get(cap),'standalone-final-event')
    _FINALS[cap]=(event,c,copy.deepcopy(original),raw)
    _raw(c,original)
    if _EVENTS.get(cap) is not event or event['event']!=_EVENT_SEALS.get(cap) or _FINALS.get(cap)!=(event,c,original,raw):raise o.Held('standalone-final-registry-after-physical')
    if response_hook is not None:
        response_hook(raw);_raw(c,original)
        if _FINALS.get(cap)!=(event,c,original,raw):raise o.Held('standalone-return-final-registry')
    return answer


def status_existing(cap):
    """Read-only original same-session lost-return reconciliation; never saved JSON."""
    c,event=_cap(cap)
    o.check(cap in _FINALS and c['phase']=='finalized','standalone-original-committed-final-required')
    e,owner,original,raw=_FINALS[cap]
    o.check(e is event and owner is c and event['event']==event['seal']==_EVENT_SEALS.get(cap),'standalone-original-final-seal')
    _validate(c);answer=json.loads(raw);_raw(c,original)
    if _EVENTS.get(cap) is not event or event['event']!=_EVENT_SEALS.get(cap) or _FINALS.get(cap)!=(e,owner,original,raw):raise o.Held('standalone-original-final-registry')
    return answer
