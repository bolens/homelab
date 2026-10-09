"""Scoped, stopped-reader all-reference lease. No DTO or HTTP acknowledgement grants."""
import base64
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import struct
import tempfile
import threading
import time
import weakref
from contextlib import closing
from mylar import publication_archive_owned as o

_KEY=object(); _SEALS=weakref.WeakKeyDictionary()
MAX=256*1024**2; ROWS=1000000

def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def cell(v):
    if v is None:return ['null']
    if type(v) is int:return ['int',str(v)]
    if type(v) is float:return ['float',struct.pack('>d',v).hex()]
    if type(v) is str:return ['text',v]
    if type(v) is bytes:return ['blob',base64.b64encode(v).decode()]
    raise o.Held('reader-cell')
def quoted(v):
    o.check(type(v) is str and v and '\0' not in v and len(v.encode())<4096,'reader-sql-name')
    return '"'+v.replace('"','""')+'"'
def logical(db,deadline):
    o.check(db.execute('PRAGMA integrity_check').fetchall()==[('ok',)] and not db.execute('PRAGMA foreign_key_check').fetchall(),'reader-integrity')
    schema=db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').fetchall()
    o.check(len(schema)<=4096,'reader-schema-bound'); result={'schema':[[cell(v) for v in row] for row in schema],'tables':{}}
    count=total=0
    for kind,name,_,_ in schema:
        if kind!='table':continue
        columns=db.execute('PRAGMA table_xinfo('+quoted(name)+')').fetchall()
        rows=[]
        for row in db.execute('SELECT * FROM '+quoted(name)):
            v=[cell(c) for c in row]; count+=1; total+=len(encoded(v))
            o.check(count<=ROWS and total<=MAX and time.monotonic()<deadline,'reader-row-bound'); rows.append(v)
        result['tables'][name]={'columns':[[cell(v) for v in row] for row in columns],'rows':sorted(rows,key=encoded)}
    return result

def pair(db,deadline):
    db=o.canonical(db); result={}
    o.check(not os.path.lexists(str(db)+'-journal'),'reader-hot-journal')
    wal=os.path.lexists(str(db)+'-wal'); shm=os.path.lexists(str(db)+'-shm')
    o.check(wal==shm,'reader-paired-WAL')
    for suffix in ('','-wal','-shm'):
        p=Path(str(db)+suffix)
        if os.path.lexists(p):result[p]={'fact':o.fact(p,MAX,deadline),'attrs':o.attributes(p)}
        else:result[p]=None
    return result

def observe(db,scratch,deadline):
    """SQLite reads ONLY another detached pair; originals and retained restore stay unopened."""
    before=pair(db,deadline)
    with tempfile.TemporaryDirectory(prefix='repair-reader-',dir=scratch) as work:
        root=Path(work);root.chmod(0o700)
        for p,v in before.items():
            if v is None:continue
            raw=o.read_checked(p,v['fact']['signature9'],MAX,deadline)
            o.write(root/p.name,raw,o.stat5(os.lstat(root)))
        o.check(pair(db,deadline)==before,'reader-copy-CAS')
        with closing(sqlite3.connect('file:'+str(root/db.name)+'?mode=ro',uri=True)) as conn:
            conn.execute('PRAGMA query_only=ON');conn.execute('PRAGMA trusted_schema=OFF');conn.execute('BEGIN')
            result=logical(conn,deadline);conn.rollback()
        o.check(pair(db,deadline)==before,'reader-observation-CAS')
    return result,before

def installed():
    for p in (Path(__file__),Path(o.__file__)):
        o.check(p==Path('/app/mylar3/mylar')/p.name and p.resolve()==p,'installed-repair-reader')

def lifecycle():
    m=importlib.import_module('mylar.publication_reader_lifecycle')
    o.check(Path(m.__file__)==Path('/app/mylar3/mylar/publication_reader_lifecycle.py') and Path(m.__file__).resolve()==Path(m.__file__),'installed-reader-lifecycle')
    return m

def direct(files,nodes,absent):
    for p,v in files.items():
        z=os.lstat(p)
        if [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]!=v:raise o.Held('reader-terminal-file')
    for p,v in nodes.items():
        z=os.lstat(p)
        if [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]!=v:raise o.Held('reader-terminal-ancestor')
    for p in absent:
        try:os.lstat(p)
        except FileNotFoundError:continue
        raise o.Held('reader-terminal-absence')

class RepairReaderLease:
    __slots__=('custody','scratch','source','deadline','_pairs','_observations','_nodes','_files','_absent','_binding','_thread','__weakref__')
    def __init__(self,key,custody,source,scratch,deadline,pairs,observations,nodes,files,absent,binding):
        o.check(key is _KEY,'reader-owning-factory');self.custody=custody;self.source=source;self.scratch=scratch;self.deadline=deadline
        self._pairs=pairs;self._observations=observations;self._nodes=nodes;self._files=files;self._absent=absent;self._binding=binding;self._thread=threading.get_ident()
        _SEALS[self]=self.seal();self.close()
    def seal(self):return hashlib.sha256(encoded({'objects':[id(self.custody),self._thread], 'paths':[str(self.source),str(self.scratch)],'deadline':self.deadline,'pairs':{str(k):{str(p):v for p,v in x.items()} for k,x in self._pairs.items()},'observations':self._observations,'nodes':{str(p):v for p,v in self._nodes.items()},'files':{str(p):v for p,v in self._files.items()},'absent':sorted(map(str,self._absent)),'binding':self._binding})).hexdigest()
    @property
    def binding(self):
        value=copy.deepcopy(self._binding);self.close();return value
    def close(self):
        entry_seal=_SEALS.get(self)
        files=tuple((str(p),tuple(v)) for p,v in self._files.items())
        nodes=tuple((str(p),tuple(v)) for p,v in self._nodes.items())
        absent=tuple(map(str,self._absent));pairs=copy.deepcopy(self._pairs)
        o.check(entry_seal==self.seal() and threading.get_ident()==self._thread and time.monotonic()<self.deadline,'reader-lifetime')
        self.custody.revalidate_stopped()
        for db,v in pairs.items():o.check(pair(db,self.deadline)==v,'reader-current-pair')
        final_seal=self.seal()
        if _SEALS.get(self)!=entry_seal or final_seal!=entry_seal:raise o.Held('reader-lifetime-final')
        # Every lifetime, custody and pair callback precedes the immutable raw closure.
        for path,value in nodes:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise o.Held('reader-inline-ancestor')
        for path,value in files:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise o.Held('reader-inline-file')
        for path in absent:
            try:os.lstat(path)
            except FileNotFoundError:continue
            raise o.Held('reader-inline-absence')
    def revalidate(self):
        self.close()
        for db,expected in self._observations.items():
            current,p=observe(Path(db),self.scratch,self.deadline)
            o.check(current==expected and p==self._pairs[Path(db)],'reader-all-reference-CAS')
        self.close();return self.binding
    def vectors(self):
        value=copy.deepcopy(self._files),copy.deepcopy(self._nodes),set(self._absent);self.close();return value

def from_stopped(custody,source,scratch,seconds=120):
    """Only the installed, continuously owning lifecycle parent supplies reader scope."""
    installed();m=lifecycle();o.check(type(custody) is m.StoppedReaderCustody,'exact-reader-custody')
    source=o.canonical(source);scratch=o.canonical(scratch)
    o.check(type(seconds) is int and 1<=seconds<=120,'reader-deadline');deadline=time.monotonic()+seconds
    paths=[custody.main,custody.tasks,custody.config_root,custody.restore_root,scratch,source]
    nodes=o.ancestors(paths);o.check(stat.S_IMODE(os.lstat(scratch).st_mode)==0o700,'reader-scratch-private')
    o.check(not any(scratch.is_relative_to(Path(p)) or Path(p).is_relative_to(scratch) for p in (custody.config_root,custody.restore_root)),'reader-scratch-disjoint')
    custody.revalidate_stopped();files,parent_nodes,absent=custody.vectors();files=copy.deepcopy(files);absent=set(absent);o.merge_nodes(nodes,parent_nodes)
    observations={};pairs={}
    for db in (Path(custody.main),Path(custody.tasks)):
        result,p=observe(db,scratch,deadline);observations[str(db)]=result;pairs[db]=p
        restored,_=observe(Path(custody.restore_root)/db.name,scratch,deadline)
        o.check(restored==result,'reader-independent-full-restore')
        for path,v in p.items():
            if v is None:absent.add(path)
            else:files[path]=v['fact']['signature9']
        absent.add(Path(str(db)+'-journal'))
    # Match native pathname with the trusted lifecycle's exact mount projection.
    url=custody.native_url(source)
    main=observations[str(custody.main)]['tables'];o.check('BOOK' in main,'reader-BOOK-schema')
    columns=[r[1][1] for r in main['BOOK']['columns']];o.check(all(k in columns for k in ('ID','URL','DELETED_DATE')),'reader-BOOK-columns')
    matches=[r for r in main['BOOK']['rows'] if r[columns.index('URL')]==['text',url]]
    o.check(matches and len(matches)<=64 and len({encoded(r[columns.index('ID')]) for r in matches})==len(matches),'reader-exact-URL-ID-census')
    # Existing page references are the owning reader's actual ordered rows, not
    # a guessed Komga hash or SDK order. Preserve deleted shadows opaquely.
    active=[x for x in matches if x[columns.index('DELETED_DATE')]==['null']]
    o.check(len(active)==1 and active[0][columns.index('ID')][0]=='text','reader-sole-active-book')
    bid=active[0][columns.index('ID')][1];o.check('MEDIA_PAGE' in main and 'MEDIA' in main,'reader-page-schema')
    pages_table=main['MEDIA_PAGE'];pc=[x[1][1] for x in pages_table['columns']]
    o.check(all(x in pc for x in ('BOOK_ID','NUMBER','FILE_NAME')),'reader-page-columns')
    pages=[x for x in pages_table['rows'] if x[pc.index('BOOK_ID')]==['text',bid]]
    o.check(pages and len(pages)<=10000 and all(x[pc.index('NUMBER')][0]=='int' and x[pc.index('FILE_NAME')][0]=='text' for x in pages),'reader-typed-pages')
    pages.sort(key=lambda x:int(x[pc.index('NUMBER')][1]));numbers=[int(x[pc.index('NUMBER')][1]) for x in pages]
    o.check(numbers[0] in (0,1) and numbers==list(range(numbers[0],numbers[0]+len(numbers))),'reader-finite-page-order')
    names=[x[pc.index('FILE_NAME')][1] for x in pages];o.check(len(set(names))==len(names),'reader-unique-page-names')
    media=main['MEDIA'];mc=[x[1][1] for x in media['columns']];o.check(all(x in mc for x in ('BOOK_ID','STATUS','PAGE_COUNT')),'reader-media-columns')
    mr=[x for x in media['rows'] if x[mc.index('BOOK_ID')]==['text',bid]]
    o.check(len(mr)==1 and mr[0][mc.index('STATUS')]==['text','READY'] and mr[0][mc.index('PAGE_COUNT')]==['int',str(len(pages))],'reader-ready-page-count')
    binding={'version':1,'kind':'same-path-repair-reader-lease','source':str(source),'url':url,'book_rows':matches,'page_rows':pages,'page_names':names,'active_book_id':bid,'all_tables_sha256':hashlib.sha256(encoded(observations)).hexdigest(),'runtime':custody.runtime,'mutation_authority':False,'publication_acceptance':False}
    for p,v in nodes.items():o.check(o.stat5(os.lstat(p))==v,'reader-admission-ancestor')
    return RepairReaderLease(_KEY,custody,source,scratch,deadline,pairs,observations,nodes,files,absent,binding)
