"""Factual ordinary-import completion, separate from immutable workflow controls.

Only the native processing owner writes; readers get facts, never release rights.
An attempt is one-use even when its completion write has an uncertain response.
"""
from contextlib import contextmanager, closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import threading
import weakref

_LOCK=threading.RLock()
_ATTEMPTS=weakref.WeakKeyDictionary()
_ACKS=weakref.WeakKeyDictionary()
_COPIES=weakref.WeakKeyDictionary()
_NAME='ordinary-import-v1.sqlite'
_LIMIT=4096


def _bytes(value):
    return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def _stamp(path):
    info=Path(path).lstat()
    return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,
            info.st_mode,info.st_uid,info.st_gid,info.st_nlink)


def _nodes(path):
    result=[]
    for parent in Path(path).parents:
        value=_stamp(parent)
        if value[5]&0o170000!=0o040000:raise ValueError('Linked history parent')
        result.append((str(parent),(value[0],value[1],value[5],value[6],value[7])))
    return result


def _close(nodes,files):
    # All replaceable/serialization/SQLite helpers precede these raw closures.
    for path,expected in nodes:
        info=os.lstat(path)
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=expected:
            raise ValueError('Import parent changed')
    for path,expected in files:
        info=os.lstat(path)
        if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,
                info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=tuple(expected):
            raise ValueError('Import file changed')


def _file(path):
    path=Path(path);before=_stamp(path);nodes=_nodes(path)
    if before[5]&0o170000!=0o100000 or before[8]!=1:
        raise ValueError('Import file must be an unlinked regular file')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        info=os.fstat(fd)
        if (info.st_dev,info.st_ino)!=(before[0],before[1]):raise ValueError('Import file replaced')
        digest=hashlib.sha256();count=0
        while chunk:=os.read(fd,1024*1024):
            count+=len(chunk)
            if count>256*1024**2:raise ValueError('Import file exceeds bound')
            digest.update(chunk)
        value=digest.hexdigest()
        _close(nodes,[(str(path),before)])
        return {'signature':list(before),'sha256':value},nodes
    finally:os.close(fd)


@contextmanager
def _database(*,write=False):
    import mylar
    path=Path(mylar.DATA_DIR).absolute()/_NAME
    nodes=_nodes(path)
    created=False
    if write and not os.path.lexists(path):
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_NOFOLLOW,0o600)
        os.close(fd);created=True
    before=_stamp(path)
    if (before[5]&0o170000!=0o100000 or stat.S_IMODE(before[5])!=0o600
            or before[6]!=os.geteuid() or before[7]!=os.getegid() or before[8]!=1
            or before[2]>16*1024**2):raise ValueError('Invalid private import history')
    if any(os.path.lexists(str(path)+suffix) for suffix in ('-journal','-wal','-shm')):
        raise ValueError('Import history requires passive recovery')
    with _LOCK:
        db=sqlite3.connect(path.as_uri()+('?mode=rw' if write else '?mode=ro&immutable=1'),uri=True,timeout=5)
        try:
            db.execute('PRAGMA synchronous=FULL')
            if write:
                if db.execute('PRAGMA journal_mode=DELETE').fetchone()[0]!='delete':
                    raise ValueError('Invalid history journal')
                if created:
                    db.execute('CREATE TABLE completions(token TEXT PRIMARY KEY,attempt TEXT NOT NULL,ack TEXT)')
                    db.execute('CREATE TABLE guided_links(token TEXT PRIMARY KEY,binding TEXT NOT NULL)')
                    db.commit()
            if {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}!={'completions','guided_links'}:
                raise ValueError('Unknown or partial import history schema')
            for table,columns in (('completions',[('token','TEXT',0,1),('attempt','TEXT',1,0),('ack','TEXT',0,0)]),
                                  ('guided_links',[('token','TEXT',0,1),('binding','TEXT',1,0)])):
                if [(r[1],r[2],r[3],r[5]) for r in db.execute('PRAGMA table_info('+table+')')]!=columns:
                    raise ValueError('Import history schema changed')
            if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise ValueError('Invalid history database')
            yield db
            db.commit()
        finally:db.close()
        after=_stamp(path)
        if not write and after!=before:raise ValueError('History changed during read')
        if (after[0:2]!=before[0:2] or after[5:]!=before[5:]):raise ValueError('History identity changed')
        _close(nodes,[])
        if any(os.path.lexists(str(path)+suffix) for suffix in ('-journal','-wal','-shm')):
            raise ValueError('History has unresolved journal')


def _owner(processor):
    from mylar import native_writers,processing_guard
    if processor is not getattr(processing_guard._ACTIVE,'processor',None):
        raise ValueError('Owning processor required')
    writer=native_writers.owner()
    if not native_writers.active() or not writer.local[1].depth:
        raise ValueError('Owning raw Writer required')
    native_writers.admission(writer)
    return writer


def supported(processor):
    import mylar
    if not getattr(getattr(mylar,'native_writers',None),'publication_mode',lambda:False)():return False
    info=getattr(processor,'download_info',None)
    return getattr(processor,'_publication_handoff',None) is not None or (
        isinstance(info,dict) and info.get('provider')=='DDL')


def begin(processor,result,destination):
    if not supported(processor):return
    _owner(processor)
    if processor in _ATTEMPTS:raise ValueError('Import placement already attempted')
    if not isinstance(result,dict) or result['owner'] is None:
        raise ValueError('Import owner missing')
    import mylar
    if mylar.CONFIG.FILE_OPTS not in ('copy','move') or getattr(mylar.CONFIG,'CHGROUP',''):
        raise ValueError('Unsupported ordinary import file policy')
    mode=getattr(mylar.CONFIG,'CHMOD_FILE',None)
    if not isinstance(mode,str) or re.fullmatch('[0-7]{3,4}',mode) is None or int(mode,8)>0o777:
        raise ValueError('Unsupported ordinary import permissions')
    settings={'action':mylar.CONFIG.FILE_OPTS,'mode':int(mode,8),'uid':os.geteuid(),'gid':os.getegid()}
    destination=str(Path(destination).absolute())
    destination_nodes=_nodes(destination)
    source=result['path'];fact,nodes=_file(source)
    if fact['sha256']!=result['inventory']['source_sha256'] or fact['signature']!=list(result['inventory']['source_signature']):
        raise ValueError('Original import source changed')
    proof=getattr(processor,'_publication_handoff',None)
    delivery=None
    if proof is not None:
        if (proof['owner']!=result['owner'] or proof['payload']!=result['inventory']['payload']
                or not re.fullmatch('[a-f0-9]{64}',proof['token'])):
            raise ValueError('Original queued import mismatch')
        token=proof['token']
    else:
        from mylar import db
        info=processor.download_info
        if set(info)!={'provider','id'} or not re.fullmatch('[0-9]{1,20}(?:-[0-9]{1,8})?',str(info['id'])):
            raise ValueError('Unsupported DDL delivery')
        rows=db.DBConnection().select('SELECT id,issueid,comicid,status,pack FROM ddl_info WHERE id=?',[str(info['id'])])
        if len(rows)!=1:raise ValueError('DDL original missing')
        row=rows[0];owner=result['owner']
        if (str(row['issueid'])!=owner['issueid'] or str(row['comicid'])!=owner['parentcomicid']
                or row['status']!='Completed' or str(row['pack']).lower() not in ('0','false')):
            raise ValueError('DDL original delivery mismatch')
        delivery={'kind':'ddl','id':str(info['id']),'issueid':owner['issueid'],'comicid':owner['parentcomicid']}
        token=hashlib.sha256(_bytes({'delivery':delivery,'source':source,'original':fact})).hexdigest()
    attempt={'version':1,'token':token,'delivery':delivery,'proof':proof,'source':source,
             'original':fact,'destination':destination,'owner':result['owner'],
             'payload':result['inventory']['payload'],'settings':settings}
    encoded=_bytes(attempt).decode()
    if len(encoded.encode())>16384:raise ValueError('Import attempt exceeds bound')
    attempt=json.loads(encoded)
    with _database(write=True) as database:
        if database.execute('SELECT count(*) FROM completions').fetchone()[0]>=_LIMIT:
            raise ValueError('Import history full; retain delivery')
        if delivery is not None:
            for (prior,) in database.execute('SELECT attempt FROM completions'):
                if json.loads(prior)['delivery']==delivery:raise ValueError('DDL delivery already attempted')
        database.execute('INSERT INTO completions(token,attempt,ack) VALUES (?,?,NULL)',(token,encoded))
    _owner(processor)
    _close(nodes,[(source,fact['signature'])])
    _ATTEMPTS[processor]=(attempt,encoded,os.getpid(),threading.get_ident(),[],tuple(destination_nodes),tuple(nodes))
    _close(nodes,[(source,fact['signature'])])


def defer_cleanup(processor,method,*args,**kwargs):
    if not supported(processor):return method(*args,**kwargs)
    _owner(processor)
    value=_ATTEMPTS.get(processor)
    if value is None:raise ValueError('Import cleanup without original attempt')
    if getattr(method,'__self__',None) is not processor or getattr(method,'__name__',None)!='tidyup':
        raise ValueError('Unknown deferred cleanup')
    if len(value[4])>=2:raise ValueError('Import cleanup bound exceeded')
    value[4].append((method,args,kwargs))


def complete(processor,destination,*,issueid,comicid):
    if not supported(processor):return
    _owner(processor)
    value=_ATTEMPTS.get(processor)
    if value is None or value[2:4]!=(os.getpid(),threading.get_ident()):
        raise ValueError('Original import attempt missing')
    attempt,encoded,_,_,cleanup,destination_original_nodes,source_original_nodes=value
    if str(Path(destination).absolute())!=attempt['destination']:
        raise ValueError('Import destination mismatch')
    from mylar import publication_native as native
    if attempt['proof'] is not None and _bytes(processor._publication_handoff)!=_bytes(attempt['proof']):
        raise ValueError('Original coordinated import proof changed')
    current=native.require(destination,issueid=issueid,comicid=comicid)
    if current['owner']!=attempt['owner'] or current['inventory']['payload']!=attempt['payload']:
        raise ValueError('Import destination identity mismatch')
    catalog,catalog_nodes=_catalog(attempt['owner'],destination)
    fact,nodes=_file(destination)
    copied=_COPIES.get(processor)
    if copied is None:raise ValueError('Original exclusive copy missing')
    signature=fact['signature'];settings=attempt['settings']
    import mylar
    if (tuple(signature[:4])!=copied[:4] or fact['sha256']!=attempt['original']['sha256']
            or signature[5]&0o7777!=settings['mode'] or signature[6:9]!=[settings['uid'],settings['gid'],1]
            or mylar.CONFIG.FILE_OPTS!=settings['action'] or getattr(mylar.CONFIG,'CHGROUP','')
            or int(mylar.CONFIG.CHMOD_FILE,8)!=settings['mode']):
        raise ValueError('Original copy or configured output attributes changed')
    _close(nodes+catalog_nodes+list(destination_original_nodes)+list(source_original_nodes),[(destination,fact['signature']),*catalog,(attempt['source'],attempt['original']['signature'])])
    ack={'version':1,'destination':fact,'catalog':catalog,'owner':attempt['owner'],'payload':attempt['payload']}
    with _database(write=True) as database:
        if database.execute('UPDATE completions SET ack=? WHERE token=? AND attempt=? AND ack IS NULL',
                (_bytes(ack).decode(),attempt['token'],encoded)).rowcount!=1:
            raise ValueError('Import attempt completion already used')
    _owner(processor)
    _close(nodes+catalog_nodes+list(destination_original_nodes)+list(source_original_nodes),[(destination,fact['signature']),*catalog,(attempt['source'],attempt['original']['signature'])])
    # Completion is durable before source deletion. An uncertain write never replays.
    _ACKS[processor]=(destination,fact,nodes)
    _close(nodes+catalog_nodes+list(destination_original_nodes)+list(source_original_nodes),[(destination,fact['signature']),*catalog,(attempt['source'],attempt['original']['signature'])])
    for method,args,kwargs in cleanup:method(*args,**kwargs)
    _close(nodes,[(destination,fact['signature'])])
    del _ATTEMPTS[processor]


def _catalog(owner,destination):
    import mylar
    path=Path(mylar.DATA_DIR).absolute()/'mylar.db';fact,nodes=_file(path)
    sidecars=[str(path)+suffix for suffix in ('-journal','-wal','-shm')]
    if any(os.path.lexists(item) for item in sidecars):raise ValueError('Catalog recovery required')
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)) as database:
        matches=[]
        for table in ('issues','annuals'):
            matches.extend((table,*row) for row in database.execute(
                'SELECT IssueID,ComicID,Status,Location FROM '+table+' WHERE IssueID=?',(owner['issueid'],)))
        parents=database.execute('SELECT ComicLocation FROM comics WHERE ComicID=?',(owner['parentcomicid'],)).fetchall()
        if owner['table']=='annuals':
            releases=database.execute('SELECT ReleaseComicID FROM annuals WHERE IssueID=?',(owner['issueid'],)).fetchall()
            if releases!=[(owner['releasecomicid'],)]:raise ValueError('Annual release owner changed')
    expected=(owner['table'],owner['issueid'],owner['parentcomicid'],'Downloaded',Path(destination).name)
    if matches!=[expected] or len(parents)!=1 or str(Path(parents[0][0]).absolute()/Path(destination).name)!=destination:
        raise ValueError('Catalog success not bound to actual destination')
    if any(os.path.lexists(item) for item in sidecars):raise ValueError('Catalog changed')
    _close(nodes,[(str(path),fact['signature'])])
    return [(str(path),fact['signature'])],nodes


def _confirmed_original(*,token=None,delivery=None,owner=None,destination=None):
    try:
        import mylar
        history_path=Path(mylar.DATA_DIR).absolute()/_NAME
        catalog_path=Path(mylar.DATA_DIR).absolute()/'mylar.db'
        absent=tuple(str(path)+suffix for path in (history_path,catalog_path) for suffix in ('-journal','-wal','-shm'))
        if any(os.path.lexists(path) for path in absent):return False
        history_fact,history_nodes=_file(history_path)
        history_original=tuple(history_fact['signature']);history_hash=history_fact['sha256']
        with _database() as database:
            if database.execute('SELECT count(*) FROM completions').fetchone()[0]>_LIMIT:return False
            rows=database.execute('SELECT token,attempt,ack FROM completions WHERE ack IS NOT NULL').fetchall()
        matches=[]
        for key,raw,done in rows:
            if len(raw.encode())>16384 or len(done.encode())>16384:return False
            attempt=json.loads(raw);ack=json.loads(done)
            if (set(attempt)!={'version','token','delivery','proof','source','original','destination','owner','payload','settings'}
                    or type(attempt['version']) is not int or attempt['version']!=1 or attempt['token']!=key
                    or set(ack)!={'version','destination','catalog','owner','payload'}
                    or type(ack['version']) is not int or ack['version']!=1):return False
            if (token is not None and key!=token) or (delivery is not None and attempt['delivery']!=delivery):continue
            if attempt['owner']!=owner or attempt['destination']!=destination:continue
            matches.append((attempt,ack))
        if len(matches)!=1:return False
        attempt,ack=matches[0]
        catalog,catalog_nodes=_catalog(owner,destination)
        fact,nodes=_file(destination)
        if fact!=ack['destination'] or ack['owner']!=owner or ack['payload']!=attempt['payload']:return False
        if _file(history_path)[0]!={'signature':list(history_original),'sha256':history_hash}:return False
        files=[(destination,fact['signature']),*catalog,(str(history_path),history_original)]
        all_nodes=nodes+catalog_nodes+history_nodes
        _close(all_nodes,files)
        for path,expected in all_nodes:
            info=os.lstat(path)
            if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=expected:return False
        for path,expected in files:
            info=os.lstat(path)
            if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=tuple(expected):return False
        for path in absent:
            try:os.lstat(path)
            except FileNotFoundError:continue
            return False
        return True
    except Exception:return False  # Unknown evidence is never completion.


def _confirmed(*,token=None,delivery=None,owner=None,destination=None):
    if _confirmed_original(token=token,delivery=delivery,owner=owner,destination=destination):return True
    try:
        from mylar import ordinary_import_continuity
        if token is None:
            with _database() as db:
                if db.execute('SELECT count(*) FROM completions').fetchone()[0]>_LIMIT:return False
                rows=db.execute('SELECT token,attempt FROM completions WHERE ack IS NOT NULL').fetchall()
            keys=[key for key,raw in rows if json.loads(raw).get('delivery')==delivery and json.loads(raw).get('owner')==owner]
            if len(keys)!=1:return False
            token=keys[0]
        return ordinary_import_continuity.confirmed(token,owner,destination)
    except Exception:return False


def confirmed_ddl(delivery_id,owner,destination):
    delivery={'kind':'ddl','id':str(delivery_id),'issueid':owner['issueid'],'comicid':owner['parentcomicid']}
    return _confirmed(delivery=delivery,owner=owner,destination=destination)


def confirmed_token(token,owner,destination):
    return _confirmed(token=token,owner=owner,destination=destination)


def cleanup_ready(processor):
    _owner(processor)
    value=_ACKS.get(processor)
    if value is None:raise ValueError('Import cleanup requires durable completion')
    path,fact,nodes=value
    _close(nodes,[(path,fact['signature'])])


def forget(processor):
    try:
        _ATTEMPTS.pop(processor,None)
        _ACKS.pop(processor,None)
        _COPIES.pop(processor,None)
    except TypeError:
        pass  # Unbound legacy fixture processors have no private attempt.


def file_ops(processor,method,source,destination):
    if not supported(processor):return method(source,destination)
    import mylar
    _owner(processor)
    attempt=_ATTEMPTS.get(processor)
    if (attempt is None or str(Path(source).absolute())!=attempt[0]['source']
            or str(Path(destination).absolute())!=attempt[0]['destination']
            or mylar.CONFIG.FILE_OPTS not in ('copy','move')):
        raise ValueError('Unsupported ordinary import placement')
    original=attempt[0]['original'];nodes=list(attempt[5])+list(attempt[6])
    _close(nodes,[(source,original['signature'])])
    # Native move would destroy the only source before catalog success. Copy to
    # an exclusive destination instead; only durable completion can run tidyup.
    left=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
    right=None
    try:
        if tuple(_stamp(source))!=tuple(original['signature']):raise ValueError('Original source lost')
        right=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        source_fd=os.fstat(left)
        if (source_fd.st_dev,source_fd.st_ino,source_fd.st_size,source_fd.st_mtime_ns,source_fd.st_ctime_ns,source_fd.st_mode,source_fd.st_uid,source_fd.st_gid,source_fd.st_nlink)!=tuple(original['signature']):raise ValueError('Original source FD changed')
        created=os.fstat(right)
        created_identity=(created.st_dev,created.st_ino,created.st_mode,created.st_uid,created.st_gid,created.st_nlink)
        if created_identity[2]&0o7777!=0o600 or created_identity[3:]!=(os.geteuid(),os.getegid(),1):raise ValueError('Foreign created destination')
        digest=hashlib.sha256();count=0
        while chunk:=os.read(left,1024*1024):
            count+=len(chunk)
            if count>original['signature'][2]:raise ValueError('Import source grew')
            digest.update(chunk)
            view=memoryview(chunk)
            while view:
                written=os.write(right,view)
                if written<=0:raise OSError('Incomplete import placement')
                view=view[written:]
        os.fsync(right)
        if count!=original['signature'][2] or digest.hexdigest()!=original['sha256']:
            raise ValueError('Import source changed')
        current=os.fstat(right)
        original_right=(current.st_dev,current.st_ino,current.st_size,current.st_mtime_ns,current.st_ctime_ns,current.st_mode,current.st_uid,current.st_gid,current.st_nlink)
        if (current.st_dev,current.st_ino,current.st_mode,current.st_uid,current.st_gid,current.st_nlink)!=created_identity:raise ValueError('Original exclusive destination changed')
        copied,copied_nodes=_file(destination)
        current=os.fstat(right)
        if (current.st_dev,current.st_ino,current.st_size,current.st_mtime_ns,current.st_ctime_ns,current.st_mode,current.st_uid,current.st_gid,current.st_nlink)!=original_right or tuple(copied['signature'])!=original_right:raise ValueError('Copied pathname is not original destination FD')
        signature=copied['signature']
        if (copied['sha256']!=original['sha256'] or signature[5]&0o7777!=0o600
                or signature[6:9]!=[os.geteuid(),os.getegid(),1]):
            raise ValueError('Incomplete or foreign destination')
    finally:
        os.close(left)
        if right is not None:os.close(right)
    _COPIES[processor]=original_right
    _owner(processor)
    _close(nodes+copied_nodes,[(source,original['signature']),(destination,copied['signature'])])
    return True


def queue_guided(proof,binding):
    """Seal the already checked queue attempt's exact original guided binding."""
    import mylar
    from mylar import native_writers,workflow
    writer=native_writers.owner()
    if not native_writers.active() or not writer.local[1].depth:raise ValueError('Guided Writer missing')
    native_writers.admission(writer)
    keys={'id','source_token','version','issueid','comicid'}
    if not isinstance(binding,dict) or set(binding)!=keys:raise ValueError('Guided binding malformed')
    control,control_nodes=_file(Path(mylar.DATA_DIR)/'workflow.sqlite')
    from mylar import publication_native
    observed=publication_native.require(proof['source'],issueid=proof['owner']['issueid'],comicid=proof['owner']['parentcomicid'])
    if (observed['owner']!=proof['owner'] or observed['inventory']['source_sha256']!=proof['source_sha256']
            or publication_native.guard.canonical_digest(observed['inventory'])!=proof['inventory_sha256']):
        raise ValueError('Original guided stage changed')
    journal=workflow.store();row=journal.get('command',binding['id'])
    if (not row or row['phase']!='queued' or row.get('dispatched')
            or any(row.get(k)!=binding[k] for k in keys)
            or journal.get('worker_import_attempt',proof['token'])!=proof):
        raise ValueError('Original guided attempt missing')
    source,source_nodes=_file(proof['source'])
    if source['sha256']!=proof['source_sha256']:raise ValueError('Guided source changed')
    with _database(write=True) as database:
        if database.execute('SELECT count(*) FROM guided_links').fetchone()[0]>=_LIMIT:raise ValueError('Guided history full')
        database.execute('INSERT INTO guided_links VALUES (?,?)',(proof['token'],_bytes(binding).decode()))
    native_writers.admission(writer)
    _close(control_nodes+source_nodes,[(str(Path(mylar.DATA_DIR)/'workflow.sqlite'),control['signature']),
                                    (proof['source'],source['signature'])])


def confirmed_guided(command):
    try:
        import mylar
        from mylar import publication_native
        keys={'id','source_token','version','issueid','comicid'}
        binding={key:command[key] for key in keys}
        history_path=Path(mylar.DATA_DIR).absolute()/_NAME
        catalog_path=Path(mylar.DATA_DIR).absolute()/'mylar.db'
        absent=tuple(str(path)+suffix for path in (history_path,catalog_path) for suffix in ('-journal','-wal','-shm'))
        if any(os.path.lexists(path) for path in absent):return False
        history_fact,history_nodes=_file(history_path)
        history_original=tuple(history_fact['signature']);history_hash=history_fact['sha256']
        with _database() as database:
            rows=database.execute('SELECT token,binding FROM guided_links').fetchall()
        matches=[token for token,raw in rows if json.loads(raw)==binding]
        if len(matches)!=1:return False
        owner=publication_native.owner(mylar.DATA_DIR,binding['issueid'],binding['comicid'])
        if owner is None:return False
        path=Path(mylar.DATA_DIR)/'mylar.db';fact,nodes=_file(path)
        with closing(sqlite3.connect(path.absolute().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
            parent=db.execute('SELECT ComicLocation FROM comics WHERE ComicID=?',(owner['parentcomicid'],)).fetchall()
            location=db.execute('SELECT Location FROM '+owner['table']+' WHERE IssueID=?',(owner['issueid'],)).fetchall()
        if len(parent)!=1 or len(location)!=1 or not location[0][0]:return False
        destination=str(Path(parent[0][0]).absolute()/location[0][0])
        destination_fact,destination_nodes=_file(destination)
        result=_confirmed(token=matches[0],owner=owner,destination=destination)
        if _file(history_path)[0]!={'signature':list(history_original),'sha256':history_hash}:return False
        all_nodes=nodes+destination_nodes+history_nodes
        files=[(str(path),fact['signature']),(destination,destination_fact['signature']),(str(history_path),history_original)]
        _close(all_nodes,files)
        for current,expected in all_nodes:
            info=os.lstat(current)
            if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=expected:return False
        for current,expected in files:
            info=os.lstat(current)
            if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=tuple(expected):return False
        for current in absent:
            try:os.lstat(current)
            except FileNotFoundError:continue
            return False
        return result
    except Exception:return False  # Unknown evidence is never completion.


def confirmed_retained(controller,writer,request,original_ack):
    """Distinct fresh recovery fact; never infer or write an ordinary completion."""
    from mylar import publication_retained_delivery
    return publication_retained_delivery.verify_ack(controller,writer,request,original_ack)
