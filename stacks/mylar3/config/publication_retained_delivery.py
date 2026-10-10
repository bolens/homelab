"""Disabled finite retained-pack acceptance; never historical ordinary placement.

Only a fresh exact Controller/Writer factory can create the live owner. Saved
records are observations. Target/source archives and Wanted intent remain intact.
"""
from contextlib import closing
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
import weakref
import zipfile

from mylar import publication_archive_owned as o

ENABLED = False
NAME = 'retained-delivery-v1'
KIND = 'retained-ddl-existing-target-v1'
FIELDS = {'version','kind','ddl_id','pack_id','member_id','source_generation',
          'source_sha256','target_sha256','owner','review_sha256'}
_CORES = weakref.WeakKeyDictionary()
_EVENTS = {}  # Only actual successful accept publishes; never JSON hydration.
PENDING_NAMES = ('normalizer-v1.pending','tagger-v2.pending','release-v1.pending',
                 'tagger-publication-v1.json','nested-derivative-v1.json','tagger-recovery-v1.pending',
                 'negative-retirement-v1.pending','negative-retirement-v1.terminal-pending',
                 'archive-repair-v1.pending','archive-repair-v1.terminal-pending')
MAX_FILE = 256 * 1024**2  # Conservative bounded offline archive; larger members remain review.
MAX_TREE = 32 * 1024**3


def request(value):
    o.check(type(value) is dict and set(value)==FIELDS and type(value['version']) is int
            and value['version']==1 and value['kind']==KIND,'retained-request')
    o.check(type(value['ddl_id']) is str and re.fullmatch(r'[0-9]{1,20}(?:-[0-9]{1,8})?',value['ddl_id']),
            'retained-ddl-key')
    for key in ('pack_id','member_id','source_generation','source_sha256','target_sha256','review_sha256'):
        o.check(type(value[key]) is str and re.fullmatch('[0-9a-f]{64}',value[key]),'retained-digest')
    o.check(len(o.compact(value))<4096,'retained-request-bound')
    return copy.deepcopy(value)


def _writer_binding(writer):
    return (writer.root,writer.lock,writer.pending,writer.tagger_pending,writer.release_pending,
            tuple(writer.lock_identity),tuple(writer.root_identity),writer.local)


def _controller_binding(controller):
    return (controller.root,controller.database,controller.native_database,controller.writer_root,
            tuple(controller.roots),controller.tool_root)


def _owning_event(controller,writer,value,token):
    event=_EVENTS.get((str(controller.root),token))
    o.check(event is not None and event[0]==os.getpid() and event[1]==o.digest(value),
            'retained-original-owning-event-required')
    o.check(_writer_binding(writer)==event[7] and _controller_binding(controller)==event[8],
            'retained-original-event-bindings')
    return event


def _nodes(paths):
    return {str(p):tuple(v) for p,v in o.ancestors(list(map(Path,paths))).items()}


def _join_nodes(original,new):
    for path,value in new.items():
        value=tuple(value)
        if path in original and original[path]!=value:raise o.Held('retained-original-node-conflict')
        original[path]=value


def _file(path,deadline,maximum=MAX_FILE):
    fact=o.fact(Path(path),maximum,deadline)
    stamp=tuple(fact['signature9'])
    o.check(stamp[5]&0o170000==0o100000 and stamp[8]==1,'retained-exclusive-file')
    return stamp,fact['sha256']


def _raw(files,nodes,absent,namespaces,claims=None):
    for path,names in namespaces.items():
        if tuple(sorted(os.listdir(path)))!=names:raise o.Held('retained-original-census')
    for path,expected in nodes.items():
        info=os.lstat(path)
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=expected:
            raise o.Held('retained-original-node')
    for path,expected in files.items():
        info=os.lstat(path)
        if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,
                info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=expected:
            raise o.Held('retained-original-file')
    for path in absent:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise o.Held('retained-original-absence')

    for path,expected in (claims or {}).items():
        try:s=os.lstat(path)
        except FileNotFoundError:
            if expected is not None:raise o.Held('retained-original-claim')
            continue
        actual=(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,
                None if s.st_mode&0o170000==0o040000 else s.st_nlink)
        if actual!=expected:raise o.Held('retained-original-claim')


def _sql(path,stamp):
    """Bounded complete native schema and typed rows, not just the selected owner."""
    with o.checked_stream(Path(path),list(stamp)) as stream, closing(sqlite3.connect(
            'file:/proc/self/fd/'+str(stream.fileno())+'?mode=ro&immutable=1',uri=True)) as db:
        o.check(db.execute('PRAGMA quick_check').fetchall()==[('ok',)],'retained-catalog-integrity')
        schema=db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()
        o.check(len(schema)<=128,'retained-schema-bound')
        rows={};count=0;size=0
        for kind,name,_,_ in schema:
            if kind!='table':continue
            o.check(re.fullmatch('[a-zA-Z_][a-zA-Z0-9_]*',name),'retained-sql-name')
            values=[]
            for row in db.execute('SELECT * FROM "'+name+'"'):
                converted=[{'blob':v.hex()} if type(v) is bytes else v for v in row]
                encoded=o.compact(converted);count+=1;size+=len(encoded)
                o.check(count<=100000 and size<=64*1024**2,'retained-sql-bound')
                values.append(encoded.decode())
            rows[name]=sorted(values)
        return {'schema':schema,'rows':rows}


def _tree(source,deadline):
    pending=[Path(source)];files={};hashes={};nodes={};namespaces={};size=0
    while pending:
        current=pending.pop();s=os.lstat(current)
        o.check(time.monotonic()<deadline and len(files)+len(namespaces)<4001,'retained-tree-bound')
        if s.st_mode&0o170000==0o040000:
            names=tuple(sorted(os.listdir(current)));namespaces[str(current)]=names
            _join_nodes(nodes,_nodes([current]));pending.extend(current/name for name in names)
        else:
            stamp,digest=_file(current,deadline,MAX_FILE);files[str(current)]=stamp;hashes[str(current)]=digest
            size+=stamp[2];o.check(size<=MAX_TREE,'retained-tree-bytes')
            _join_nodes(nodes,_nodes([current]))
    _raw(files,nodes,(),namespaces)
    return files,hashes,nodes,namespaces


def _write(path,raw,nodes,*,created_field=False):
    o.check(len(raw)<=MAX_FILE,'retained-output-bound')
    with o.directory_fd(path.parent,list(nodes[str(path.parent)])) as parent:
        fd=os.open(path.name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
        try:
            s=os.fstat(fd);created=(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_nlink)
            o.check(created[2]&0o170000==0o100000 and created[2]&0o7777==0o600
                    and created[3:]==(os.geteuid(),os.getegid(),1),'retained-created-FD')
            if created_field:
                value=json.loads(raw);o.check(type(value) is dict and 'created_fd_identity6' not in value,'retained-output-identity-owner')
                raw=o.compact(dict(value,created_fd_identity6=list(created)))
            view=memoryview(raw)
            while view:
                count=os.write(fd,view);o.check(count>0,'retained-short-write');view=view[count:]
            os.fsync(fd);os.lseek(fd,0,0)
            digest=hashlib.sha256();remaining=len(raw)
            while remaining:
                block=os.read(fd,min(remaining,1024*1024));o.check(block,'retained-readback')
                digest.update(block);remaining-=len(block)
            o.check(not os.read(fd,1) and digest.hexdigest()==hashlib.sha256(raw).hexdigest(),'retained-intended-bytes')
            s=os.fstat(fd);stamp=tuple(o.stat9(s))
            o.check((stamp[0],stamp[1],*stamp[5:])==created and tuple(o.stat9(os.stat(path.name,dir_fd=parent,follow_symlinks=False)))==stamp,
                    'retained-created-identity')
            os.fsync(parent)
        finally:os.close(fd)
    # No replacement helper can refresh the identity just captured from the FD.
    s=os.lstat(path)
    if (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink)!=stamp:
        raise o.Held('retained-output-final')
    return stamp,hashlib.sha256(raw).hexdigest()


def _member(source,files,hashes,member_id,source_sha,deadline):
    """Native derives the worker member key from retained original bytes."""
    matches=[]
    if source.is_dir():
        for path,digest in hashes.items():
            relative=Path(path).relative_to(source)
            key=hashlib.sha256(os.fsencode(Path('extracted')/relative)+b'\0'+digest.encode()).hexdigest()
            if key==member_id:
                o.check(digest==source_sha,'retained-member-sha')
                matches.append((Path(path),None))
    else:
        key=hashlib.sha256(os.fsencode(Path('extracted')/source.name)+b'\0'+hashes[str(source)].encode()).hexdigest()
        if key==member_id:
            o.check(hashes[str(source)]==source_sha,'retained-member-sha');matches.append((source,None))
        else:
            # Finite ZIP nested members only; other outer formats remain review.
            o.check(source.suffix.lower() in ('.zip','.cbz'),'retained-outer-format')
            with o.checked_stream(source,list(files[str(source)])) as stream, zipfile.ZipFile(stream) as archive:
                entries=archive.infolist();total=0;seen=set()
                o.check(len(entries)<=2000,'retained-outer-bound')
                for entry in entries:
                    p=Path(entry.filename)
                    o.check(not p.is_absolute() and '..' not in p.parts and entry.filename not in seen
                            and not entry.flag_bits&1 and (entry.external_attr>>16)&0o170000 not in (0o120000,),
                            'retained-outer-member')
                    seen.add(entry.filename);total+=entry.file_size
                    o.check(total<=MAX_TREE and entry.file_size<=MAX_FILE,'retained-outer-bytes')
                    if entry.is_dir():continue
                    digestor=hashlib.sha256()
                    with archive.open(entry) as incoming:
                        while block:=incoming.read(1024*1024):
                            o.check(time.monotonic()<deadline,'retained-outer-deadline');digestor.update(block)
                    digest=digestor.hexdigest()
                    key=hashlib.sha256(os.fsencode(Path('extracted')/p)+b'\0'+digest.encode()).hexdigest()
                    if key==member_id:
                        o.check(digest==source_sha,'retained-member-sha');matches.append((p,archive.read(entry)))
    o.check(len(matches)==1,'retained-unique-member')
    return matches[0]


class RetainedDeliveryAcceptance:
    __slots__=('__weakref__',)
    def __init__(self):raise o.Held('retained-owning-factory-required')

    def accept(self):
        core=_CORES.get(self)
        o.check(type(self) is RetainedDeliveryAcceptance and core is not None
                and core['thread']==threading.get_ident() and core['pid']==os.getpid() and core['phase']=='prepared','retained-live-owner')
        controller=core['controller'];writer=core['writer']
        writer_binding=core['writer_binding'];controller_binding=core['controller_binding']
        o.writer_pair(controller,writer,core['modules'])
        originals=copy.deepcopy(_vectors(core))
        _validate(core)
        o.check(_vectors(core)==originals,'retained-helper-baseline-replacement')
        # Enter uncertain BEFORE the owning catalog transaction. Never replay it.
        core['phase']='uncertain'
        before=core['files'][str(controller.native_database)]
        with closing(sqlite3.connect(controller.native_database)) as db:
            db.execute('PRAGMA trusted_schema=OFF');db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
            _raw(core['files'],core['nodes'],core['absent'],core['namespaces'],core['claims'])
            owner=core['request']['owner'];row=core['catalog_row']
            selected=db.execute('SELECT * FROM '+owner['table']+' WHERE IssueID=?',(owner['issueid'],)).fetchall()
            o.check(selected==[row],'retained-catalog-CAS')
            columns=[r[1] for r in db.execute('PRAGMA table_info('+owner['table']+')')]
            location=row[columns.index('Location')];status=row[columns.index('Status')]
            changed=db.execute('UPDATE '+owner['table']+' SET Location=?, Status=? WHERE IssueID=? AND ComicID=? AND Location IS ? AND Status IS ?',
                (location,status,owner['issueid'],owner['parentcomicid'],location,status)).rowcount
            o.check(changed==1,'retained-fresh-catalog-event');db.commit()
        now=tuple(o.signature(controller.native_database))
        o.check(now[:2]==before[:2] and now[5:]==before[5:] and _sql(controller.native_database,now)==core['sql'],
                'retained-complete-catalog-preserved')
        core['files'][str(controller.native_database)]=now  # Sole exact owned SQL transition, semantic equality proved.
        raw_catalog=o.read_checked(controller.native_database,list(now),256*1024**2,core['deadline'])
        core['hashes'][str(controller.native_database)]=hashlib.sha256(raw_catalog).hexdigest()
        _validate(core)
        body={'version':1,'kind':'fresh-retained-delivery-acceptance','token':core['token'],
              'request':core['request'],'source':core['source'],'target':core['target'],
              'target_preservation':core['preservation'],'target_inventory':core['target_inventory'],
              'source_inventory':core['source_inventory'],'catalog_before_sha256':core['catalog_before_sha256'],
              'fresh_catalog_event':True,'historical_import_ack':False,
              'original_vectors':_vectors(core),'mutation_authority':False,'publication_acceptance':False,
              'reader_index_acceptance':False,'automatic_replay':False}
        raw=o.compact(body);stamp,digest=_write(core['folder']/'accepted.json',raw,core['nodes'])
        core['files'][str(core['folder']/'accepted.json')]=stamp
        core['hashes'][str(core['folder']/'accepted.json')]=digest
        core['namespaces'][str(core['folder'])]=tuple(sorted((*core['namespaces'][str(core['folder'])],'accepted.json')))
        issued={'version':1,'kind':'retained-delivery-issued-reference','token':core['token'],
                'request_sha256':o.digest(core['request']),
                'ack':{'path':str(core['folder']/'accepted.json'),'sha256':digest,'signature9':list(stamp)},
                'intent':{'path':str(core['folder']/'intent.json'),
                          'sha256':core['hashes'][str(core['folder']/'intent.json')],
                          'signature9':list(core['files'][str(core['folder']/'intent.json')])}}
        issued_stamp,issued_digest=_write(core['folder']/'issued.json',o.compact(issued),core['nodes'],created_field=True)
        core['files'][str(core['folder']/'issued.json')]=issued_stamp
        core['hashes'][str(core['folder']/'issued.json')]=issued_digest
        core['namespaces'][str(core['folder'])]=tuple(sorted((*core['namespaces'][str(core['folder'])],'issued.json')))
        result={'version':1,'outcome':'fresh-retained-delivery-accepted','token':core['token'],
                'ack':{'path':str(core['folder']/'accepted.json'),'sha256':digest,'signature9':list(stamp)},
                'historical_import_ack':False,'ordinary_import_grant':False,'mutation_authority':False,
                'publication_acceptance':False,'reader_index_acceptance':False,'automatic_replay':False}
        originals=copy.deepcopy(_vectors(core))
        event=(os.getpid(),issued['request_sha256'],
               (str(core['folder']/'accepted.json'),digest,stamp),
               (str(core['folder']/'intent.json'),issued['intent']['sha256'],tuple(issued['intent']['signature9'])),
               (str(core['folder']/'issued.json'),issued_digest,issued_stamp),
               o.compact(originals),core['token'],
               writer_binding,controller_binding)
        # Copy originals BEFORE all final helpers; they cannot replace the baseline.
        _validate(core)
        o.check(_vectors(core)==originals,'retained-helper-baseline-replacement')
        # Every helper runs before these complete copied primitive closures.
        files=tuple(core['files'].items());nodes=tuple(core['nodes'].items());absent=tuple(core['absent']);namespaces=tuple(core['namespaces'].items())
        for path,names in namespaces:
            if tuple(sorted(os.listdir(path)))!=names:raise o.Held('retained-ACK-census')
        for path,expected in nodes:
            s=os.lstat(path)
            if (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid)!=expected:raise o.Held('retained-ACK-node')
        for path,expected in files:
            s=os.lstat(path)
            if (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink)!=expected:raise o.Held('retained-ACK-file')
        for path in absent:
            try:os.lstat(path)
            except FileNotFoundError:continue
            raise o.Held('retained-ACK-absence')
        for path,expected in tuple(core['claims'].items()):
            try:s=os.lstat(path)
            except FileNotFoundError:
                if expected is not None:raise o.Held('retained-final-claim')
                continue
            actual=(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,
                    None if s.st_mode&0o170000==0o040000 else s.st_nlink)
            if actual!=expected:raise o.Held('retained-final-claim')
        if (writer.root,writer.lock,writer.pending,writer.tagger_pending,writer.release_pending,
                tuple(writer.lock_identity),tuple(writer.root_identity),writer.local)!=writer_binding:
            raise o.Held('retained-final-Writer-binding')
        if (controller.root,controller.database,controller.native_database,controller.writer_root,
                tuple(controller.roots),controller.tool_root)!=controller_binding:
            raise o.Held('retained-final-controller-binding')
        if getattr(writer.local[1],'depth',0)<=0 or any(getattr(writer.local[1],k,False) for k in
                ('allow_pending','allow_tagger_pending','allow_release_pending')):
            raise o.Held('retained-final-Writer-purpose')
        _EVENTS[(str(controller.root),core['token'])]=event
        core['phase']='accepted'
        return result


def _vectors(core):
    return {'files9':list(core['files'].items()),'nodes5':list(core['nodes'].items()),
            'absent':list(core['absent']),'namespaces':list(core['namespaces'].items()),
            'claims':list(core['claims'].items())}


def _validate(core):
    o.check(time.monotonic()<core['deadline'],'retained-deadline')
    for path,digest in core['hashes'].items():
        actual=hashlib.sha256()
        with o.checked_stream(Path(path),list(core['files'][path])) as stream:
            while block:=stream.read(1024*1024):
                o.check(time.monotonic()<core['deadline'],'retained-deadline');actual.update(block)
        o.check(actual.hexdigest()==digest,'retained-original-bytes')
    g=core['modules'][2];controller=core['controller'];writer=core['writer']
    o.writer_pair(controller,writer,core['modules'])
    o.check(g.media_snapshot(controller.database,writer.root/'publication-v1.json')[0]==core['census'],'retained-current-census')
    decision=controller._check({'owner':core['request']['owner'],'payload':core['source_inventory']['payload']},writer)
    o.check(decision['decision'] in ('allowed','unknown'),'retained-owner-rejected')
    _raw(core['files'],core['nodes'],core['absent'],core['namespaces'],core['claims'])


def prepare_existing(controller,writer,value):
    """Only this exact live factory admits unchanged current-target acceptance."""
    o.check(ENABLED,'retained-default-disabled')
    modules=o.sdk();roots,_=o.writer_pair(controller,writer,modules);g=modules[2]
    value=request(value);owner=g.exact_owner(value['owner']);value['owner']=owner
    import mylar
    from mylar import workflow_store,pack_intake
    cache=o.canonical(mylar.CONFIG.DDL_LOCATION)
    o.check(cache!=controller.root and not any(cache.is_relative_to(p) or p.is_relative_to(cache) for p in roots),
            'retained-cache-library-separated')
    deadline=time.monotonic()+120
    controls=[controller.database,controller.native_database,writer.lock,writer.root/'publication-v1.json']
    files={};hashes={};nodes=_nodes(controls);absent=[]
    for path in controls:
        stamp,digest=_file(path,deadline,256*1024**2);files[str(path)]=stamp;hashes[str(path)]=digest
    for path in (controller.database,controller.native_database):
        absent.extend(str(path)+s for s in ('-journal','-wal','-shm'))
    absent.extend(str(writer.root/name) for name in PENDING_NAMES)
    writer_binding=_writer_binding(writer);controller_binding=_controller_binding(controller)
    writer_names=tuple(sorted(os.listdir(writer.root)))
    _raw(files,nodes,absent,{str(writer.root):writer_names})
    store=workflow_store.Store(controller.root,existing_only=True)
    capture=store.get('pack',value['pack_id'])
    o.check(type(capture) is dict and capture.get('id')==value['pack_id']
            and capture.get('ddl_id')==value['ddl_id'] and capture.get('source_generation')==value['source_generation']
            and not capture.get('cleanup_started') and not capture.get('cleanup_complete'),'retained-capture')
    source=Path(capture['source']);o.check(source.is_relative_to(cache),'retained-configured-source')
    with closing(sqlite3.connect(controller.native_database.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        db.row_factory=sqlite3.Row
        rows=db.execute('SELECT * FROM ddl_info WHERE id=?',(value['ddl_id'],)).fetchall()
        o.check(len(rows)==1,'retained-original-DDL')
        row=dict(rows[0]);o.check(row['status']=='Completed' and pack_intake.is_pack(row['pack'])
            and str(row['comicid'])==owner['parentcomicid'] and Path(row['filename']).name==source.name,
            'retained-delivery-join')
        catalog_row=db.execute('SELECT * FROM '+owner['table']+' WHERE IssueID=?',(owner['issueid'],)).fetchall()
        o.check(len(catalog_row)==1,'retained-unique-catalog-owner');catalog_row=tuple(catalog_row[0])
    sql=_sql(controller.native_database,files[str(controller.native_database)])
    tree_files,tree_hashes,tree_nodes,namespaces=_tree(source,deadline)
    files.update(tree_files);hashes.update(tree_hashes);_join_nodes(nodes,tree_nodes)
    o.check(str(writer.root) not in namespaces,'retained-Writer-source-separated')
    namespaces[str(writer.root)]=writer_names
    o.check(pack_intake.source_state(source,content=True)==value['source_generation']
            and capture.get('source_stamp')==pack_intake.source_state(source),'retained-original-generation')
    member,data=_member(source,tree_files,tree_hashes,value['member_id'],value['source_sha256'],deadline)
    catalog,claims,more=o.catalog(controller,owner,g,deadline);_join_nodes(nodes,{str(p):tuple(v) for p,v in more.items()})
    target=Path(catalog['owner']['path']);target_stamp,target_hash=_file(target,deadline)
    o.check(target_hash==value['target_sha256'] and target_stamp[:2] not in [v[:2] for v in tree_files.values()],
            'retained-reviewed-independent-target')
    files[str(target)]=target_stamp;hashes[str(target)]=target_hash;_join_nodes(nodes,_nodes([target]))
    # Global fixed owner prevents a different request digest bypassing uncertainty.
    token=hashlib.sha256((value['ddl_id']+'\0'+value['pack_id']+'\0'+value['member_id']).encode()).hexdigest()
    journal=controller.root/NAME
    if not os.path.lexists(journal):os.mkdir(journal,0o700)
    info=os.lstat(journal)
    journal_original=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)
    o.check(info.st_mode&0o170000==0o040000 and info.st_mode&0o7777==0o700
            and (info.st_uid,info.st_gid)==(os.geteuid(),os.getegid()),'retained-private-journal')
    journal_names=tuple(sorted(os.listdir(journal)))
    o.check(len(journal_names)<4096 and all(re.fullmatch('[0-9a-f]{64}',name) for name in journal_names),'retained-history-bound')
    folder=journal/token;os.mkdir(folder,0o700)  # Existing/uncertain means HOLD, never rerun.
    info=os.lstat(folder)
    folder_original=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)
    # Actual mkdir identities precede every ancestry/output helper.
    _join_nodes(nodes,{str(journal):journal_original,str(folder):folder_original})
    o.check(info.st_mode&0o170000==0o040000 and info.st_mode&0o7777==0o700
            and (info.st_uid,info.st_gid)==(os.geteuid(),os.getegid()),'retained-created-private-folder')
    _join_nodes(nodes,_nodes([folder]));namespaces[str(folder)]=()
    namespaces[str(journal)]=tuple(sorted((*journal_names,token)))
    if data is not None:
        selected=folder/('source'+member.suffix.lower());stamp,digest=_write(selected,data,nodes)
        files[str(selected)]=stamp;hashes[str(selected)]=digest
    else:selected=member
    source_inventory=g.inventory(selected,tool_root=controller.tool_root,deadline=deadline)
    target_inventory=g.inventory(target,tool_root=controller.tool_root,deadline=deadline)
    o.check(source_inventory['payload']==target_inventory['payload'] and source_inventory['pages']==target_inventory['pages'],
            'retained-original-pages-payload')
    decision=controller._check({'owner':owner,'payload':source_inventory['payload']},writer)
    o.check(decision['decision'] in ('allowed','unknown'),'retained-owner-rejected')
    original=o.read_checked(target,list(target_stamp),MAX_FILE,deadline)
    preservation={}
    for name in ('target-preserved'+target.suffix.lower(),'target-restored'+target.suffix.lower()):
        path=folder/name;stamp,digest=_write(path,original,nodes)
        o.check(stamp[:2]!=target_stamp[:2] and stamp[:2] not in [v[:2] for v in files.values()],
                'retained-independent-preservation')
        files[str(path)]=stamp;hashes[str(path)]=digest
        o.check(digest==target_hash and {k:v for k,v in g.inventory(path,tool_root=controller.tool_root,deadline=deadline).items() if k in ('version','members','pages','payload')}=={k:v for k,v in target_inventory.items() if k in ('version','members','pages','payload')},
                'retained-restore-inventory')
        preservation[name]={'path':str(path),'signature9':list(stamp),'sha256':digest}
    census,_=g.media_snapshot(controller.database,writer.root/'publication-v1.json')
    core={'controller':controller,'writer':writer,'modules':modules,'thread':threading.get_ident(),'pid':os.getpid(),
          'phase':'prepared','request':value,'token':token,'folder':folder,'source':str(selected),'target':str(target),
          'files':files,'hashes':hashes,'nodes':nodes,'absent':tuple(absent),'namespaces':namespaces,
          'source_inventory':source_inventory,'target_inventory':target_inventory,'preservation':preservation,
          'catalog_before_sha256':hashes[str(controller.native_database)],'catalog_row':catalog_row,
          'sql':sql,'census':census,'deadline':deadline,'writer_binding':writer_binding,'controller_binding':controller_binding,'claims':{str(p):None if v is None else tuple(v) for p,v in claims.items()}}
    intent={'version':1,'kind':KIND,'request':value,'token':token,'ddl_row_sha256':o.digest(row),
            'source':str(selected),'target':str(target),'original_vectors':_vectors(core),
            'historical_import_ack':False,'automatic_replay':False}
    stamp,digest=_write(folder/'intent.json',o.compact(intent),nodes)
    files[str(folder/'intent.json')]=stamp;hashes[str(folder/'intent.json')]=digest
    namespaces[str(folder)]=tuple(sorted(Path(p).name for p in files if Path(p).parent==folder))
    originals=copy.deepcopy(_vectors(core))
    _validate(core)
    o.check(_vectors(core)==originals,'retained-helper-baseline-replacement')
    obj=RetainedDeliveryAcceptance.__new__(RetainedDeliveryAcceptance);_CORES[obj]=core
    # Final kernel-only original closure after registry publication/last helper.
    for path,names in tuple(namespaces.items()):
        if tuple(sorted(os.listdir(path)))!=names:raise o.Held('retained-factory-census')
    for path,expected in tuple(nodes.items()):
        s=os.lstat(path)
        if (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid)!=expected:raise o.Held('retained-factory-node')
    for path,expected in tuple(files.items()):
        s=os.lstat(path)
        if (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink)!=expected:raise o.Held('retained-factory-file')
    for path in absent:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise o.Held('retained-factory-absence')
    for path,expected in tuple(core['claims'].items()):
        try:s=os.lstat(path)
        except FileNotFoundError:
            if expected is not None:raise o.Held('retained-final-claim')
            continue
        actual=(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,
                None if s.st_mode&0o170000==0o040000 else s.st_nlink)
        if actual!=expected:raise o.Held('retained-final-claim')
    if (writer.root,writer.lock,writer.pending,writer.tagger_pending,writer.release_pending,
            tuple(writer.lock_identity),tuple(writer.root_identity),writer.local)!=writer_binding:
        raise o.Held('retained-factory-Writer-binding')
    if (controller.root,controller.database,controller.native_database,controller.writer_root,
            tuple(controller.roots),controller.tool_root)!=controller_binding:
        raise o.Held('retained-factory-controller-binding')
    if getattr(writer.local[1],'depth',0)<=0 or any(getattr(writer.local[1],k,False) for k in
            ('allow_pending','allow_tagger_pending','allow_release_pending')):
        raise o.Held('retained-factory-Writer-purpose')
    return obj


def verify_ack(controller,writer,value,reference):
    """Fresh factual read of an ORIGINAL emitted ACK ref; never recreate a cap."""
    # Caller may supply an original reference, never a pathname/baseline grant.
    value=request(value)
    token=hashlib.sha256((value['ddl_id']+'\0'+value['pack_id']+'\0'+value['member_id']).encode()).hexdigest()
    event=_owning_event(controller,writer,value,token)
    path=Path(controller.root)/NAME/token/'accepted.json'
    o.check(type(reference) is dict and set(reference)=={'path','sha256','signature9'}
            and reference['path']==str(path) and type(reference['signature9']) in (tuple,list)
            and len(reference['signature9'])==9 and all(type(n) is int for n in reference['signature9'])
            and type(reference['sha256']) is str and re.fullmatch('[0-9a-f]{64}',reference['sha256']),
            'retained-original-ACK-ref')
    expected=tuple(reference['signature9']);digest=reference['sha256']
    o.check((str(path),digest,expected)==event[2],'retained-original-event-ACK')
    modules=o.sdk();o.writer_pair(controller,writer,modules);g=modules[2];deadline=time.monotonic()+120
    raw=o.read_checked(path,list(expected),16*1024**2,deadline)
    o.check(hashlib.sha256(raw).hexdigest()==digest and expected[5]&0o7777==0o600
            and expected[6:]==(os.geteuid(),os.getegid(),1),'retained-original-ACK-bytes')
    def pairs(items):
        result={}
        for key,item in items:o.check(key not in result,'retained-duplicate-ACK-key');result[key]=item
        return result
    body=json.loads(raw,object_pairs_hook=pairs)
    o.check(type(body) is dict and set(body)=={'version','kind','token','request','source','target',
            'target_preservation','target_inventory','source_inventory','catalog_before_sha256',
            'fresh_catalog_event','historical_import_ack','original_vectors','mutation_authority',
            'publication_acceptance','reader_index_acceptance','automatic_replay'}
            and type(body['version']) is int and body['version']==1
            and body['kind']=='fresh-retained-delivery-acceptance' and body['token']==token
            and body['request']==value and body['fresh_catalog_event'] is True
            and all(body[k] is False for k in ('historical_import_ack','mutation_authority','publication_acceptance',
                                              'reader_index_acceptance','automatic_replay')),'retained-ACK-contract')
    vectors=body['original_vectors']
    # Producer event retains final vectors independently from this saved record.
    o.check(type(vectors) is dict and set(vectors)=={'files9','nodes5','absent','namespaces','claims'}
            and all(type(v) is list and len(v)<=8192 for v in vectors.values()),'retained-ACK-vectors')
    o.check(all(len({p for p,_ in vectors[key]})==len(vectors[key]) for key in ('files9','nodes5','namespaces','claims'))
            and len(set(vectors['absent']))==len(vectors['absent']),'retained-duplicate-vector')
    files={p:tuple(v) for p,v in vectors['files9']};nodes={p:tuple(v) for p,v in vectors['nodes5']}
    namespaces={p:tuple(v) for p,v in vectors['namespaces']};claims={p:None if v is None else tuple(v) for p,v in vectors['claims']}
    absent=tuple(vectors['absent'])
    o.check(all(type(p) is str and Path(p).is_absolute() and '..' not in Path(p).parts for p in (*files,*nodes,*namespaces,*claims,*absent))
            and all(len(v)==9 and all(type(n) is int for n in v) for v in files.values())
            and all(len(v)==5 and all(type(n) is int for n in v) for v in nodes.values())
            and all(v is None or len(v)==6 and all(type(n) is int or i==5 and n is None for i,n in enumerate(v)) for v in claims.values()),
            'retained-ACK-vector-types')
    o.check(str(controller.database) in files and str(controller.native_database) in files
            and str(writer.lock) in files and str(writer.root/'publication-v1.json') in files
            and body['source'] in files and body['target'] in files,'retained-ACK-owning-controls')
    folder=str(path.parent)
    o.check(folder in namespaces and 'accepted.json' not in namespaces[folder],'retained-owned-ACK-transition')
    namespaces[folder]=tuple(sorted((*namespaces[folder],'accepted.json','issued.json')));files[str(path)]=expected
    issued=path.parent/'issued.json';issued_stamp=tuple(o.signature(issued))
    issued_raw=o.read_checked(issued,list(issued_stamp),16384,deadline)
    issuance=json.loads(issued_raw,object_pairs_hook=pairs)
    o.check(type(issuance) is dict and set(issuance)=={'version','kind','token','request_sha256','ack','intent','created_fd_identity6'}
            and type(issuance['version']) is int and issuance['version']==1
            and issuance['kind']=='retained-delivery-issued-reference' and issuance['token']==token
            and issuance['request_sha256']==o.digest(value) and issuance['ack']==reference
            and tuple(issuance['created_fd_identity6'])==(issued_stamp[0],issued_stamp[1],*issued_stamp[5:])
            and issued_stamp[5]&0o170000==0o100000 and issued_stamp[5]&0o7777==0o600
            and issued_stamp[6:]==(os.geteuid(),os.getegid(),1),'retained-original-issued-reference')
    o.check((str(issued),hashlib.sha256(issued_raw).hexdigest(),issued_stamp)==event[4]
            and (issuance['intent']['path'],issuance['intent']['sha256'],tuple(issuance['intent']['signature9']))==event[3],
            'retained-original-event-issuance')
    files[str(issued)]=issued_stamp
    o.check(o.compact({'files9':list(files.items()),'nodes5':list(nodes.items()),'absent':list(absent),
             'namespaces':list(namespaces.items()),'claims':list(claims.items())})==event[5],
            'retained-original-event-vectors')
    _raw(files,nodes,absent,namespaces,claims)
    catalog,_,_=o.catalog(controller,value['owner'],g,deadline)
    o.check(catalog['owner']['path']==body['target'],'retained-current-exact-target')
    source=g.inventory(Path(body['source']),tool_root=controller.tool_root,deadline=deadline)
    target=g.inventory(Path(body['target']),tool_root=controller.tool_root,deadline=deadline)
    o.check(source==body['source_inventory'] and target==body['target_inventory']
            and source['payload']==target['payload'],'retained-ACK-current-original-inventories')
    for name,ref in body['target_preservation'].items():
        o.check(name in ('target-preserved'+Path(body['target']).suffix.lower(),'target-restored'+Path(body['target']).suffix.lower())
                and ref['path']==str(path.parent/name) and tuple(ref['signature9'])==files[ref['path']],
                'retained-ACK-independent-preservation')
        raw_copy=o.read_checked(Path(ref['path']),list(files[ref['path']]),MAX_FILE,deadline)
        o.check(hashlib.sha256(raw_copy).hexdigest()==value['target_sha256']==ref['sha256'],'retained-ACK-restored-bytes')
    o.check(len(body['target_preservation'])==2,'retained-ACK-complete-preservation')
    decision=controller._check({'owner':value['owner'],'payload':source['payload']},writer)
    o.check(decision['decision'] in ('allowed','unknown'),'retained-ACK-owner-rejected')
    result={'version':1,'outcome':'fresh-retained-delivery-accepted','token':token,'historical_import_ack':False,
            'ordinary_import_grant':False,'mutation_authority':False,'publication_acceptance':False,
            'reader_index_acceptance':False,'automatic_replay':False}
    _raw(files,nodes,absent,namespaces,claims)
    # No helper or deserialization follows the last copied original closure.
    for current,names in tuple(namespaces.items()):
        if tuple(sorted(os.listdir(current)))!=names:raise o.Held('retained-passive-census')
    for current,stamp in tuple(nodes.items()):
        s=os.lstat(current)
        if (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid)!=stamp:raise o.Held('retained-passive-node')
    for current,stamp in tuple(files.items()):
        s=os.lstat(current)
        if (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink)!=stamp:raise o.Held('retained-passive-file')
    for current,stamp in tuple(claims.items()):
        try:s=os.lstat(current)
        except FileNotFoundError:
            if stamp is not None:raise o.Held('retained-passive-claim')
            continue
        actual=(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,None if s.st_mode&0o170000==0o040000 else s.st_nlink)
        if actual!=stamp:raise o.Held('retained-passive-claim')
    for current in absent:
        try:os.lstat(current)
        except FileNotFoundError:continue
        raise o.Held('retained-passive-absence')
    if (writer.root,writer.lock,writer.pending,writer.tagger_pending,writer.release_pending,
            tuple(writer.lock_identity),tuple(writer.root_identity),writer.local)!=event[7]:
        raise o.Held('retained-passive-Writer-binding')
    if (controller.root,controller.database,controller.native_database,controller.writer_root,
            tuple(controller.roots),controller.tool_root)!=event[8]:
        raise o.Held('retained-passive-controller-binding')
    if getattr(writer.local[1],'depth',0)<=0 or any(getattr(writer.local[1],k,False) for k in
            ('allow_pending','allow_tagger_pending','allow_release_pending')):
        raise o.Held('retained-passive-Writer-purpose')
    return result


def status_existing(controller,writer,value):
    """Lost reply reconciliation reads the producer-issued original ACK reference.

    Missing/partial issuance remains uncertain. It never retries catalog acceptance.
    """
    value=request(value)
    token=hashlib.sha256((value['ddl_id']+'\0'+value['pack_id']+'\0'+value['member_id']).encode()).hexdigest()
    event=_owning_event(controller,writer,value,token)
    path=Path(controller.root)/NAME/token/'issued.json'
    try:
        expected=tuple(o.signature(path))
    except FileNotFoundError:
        return {'version':1,'token':token,'outcome':'retained-delivery-uncertain',
                'historical_import_ack':False,'ordinary_import_grant':False,'automatic_replay':False}
    o.check((str(path),event[4][1],expected)==event[4],'retained-status-original-issued')
    nodes=_nodes([path])
    raw=o.read_checked(path,list(expected),16384,time.monotonic()+120)
    o.check(hashlib.sha256(raw).hexdigest()==event[4][1],'retained-status-original-issued-bytes')
    value_sha=o.digest(value)
    record=json.loads(raw)
    o.check(type(record) is dict and set(record)=={'version','kind','token','request_sha256','ack','intent','created_fd_identity6'}
            and type(record['version']) is int and record['version']==1
            and record['kind']=='retained-delivery-issued-reference' and record['token']==token
            and record['request_sha256']==value_sha and tuple(record['created_fd_identity6'])==(expected[0],expected[1],*expected[5:])
            and expected[5]&0o170000==0o100000 and expected[5]&0o7777==0o600
            and expected[6:]==(os.geteuid(),os.getegid(),1),'retained-original-issued-reference')
    intent=record['intent'];intent_path=path.parent/'intent.json'
    o.check(type(intent) is dict and set(intent)=={'path','sha256','signature9'} and intent['path']==str(intent_path),
            'retained-issued-intent')
    original=o.read_checked(intent_path,intent['signature9'],16*1024**2,time.monotonic()+120)
    o.check(hashlib.sha256(original).hexdigest()==intent['sha256'],'retained-issued-original-intent')
    # Copy the producer's ORIGINAL accepted evidence before the verifier callback.
    # Its returned status is not an authority to recapture current vectors.
    ack=record['ack'];ack_path=path.parent/'accepted.json'
    o.check(type(ack) is dict and set(ack)=={'path','sha256','signature9'} and ack['path']==str(ack_path),
            'retained-issued-ACK')
    ack_raw=o.read_checked(ack_path,ack['signature9'],16*1024**2,time.monotonic()+120)
    o.check(hashlib.sha256(ack_raw).hexdigest()==ack['sha256'],'retained-issued-original-ACK')
    body=json.loads(ack_raw);vectors=body['original_vectors']
    o.check(type(vectors) is dict and set(vectors)=={'files9','nodes5','absent','namespaces','claims'}
            and all(type(v) is list and len(v)<=8192 for v in vectors.values()),'retained-issued-vectors')
    o.check(all(len({p for p,_ in vectors[key]})==len(vectors[key]) for key in ('files9','nodes5','namespaces','claims'))
            and len(set(vectors['absent']))==len(vectors['absent']),'retained-issued-duplicate-vector')
    files={p:tuple(v) for p,v in vectors['files9']}
    original_nodes={p:tuple(v) for p,v in vectors['nodes5']}
    namespaces={p:tuple(v) for p,v in vectors['namespaces']}
    claims={p:None if v is None else tuple(v) for p,v in vectors['claims']}
    absent=tuple(vectors['absent'])
    o.check(all(type(p) is str and Path(p).is_absolute() and '..' not in Path(p).parts
                for p in (*files,*original_nodes,*namespaces,*claims,*absent))
            and all(len(v)==9 and all(type(n) is int for n in v) for v in files.values())
            and all(len(v)==5 and all(type(n) is int for n in v) for v in original_nodes.values())
            and all(v is None or len(v)==6 and all(type(n) is int or i==5 and n is None for i,n in enumerate(v)) for v in claims.values()),
            'retained-issued-vector-types')
    for current,stamp in ((str(path),expected),(str(intent_path),tuple(intent['signature9'])),
                          (str(ack_path),tuple(ack['signature9']))):
        if current in files and files[current]!=stamp:raise o.Held('retained-issued-original-conflict')
        files[current]=stamp
    _join_nodes(original_nodes,nodes)
    folder=str(path.parent)
    o.check(folder in namespaces and 'accepted.json' not in namespaces[folder]
            and 'issued.json' not in namespaces[folder],'retained-issued-own-transition')
    namespaces[folder]=tuple(sorted((*namespaces[folder],'accepted.json','issued.json')))
    # These primitive copies survive the final verification/helper boundary.
    files=tuple(files.items());original_nodes=tuple(original_nodes.items())
    namespaces=tuple(namespaces.items());claims=tuple(claims.items())
    result=verify_ack(controller,writer,value,record['ack'])
    for current,names in namespaces:
        if tuple(sorted(os.listdir(current)))!=names:raise o.Held('retained-issued-final-census')
    for current,stamp in original_nodes:
        info=os.lstat(current)
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=stamp:raise o.Held('retained-issued-final-node')
    for current,stamp in files:
        info=os.lstat(current)
        if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,
                info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=stamp:raise o.Held('retained-issued-final-file')
    for current,stamp in claims:
        try:info=os.lstat(current)
        except FileNotFoundError:
            if stamp is not None:raise o.Held('retained-issued-final-claim')
            continue
        actual=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,
                None if info.st_mode&0o170000==0o040000 else info.st_nlink)
        if actual!=stamp:raise o.Held('retained-issued-final-claim')
    for current in absent:
        try:os.lstat(current)
        except FileNotFoundError:continue
        raise o.Held('retained-issued-final-absence')
    # Original issuance controls survive the final verifier and its callbacks.
    for current,stamp in ((str(path),expected),(str(intent_path),tuple(intent['signature9']))):
        info=os.lstat(current)
        if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,
                info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=stamp:raise o.Held('retained-issued-final-file')
    for current,stamp in nodes.items():
        info=os.lstat(current)
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=stamp:raise o.Held('retained-issued-final-node')
    if (writer.root,writer.lock,writer.pending,writer.tagger_pending,writer.release_pending,
            tuple(writer.lock_identity),tuple(writer.root_identity),writer.local)!=event[7]:
        raise o.Held('retained-passive-Writer-binding')
    if (controller.root,controller.database,controller.native_database,controller.writer_root,
            tuple(controller.roots),controller.tool_root)!=event[8]:
        raise o.Held('retained-passive-controller-binding')
    if getattr(writer.local[1],'depth',0)<=0 or any(getattr(writer.local[1],k,False) for k in
            ('allow_pending','allow_tagger_pending','allow_release_pending')):
        raise o.Held('retained-passive-Writer-purpose')
    return result


def _begin_finalization(cap):
    """Finite owning handoff; only actual acceptance, never saved receipts."""
    o.check(type(cap) is RetainedDeliveryAcceptance,'retained-finalize-live-type')
    core=_CORES.get(cap)
    o.check(type(cap) is RetainedDeliveryAcceptance and core is not None
            and core['phase']=='accepted' and core['thread']==threading.get_ident()
            and core['pid']==os.getpid(),'retained-finalize-live-owner')
    event=_owning_event(core['controller'],core['writer'],core['request'],core['token'])
    # The immutable producer bytes, rather than mutable registry DTOs, own facts.
    o.check(o.compact(_vectors(core))==event[5],'retained-finalize-original-event')
    core['phase']='finalization-uncertain'  # Before any backend helper/commit.
    return {'controller':core['controller'],'writer':core['writer'],'modules':core['modules'],
            'request':copy.deepcopy(core['request']),'token':core['token'],'event':event,
            'vectors':json.loads(event[5]),'hashes':dict(core['hashes']),
            'deadline':core['deadline'],'core':core}
