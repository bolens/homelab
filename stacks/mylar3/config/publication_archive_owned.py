"""Owned lossless ZIP PREPARE proposal. No API, adoption, or mutation grant.

The only exceptional inventory belongs to the current catalog owner's one
malformed original. Other matched owners retain ordinary SDK observation.
"""
from contextlib import closing,contextmanager
import copy
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import threading
import time
import weakref

class Held(ValueError):pass

def check(value,reason):
    if not value:raise Held(reason)

def compact(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(value):return hashlib.sha256(compact(value)).hexdigest()
def signature(path):
    s=os.lstat(path)
    return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]
def canonical(path):
    p=Path(path)
    check(p.is_absolute() and '..' not in p.parts and p.resolve(strict=True)==p,'canonical')
    return p
def ancestors(paths):
    result={}
    for path in paths:
        admitted=canonical(path)
        directories=(admitted,*admitted.parents) if admitted.is_dir() else admitted.parents
        for p in directories:
            s=signature(p);v=[s[i] for i in (0,1,5,6,7)]
            check(stat.S_ISDIR(s[5]) and (p not in result or result.get(p)==v),'ancestor')
            result[p]=v
    return result

def merge_nodes(current,new):
    for p,v in new.items():
        check(p not in current or current[p]==v,'shared-ancestor')
        current[p]=v


def stat9(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]
def stat5(s):return [s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid]

@contextmanager
def directory_fd(path,expected=None):
    p=canonical(path);nodes=ancestors([p]);fds=[]
    try:
        fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);fds.append(fd)
        check(stat5(os.fstat(fd))==nodes[Path('/')],'directory-fd')
        current=Path('/')
        for component in p.parts[1:]:
            current=current/component
            fd=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);fds.append(fd)
            check(stat5(os.fstat(fd))==nodes[current],'directory-fd')
        if expected is not None:check(stat5(os.fstat(fd))==expected,'owned-directory-fd')
        yield fd
        for node,value in nodes.items():check(stat5(os.lstat(node))==value,'directory-path-CAS')
    finally:
        for fd in reversed(fds):os.close(fd)

@contextmanager
def checked_stream(path,expected):
    p=canonical(path);check(signature(p)==expected,'read-path-CAS')
    with directory_fd(p.parent) as parent:
        fd=os.open(p.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
        with os.fdopen(fd,'rb') as stream:
            check(stat9(os.fstat(stream.fileno()))==expected,'read-fd-CAS')
            yield stream
            check(stat9(os.fstat(stream.fileno()))==expected and signature(p)==expected,'read-final-CAS')

def attributes(path):
    p=canonical(path);before=signature(p)
    with checked_stream(p,before) as stream:
        names=sorted(os.listxattr(stream.fileno()))
        check(len(names)<=64 and sum(len(os.fsencode(n)) for n in names)<=65536,'xattr-name-bound')
        values={};budget=2
        for name in names:
            value=os.getxattr(stream.fileno(),name)
            # Linux xattr values are limited by the kernel; enforce our smaller
            # aggregate before adding hexadecimal values to the retained map.
            check(len(value)<=65536,'xattr-value-bound')
            budget+=len(compact(name))+2*len(value)+4
            check(budget<=1024**2,'xattr-bound');values[name]=value.hex()
    return dict(mode=before[5],uid=before[6],gid=before[7],mtime_ns=before[3],xattrs=values)

def read_checked(path,expected,maximum,deadline):
    check(0<expected[2]<=maximum,'file-bound');chunks=[];count=0
    with checked_stream(path,expected) as stream:
        while block:=stream.read(1024**2):
            count+=len(block);check(count<=maximum and time.monotonic()<deadline,'read-bound');chunks.append(block)
    check(count==expected[2],'read-size');return b''.join(chunks)

def fact(path,maximum,deadline):
    p=canonical(path);before=signature(p)
    check(stat.S_ISREG(before[5]) and before[8]==1 and 0<before[2]<=maximum,'file-bound')
    h=hashlib.sha256();count=0
    with checked_stream(p,before) as stream:
        while block:=stream.read(1024**2):
            count+=len(block);check(count<=maximum and time.monotonic()<deadline,'deadline');h.update(block)
    check(count==before[2],'file-size')
    return dict(path=str(p),signature9=before,sha256=h.hexdigest())

def sdk():
    names=('publication_api','media_writer','publication_guard','publication_derivative',
           'publication_archive_repair','publication_archive_derivative','publication_archive_layout')
    modules=[importlib.import_module('mylar.'+name) for name in names]
    for module,name in zip(modules,names):
        check(Path(module.__file__)==Path('/app/mylar3/mylar')/(name+'.py')
              and Path(module.__file__).resolve()==Path(module.__file__),'installed-sdk-required')
    return modules

def writer_pair(controller,writer,modules):
    api,writers,g=modules[:3]
    g.ordinary_purpose(writer)
    check(type(controller) is api.Controller and type(writer) is writers.Writer,'exact-sdk-types')
    root=canonical(controller.root)
    check(controller.database==root/'workflow.sqlite' and controller.native_database==root/'mylar.db'
          and controller.writer_root==root/'media-writer' and writer.root==controller.writer_root
          and controller.tool_root==g.TOOL_ROOT,'configured-sdk-paths')
    check(type(controller.roots) in (list,tuple) and 1<=len(controller.roots)<=8,'configured-roots')
    roots=[canonical(p) for p in controller.roots];check(len(set(roots))==len(roots),'duplicate-roots')
    check(getattr(writer.local[1],'depth',0)>0 and not any(getattr(writer.local[1],k,False)
          for k in ('allow_pending','allow_tagger_pending','allow_release_pending')),'held-ordinary-writer')
    fresh=writers.Writer(writer.root,create=False)
    check(fresh.local is writer.local and writer.lock==writer.root/'writer-v1.lock'
          and writer.pending==writer.root/'normalizer-v1.pending'
          and writer.tagger_pending==writer.root/'tagger-v2.pending'
          and writer.release_pending==writer.root/'release-v1.pending','writer-registry')
    check(not any(os.path.lexists(writer.root/name) for name in ('normalizer-v1.pending',
          'tagger-v2.pending','release-v1.pending','tagger-publication-v1.json',
          'nested-derivative-v1.json','tagger-recovery-v1.pending')),'pending-media')
    return roots,g.writer_identity(writer)

def catalog(controller,owner,g,deadline):
    """Complete unfiltered native projection; no exceptional SQL filtering."""
    dbpath=canonical(controller.native_database);nodes=ancestors([dbpath,*map(Path,controller.roots)])
    before=fact(dbpath,256*1024**2,deadline)
    check(before['signature9'][6]==os.geteuid(),'catalog-owner')
    companions=[Path(str(dbpath)+s) for s in ('-wal','-shm','-journal')]
    check(not any(os.path.lexists(p) for p in companions),'catalog-companion')
    with checked_stream(dbpath,before['signature9']) as stream:header=stream.read(100)
    check(header[:16]==b'SQLite format 3\0' and header[18:20]==b'\x01\x01','catalog-journal-mode')
    rows={};count=size=0
    with checked_stream(dbpath,before['signature9']) as database_stream, closing(sqlite3.connect(
            'file:/proc/self/fd/'+str(database_stream.fileno())+'?mode=ro&immutable=1',uri=True)) as db:
        db.execute('PRAGMA query_only=ON');db.execute('PRAGMA trusted_schema=OFF')
        db.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000);db.execute('BEGIN')
        check(db.execute('PRAGMA quick_check').fetchall()==[('ok',)],'catalog-integrity')
        for table,fields in (('comics',('ComicID','ComicLocation')),
            ('issues',('IssueID','ComicID','Location','Status')),
            ('annuals',('IssueID','ComicID','ReleaseComicID','Location','Status','Deleted'))):
            check(db.execute('SELECT type FROM sqlite_master WHERE name=?',(table,)).fetchall()==[('table',)],'catalog-schema')
            rows[table]=[]
            for values in db.execute('SELECT '+','.join(fields)+' FROM '+table):
                count+=1;size+=sum(len(str(v).encode()) for v in values if v is not None)
                check(count<=g.CATALOG_ROWS and size<=g.CATALOG_BYTES and time.monotonic()<deadline,'catalog-bound')
                row=dict(zip(fields,values));check(all(v is None or type(v) is str for k,v in row.items() if k!='Deleted')
                    and (table!='annuals' or row['Deleted'] is None or type(row['Deleted']) is int),'catalog-types')
                rows[table].append(row)
        db.rollback()
    parents={}
    for row in rows['comics']:parents.setdefault(row['ComicID'],[]).append(row)
    issues=[(t,row) for t in ('issues','annuals') for row in rows[t]];claims={};physical={};identities={};identity_bytes=0
    for table,row in issues:
        if row['Location'] is None or row['Location']=='':continue
        folders=parents.get(row['ComicID'],[]);check(len(folders)==1,'catalog-parent')
        path=g._catalog_path(folders[0]['ComicLocation'],row['Location'],list(map(Path,controller.roots)))
        for p in (path,*path.parents):
            check(len(identities)<g.CATALOG_PATHS or p in identities,'claim-bound')
            if p not in identities:
                identity_bytes+=len(os.fsencode(p));check(identity_bytes<=g.CATALOG_BYTES,'claim-byte-bound')
                identities[p]=g._claim_identity(p)
        claims.setdefault(path,[]).append((table,row))
        if identities[path] is not None:physical.setdefault(identities[path][:2],[]).append((table,row))
    matched=[(t,r) for t,r in issues if r['IssueID']==owner['issueid']]
    check(len(matched)==1 and matched[0][0]==owner['table'],'sole-issue-owner');table,row=matched[0]
    folders=parents.get(owner['parentcomicid'],[])
    check(row['ComicID']==owner['parentcomicid'] and len(folders)==1
          and (table!='annuals' or row['ReleaseComicID']==owner['releasecomicid']),'owner-parent-release')
    path=g._catalog_path(folders[0]['ComicLocation'],row['Location'],list(map(Path,controller.roots)))
    identity=identities.get(path)
    check(identity is not None and len(claims.get(path,[]))==1 and len(physical.get(identity[:2],[]))==1,'sole-physical-owner')
    binding=dict(version=1,comic_location=folders[0]['ComicLocation'],location=row['Location'],path=str(path),status=row['Status'],deleted=row.get('Deleted'))
    g.catalog_fact(binding,owner)
    check(fact(dbpath,256*1024**2,deadline)==before and not any(os.path.lexists(p) for p in companions),'catalog-CAS')
    for p,v in identities.items():check(g._claim_identity(p)==v,'catalog-claim-CAS')
    for p,v in nodes.items():check([signature(p)[i] for i in (0,1,5,6,7)]==v,'catalog-ancestor-CAS')
    return dict(file=before,projection_sha256=digest(rows),owner=binding),identities,nodes

def policy(controller,writer,owner,inventory,records,modules,deadline):
    g,lineage=modules[2:4];payload=inventory['payload']
    if any(r['version']==2 for r in records.values()):
        matches=list(lineage.matches(records,payload).values());index,_=lineage.families(records)
    else:matches=[r for r in records.values() if r['inventory']['payload']==payload];index={}
    allowed={g.canonical_digest(o):o for r in matches for o in r['allowed']}
    rejected={g.canonical_digest(o) for r in matches for o in r['rejected']};key=g.canonical_digest(owner)
    check(not matches or key in allowed and key not in rejected,'rejected-or-unreviewed-owner')
    check(len(allowed)<=8,'matched-owner-bound');observed=[]
    for key2,other in sorted(allowed.items()):
        if key2==key:continue
        proof=g.observe_owners(controller.native_database,writer,[other],controller.roots,tool_root=controller.tool_root)
        current=proof['inventory']['payload']
        check((index.get(current)==index.get(payload) and index.get(payload) is not None) if index else current==payload,'other-owner-payload')
        observed+=proof['observed'];check(time.monotonic()<deadline,'owner-observation-deadline')
    return dict(decision='allowed' if matches else 'unknown',matched=sorted(g.attestation(r) for r in matches),other_observed=observed)

def historical_claims(owner,sourcefact,records,claims,g):
    for record in records.values():
        for item in record['observed']:
            p=Path(item['catalog']['path'])
            for q in (p,*p.parents):
                value=g._claim_identity(q)
                check(q not in claims or claims[q]==value,'registered-claim-drift');claims[q]=value
            if p.exists() and g._claim_identity(p)[:2]==tuple(sourcefact['signature9'][:2]):
                check(item['owner']==owner,'other-registered-original')

def witness(raw,source,plan,modules,deadline):
    g=modules[2];derivative,layout=modules[5:7]
    headers,envelope=layout.layout(io.BytesIO(raw),len(raw));entry=plan['entry']
    inv,metadata=derivative.independent(raw,g,deadline,entry['index'])
    return dict(version=1,kind='one-zip-directory-header-virtual-inventory',source=source,entry=entry,
        zip_envelope=envelope,all_members_crc_verified=True,proposed_directory_name=entry['name']+'/',
        virtual_original_inventory=inv,root_metadata_sha256=metadata,
        raw_header_commitments=[dict(**row,crc_verified=True,uncompressed_sha256=member['sha256'],
            virtual_directory=member['directory'],header_change_declared=row['index']==entry['index'])
            for row,member in zip(headers,inv['members'])],ordinary_source_admission=False,native_grant=False,
        mutation_authority=False,publication_acceptance=False,derivative_written=False,
        derivative_equivalence_verified=False,purpose_integration_verified=False)

def write(path,raw,parent_identity):
    with directory_fd(path.parent,parent_identity) as parent:
        info=os.fstat(parent)
        check(stat.S_IMODE(info.st_mode)==0o700 and info.st_uid==os.geteuid(),'private-write-parent')
        fd=os.open(path.name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
        with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.fsync(parent)

def preserve(source,target,sourcefact,sourceattrs,deadline,parent_identity):
    with checked_stream(source,sourcefact['signature9']) as inp,directory_fd(target.parent,parent_identity) as parent:
        info=os.fstat(parent);check(stat.S_IMODE(info.st_mode)==0o700 and info.st_uid==os.geteuid(),'private-copy-parent')
        fd=os.open(target.name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
        with os.fdopen(fd,'w+b') as out:
            while block:=inp.read(1024**2):
                check(time.monotonic()<deadline,'custody-deadline');out.write(block)
            out.flush();os.fsync(out.fileno());out.seek(0)
            check(hashlib.sha256(out.read()).hexdigest()==sourcefact['sha256'],'custody-fd-readback')
            os.fchmod(out.fileno(),stat.S_IMODE(sourceattrs['mode']))
            check(os.fstat(out.fileno()).st_uid==sourceattrs['uid'] and os.fstat(out.fileno()).st_gid==sourceattrs['gid'],'custody-ownership')
            os.utime(out.fileno(),ns=(os.fstat(out.fileno()).st_atime_ns,sourceattrs['mtime_ns']))
            for name,value in sourceattrs['xattrs'].items():os.setxattr(out.fileno(),name,bytes.fromhex(value))
            os.fsync(out.fileno());created=stat9(os.fstat(out.fileno()))
        os.fsync(parent);check(signature(target)==created,'custody-path-CAS')
    check(attributes(target)==sourceattrs and fact(target,512*1024**2,deadline)['sha256']==sourcefact['sha256'],'custody-readback')

_KEY=object()
_SEALS=weakref.WeakKeyDictionary()
class RepairPreparation:
    __slots__=('_key','_controller','_writer','_modules','_thread','_local','_identity','_projection',
        '_files','_attrs','_nodes','_claims','_census','_records','_binding','_seal','_deadline','_names','_operation','_directory','_objects','__weakref__')
    def __init__(self,key,controller,writer,modules,files,attrs,nodes,claims,census,records,binding,deadline,operation,directory):
        check(key is _KEY,'owning-factory');self._key=key;self._controller=controller;self._writer=writer;self._modules=modules
        self._thread=threading.get_ident();self._local=writer.local;self._identity=modules[2].writer_identity(writer)
        self._projection=projection(controller);self._files=files;self._attrs=attrs;self._nodes=nodes;self._claims=claims
        self._census=census;self._records=records;self._binding=binding;self._deadline=deadline;self._operation=operation
        self._names={'intent.json','original.arc','restored-original.arc','prepared.cbz','preparation.json'}
        self._directory=directory;self._objects=[id(controller),id(writer),id(modules),id(writer.local),self._thread,*map(id,modules)]
        self._seal=self._core();_SEALS[self]=self._seal;self.close_passive()
    def _core(self):return digest(dict(binding=self._binding,files={str(p):v for p,v in self._files.items()},
        attrs={str(p):v for p,v in self._attrs.items()},nodes={str(p):v for p,v in self._nodes.items()},
        claims={str(p):v for p,v in self._claims.items()},census=self._census,records=self._records,
        projection=self._projection,identity=self._identity,names=sorted(self._names),deadline=self._deadline,
        directory=self._directory,objects=self._objects))
    @property
    def binding(self):self.close_passive();return copy.deepcopy(self._binding)
    def close_passive(self):
        check(self._key is _KEY and self._core()==self._seal==_SEALS.get(self) and threading.get_ident()==self._thread
              and time.monotonic()<self._deadline and self._writer.local is self._local
              and getattr(self._local[1],'depth',0)>0 and projection(self._controller)==self._projection
              and [id(self._controller),id(self._writer),id(self._modules),id(self._writer.local),self._thread,*map(id,self._modules)]==self._objects,'preparation-lifetime')
        check(set(os.listdir(self._operation))==self._names,'operation-census')
        for db in (self._controller.database,self._controller.native_database):
            check(not any(os.path.lexists(str(db)+s) for s in ('-wal','-shm','-journal')),'companion')
        for p,v in self._claims.items():check(self._modules[2]._claim_identity(p)==v,'claim-CAS')
        for p,v in self._attrs.items():check(attributes(p)==v,'attribute-CAS')
        check(writer_pair(self._controller,self._writer,self._modules)[1]==self._identity,'terminal-writer')
        self._modules[2].ordinary_purpose(self._writer)
        # Every replaceable SDK/hash/xattr/census callback precedes direct closure.
        for p,v in self._claims.items():
            try:s=os.lstat(p)
            except FileNotFoundError:check(v is None,'missing-claim');continue
            check((s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,None if stat.S_ISDIR(s.st_mode) else s.st_nlink)==v,'terminal-claim')
        for db in (self._controller.database,self._controller.native_database):
            for suffix in ('-wal','-shm','-journal'):
                try:os.lstat(str(db)+suffix)
                except FileNotFoundError:continue
                raise Held('terminal-companion')
        for name in ('negative-retirement-v1.pending','normalizer-v1.pending','tagger-v2.pending','release-v1.pending',
                     'tagger-publication-v1.json','nested-derivative-v1.json','tagger-recovery-v1.pending'):
            try:os.lstat(self._writer.root/name)
            except FileNotFoundError:continue
            raise Held('terminal-pending')
        s=os.lstat(self._operation)
        check([s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]==self._directory,'terminal-operation-incarnation')
        for p,f in self._files.items():
            s=os.lstat(p)
            check([s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]==f['signature9'],'terminal-file')
        for p,v in self._nodes.items():
            s=os.lstat(p);check([s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid]==v,'terminal-ancestor')
    def revalidate(self):
        self.close_passive();g=self._modules[2]
        roots,identity=writer_pair(self._controller,self._writer,self._modules)
        check(identity==self._identity and roots==list(map(Path,self._controller.roots)),'writer-identity')
        census,records=g.media_snapshot(self._controller.database,self._writer.root/'publication-v1.json')
        check(census==self._census and records==self._records,'current-authority')
        check(fact(self._controller.native_database,256*1024**2,self._deadline)==self._files[self._controller.native_database],'current-catalog')
        for p,f in self._files.items():check(fact(p,max(f['signature9'][2],1),self._deadline)==f,'readback-CAS')
        self.close_passive();return self.binding
    def adopt(self):
        self.revalidate();raise Held('owned-repair-adoption-and-reader-consumer-not-installed')

def projection(c):return [str(c.root),str(c.database),str(c.native_database),str(c.writer_root),list(map(str,c.roots)),str(c.tool_root)]

def prepare_existing(controller,writer,owner,operation_id):
    implementation=canonical(Path(__file__));initial_nodes=ancestors([implementation])
    preliminary_deadline=time.monotonic()+180
    implementation_fact=fact(implementation,1024**2,preliminary_deadline)
    modules=sdk();g=modules[2];roots,identity=writer_pair(controller,writer,modules)
    check(type(operation_id) is str and re.fullmatch('[0-9a-f]{64}',operation_id),'operation-id')
    owner=g.exact_owner(owner);deadline=time.monotonic()+g.TIMEOUT
    control=[implementation,controller.database,controller.native_database,writer.lock,writer.root/'publication-v1.json']
    nodes=initial_nodes;merge_nodes(nodes,ancestors([controller.root,writer.root,*roots,*control]))
    files={p:fact(p,256*1024**2,deadline) for p in control}
    check(files[implementation]==implementation_fact,'implementation-before-sdk')
    census,records=g.media_snapshot(controller.database,writer.root/'publication-v1.json')
    observed,claims,cnodes=catalog(controller,owner,g,deadline);merge_nodes(nodes,cnodes);source=Path(observed['owner']['path'])
    merge_nodes(nodes,ancestors([source]));sourcefact=fact(source,512*1024**2,deadline);sourceattrs=attributes(source)
    check(sourcefact['signature9'][6]==os.geteuid(),'source-custody-owner')
    raw=read_checked(source,sourcefact['signature9'],512*1024**2,deadline);check(hashlib.sha256(raw).hexdigest()==sourcefact['sha256'] and signature(source)==sourcefact['signature9'],'source-bytes')
    plan=modules[4].classify(raw,g,deadline);check(plan['status']=='repair-candidate','supported-defect-only')
    w=witness(raw,sourcefact,plan,modules,deadline);repaired,evidence=modules[5].derive(raw,w,g,deadline)
    policyproof=policy(controller,writer,owner,plan['inventory'],records,modules,deadline)
    # Immutable registered originals cannot borrow another owner's exception.
    historical_claims(owner,sourcefact,records,claims,g)
    op=controller.root/('archive-repair-'+operation_id)
    check(not os.path.lexists(op) and not any(op.is_relative_to(r) or r.is_relative_to(op) for r in roots),'private-stage-scope')
    # Refresh every owning source/control fact before exclusive private creation.
    check(fact(source,512*1024**2,deadline)==sourcefact and attributes(source)==sourceattrs,'source-before-stage')
    check(catalog(controller,owner,g,deadline)[0]==observed,'catalog-before-stage')
    check(g.media_snapshot(controller.database,writer.root/'publication-v1.json')==(census,records),'authority-before-stage')
    for p in control:check(fact(p,256*1024**2,deadline)==files[p],'control-before-stage')
    files[source]=sourcefact
    for item in policyproof['other_observed']:
        p=Path(item['catalog']['path']);files[p]=dict(path=str(p),signature9=item['signature'],sha256=item['source_sha256']);merge_nodes(nodes,ancestors([p]))
    with directory_fd(controller.root,nodes[controller.root]) as root_fd:
        os.mkdir(op.name,mode=0o700,dir_fd=root_fd);os.fsync(root_fd)
    merge_nodes(nodes,ancestors([op]));opidentity=signature(op)
    parent_identity=[opidentity[i] for i in (0,1,5,6,7)]
    check(stat.S_ISDIR(opidentity[5]) and stat.S_IMODE(opidentity[5])==0o700 and opidentity[6]==os.geteuid(),'private-operation-directory')
    fd=os.open(op.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
    intent=compact(dict(version=1,kind='owned-archive-repair-prepare-intent',source=sourcefact,
        owner=owner,census=census,operation_id=operation_id,executable=False,mutation_authority=False))
    write(op/'intent.json',intent,parent_identity);files[op/'intent.json']=fact(op/'intent.json',1024**2,deadline)
    check(files[op/'intent.json']['sha256']==hashlib.sha256(intent).hexdigest(),'intended-intent')
    preserve(source,op/'original.arc',sourcefact,sourceattrs,deadline,parent_identity)
    files[op/'original.arc']=fact(op/'original.arc',512*1024**2,deadline)
    preserve(op/'original.arc',op/'restored-original.arc',files[op/'original.arc'],sourceattrs,deadline,parent_identity)
    files[op/'restored-original.arc']=fact(op/'restored-original.arc',512*1024**2,deadline)
    write(op/'prepared.cbz',repaired,parent_identity)
    staged=fact(op/'prepared.cbz',512*1024**2+2,deadline);files[op/'prepared.cbz']=staged
    readback=read_checked(op/'prepared.cbz',staged['signature9'],512*1024**2+2,deadline);inv,metadata=modules[5].independent(readback,g,deadline)
    check(hashlib.sha256(readback).hexdigest()==evidence['derivative_sha256'] and inv==plan['inventory']
          and metadata==plan['root_metadata_sha256'],'independent-stage-readback')
    binding=dict(version=1,kind='owned-archive-repair-preparation',implementation=implementation_fact,owner=owner,census=census,
        controls={str(p):files[p] for p in control},ancestors={str(p):v for p,v in nodes.items()},
        claims={str(p):v for p,v in claims.items()},
        catalog=observed,policy=policyproof,writer_identity=identity,source=sourcefact,source_attributes=sourceattrs,
        exceptional_witness=w,derivative=staged,preservation=evidence,operation_id=operation_id,
        custody=dict(original=files[op/'original.arc'],restore=files[op/'restored-original.arc']),
        executable=False,native_grant=False,mutation_authority=False,adoption_authority=False,
        ordinary_source_admission=False,publication_acceptance=False,reader_preservation_verified=False)
    binding['token']=digest(binding);data=compact(binding);write(op/'preparation.json',data,parent_identity)
    directory=signature(op)
    check([directory[i] for i in (0,1,5,6,7)]==[opidentity[i] for i in (0,1,5,6,7)],'owned-operation-incarnation')
    files[op/'preparation.json']=fact(op/'preparation.json',512*1024**2+2,deadline)
    check(read_checked(op/'preparation.json',files[op/'preparation.json']['signature9'],512*1024**2+2,deadline)==data,'intended-preparation')
    check(files[op/'preparation.json']['sha256']==hashlib.sha256(data).hexdigest(),'intended-preparation-digest')
    check(set(os.listdir(op))=={'intent.json','original.arc','restored-original.arc','prepared.cbz','preparation.json'},'closed-stage-census')
    for p,f in files.items():check(fact(p,max(f['signature9'][2],1),deadline)==f,'stage-CAS')
    attrs={p:attributes(p) for p in (source,op/'original.arc',op/'restored-original.arc')}
    check(all(v==sourceattrs for v in attrs.values()),'preserved-attributes')
    result=RepairPreparation(_KEY,controller,writer,modules,files,attrs,nodes,claims,census,records,binding,deadline,op,directory)
    result.revalidate();return result

if __name__=='__main__':print(json.dumps(dict(prepare=False,adoption_authority=False,mutation_authority=False)))
