"""Read-only catalog projection component; never authorizes library retirement.

Caller must separately bind actual held native process, installed SDK, owned
create=False rawWriter, current census/registered originals and current target
owner. This standalone component intentionally makes none of those claims.
"""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import time


class Held(ValueError):
    pass


def signature(p):
    s = p.lstat()
    return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,
            s.st_mode,s.st_uid,s.st_gid,s.st_nlink]


def canonical(p, existing=True):
    p = Path(p)
    if not p.is_absolute() or '..' in p.parts or p.resolve(strict=existing) != p:
        raise Held('noncanonical-path')
    for q in (p,*p.parents):
        if q.is_symlink():
            raise Held('linked-path')
    return p


def parents(paths):
    result = {}
    for p in paths:
        for q in p.parents:
            s = signature(q)
            if not stat.S_ISDIR(s[5]):
                raise Held('ancestor-type')
            result[str(q)] = [s[i] for i in (0,1,5,6,7)]
    return result


def fact(p, deadline):
    canonical(p);before = signature(p)
    if not stat.S_ISREG(before[5]) or before[8] != 1 or not 0 < before[2] <= 4*1024**3:
        raise Held('regular-detached-file')
    fd = os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    h = hashlib.sha256();total = 0
    with os.fdopen(fd,'rb') as f:
        if signature_fd(f.fileno()) != before:
            raise Held('opened-incarnation')
        while True:
            if time.monotonic() >= deadline:
                raise Held('deadline')
            b = f.read(1024**2)
            if not b:
                break
            total += len(b)
            if total > before[2]:
                raise Held('file-growth')
            h.update(b)
        if total != before[2] or signature_fd(f.fileno()) != before:
            raise Held('read-incarnation')
    if canonical(p) != p or signature(p) != before:
        raise Held('file-incarnation')
    return {'signature9':before,'sha256':h.hexdigest()}


def signature_fd(fd):
    s = os.fstat(fd)
    return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,
            s.st_mode,s.st_uid,s.st_gid,s.st_nlink]


def no_companions(db):
    if any(os.path.lexists(str(db)+x) for x in ('-wal','-shm','-journal')):
        raise Held('database-companion')


def text(v, nullable=False):
    if v is None and nullable:
        return
    if not isinstance(v,str) or '\0' in v or '\\' in v or len(v.encode()) > 4096:
        raise Held('catalog-value-type')


def claim_path(folder,location,roots):
    text(folder);text(location)
    if not folder or not location:
        raise Held('empty-claim')
    f,l = Path(folder),Path(location);p = f/l
    if not f.is_absolute() or '..' in f.parts or '..' in l.parts or len(p.parts)>64 or not p.is_relative_to(f) or not any(p.is_relative_to(r) for r in roots):
        raise Held('catalog-root-escape')
    canonical(p,existing=False)
    return p


def project_absence(database,source,target,library_roots, *, seconds=120,
                    max_rows=250000,max_projection_bytes=64*1024**2):
    """Pure projection proof. Caller supplies trusted native spellings; no mapping.

    Returns no raw rows. Complete typed-row digest includes comics and leftjoined
    regular/annual claims, regardless of Status, Deleted or registration.
    """
    if type(seconds) is not int or not 0<seconds<=300 or type(max_rows) is not int or not 0<max_rows<=250000 or type(max_projection_bytes) is not int or not 0<max_projection_bytes<=64*1024**2:
        raise Held('bounds')
    deadline = time.monotonic()+seconds
    db,src,dst = map(canonical,(database,source,target))
    if not isinstance(library_roots,(list,tuple)) or not 1<=len(library_roots)<=8:
        raise Held('library-root-count')
    roots = [canonical(r) for r in library_roots]
    if len({tuple(signature(r)[:2]) for r in roots})!=len(roots) or len(set(roots))!=len(roots) or any(not r.is_dir() for r in roots) or any(a!=b and a in b.parents for a in roots for b in roots):
        raise Held('library-root-alias')
    if src==dst or not all(any(p.is_relative_to(r) for r in roots) for p in (src,dst)):
        raise Held('source-target-scope')
    ancestor_facts = parents([db,src,dst,*roots])
    no_companions(db)
    facts = {p:fact(p,deadline) for p in (db,src,dst)}
    if facts[src]['signature9'][:2]==facts[dst]['signature9'][:2]:
        raise Held('source-target-physical-alias')
    if parents([db,src,dst,*roots])!=ancestor_facts:
        raise Held('admission-ancestor-drift')
    projected = [];count = used = 0;counts = {'comics':0,'issues':0,'annuals':0};claim_facts = {};claim_namespace = {}
    def add(table,row):
        nonlocal count,used
        if time.monotonic()>=deadline:
            raise Held('deadline')
        raw = json.dumps([table,list(row)],ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
        count+=1;used+=len(raw)
        if count>max_rows or used>max_projection_bytes:
            raise Held('projection-bound')
        projected.append(raw);counts[table]=counts.get(table,0)+1
    try:
        with closing(sqlite3.connect(db.as_uri()+'?mode=ro&immutable=1',uri=True)) as conn:
            conn.execute('PRAGMA query_only=ON');conn.execute('BEGIN')
            conn.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
            if conn.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:
                raise Held('database-integrity')
            parent_count = {}
            for row in conn.execute('SELECT ComicID,ComicLocation FROM comics'):
                text(row[0]);text(row[1],nullable=True)
                if not row[0]:raise Held('empty-comic-id')
                parent_count[row[0]]=parent_count.get(row[0],0)+1;add('comics',row)
            for table in ('issues','annuals'):
                fields = 'i.IssueID,i.ComicID,i.Location,i.Status'+(',i.Deleted' if table=='annuals' else '')
                sql = 'SELECT '+fields+',c.ComicID,c.ComicLocation FROM '+table+' i LEFT JOIN comics c ON c.ComicID=i.ComicID'
                for row in conn.execute(sql):
                    issue,comic,location,status = row[:4]
                    for value in (issue,comic):
                        text(value)
                        if not value:raise Held('empty-issue-id')
                    text(location,nullable=True);text(status,nullable=True)
                    if parent_count.get(comic)!=1 or row[-2]!=comic:
                        raise Held('orphan-or-shadow-parent')
                    if table=='annuals' and row[4] is not None and type(row[4]) is not int:
                        raise Held('deleted-type')
                    add(table,row)
                    if location is None or location=='':
                        continue
                    p = claim_path(row[-1],location,roots)
                    if p==src:
                        raise Held('source-catalog-path')
                    for q in p.parents:
                        try:ns=signature(q)
                        except FileNotFoundError:ns=None
                        if ns is not None and not stat.S_ISDIR(ns[5]):raise Held('claim-ancestor-type')
                        value=None if ns is None else [ns[i] for i in (0,1,5,6,7)]
                        if q in claim_namespace and claim_namespace[q]!=value:raise Held('claim-ancestor-drift')
                        claim_namespace[q]=value
                    try:s = signature(p)
                    except FileNotFoundError:
                        claim_facts[p] = None
                        continue
                    claim_facts[p] = s
                    if not stat.S_ISREG(s[5]):
                        raise Held('catalog-archive-type')
                    if s[:2]==facts[src]['signature9'][:2]:
                        raise Held('source-catalog-physical-alias')
            conn.rollback()
    except sqlite3.Error as e:
        raise Held('catalog-read-failed') from e
    digest = hashlib.sha256()
    for raw in sorted(projected):
        digest.update(len(raw).to_bytes(8,'big'));digest.update(raw)
    # Expensive full hashes finish before the terminal passive boundary.
    for p,expected in facts.items():
        if fact(p,deadline)!=expected:
            raise Held('final-file-drift')
    for p,expected in claim_facts.items():
        if time.monotonic()>=deadline:raise Held('deadline')
        canonical(p,existing=False)
        try:actual=signature(p)
        except FileNotFoundError:actual=None
        if actual!=expected:raise Held('catalog-claim-incarnation')
    no_companions(db)
    if parents([db,src,dst,*roots])!=ancestor_facts:
        raise Held('final-ancestor-drift')
    for p,expected in facts.items():
        canonical(p)
        if signature(p)!=expected['signature9']:
            raise Held('final-file-incarnation')
    no_companions(db)
    for p,expected in claim_facts.items():
        try:st=os.lstat(p)
        except FileNotFoundError:actual=None
        else:actual=[st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_mode,st.st_uid,st.st_gid,st.st_nlink]
        if actual!=expected:raise Held('terminal-claim-vector')
    for p,expected in claim_namespace.items():
        try:st=os.lstat(p)
        except FileNotFoundError:actual=None
        else:actual=[st.st_dev,st.st_ino,st.st_mode,st.st_uid,st.st_gid]
        if actual!=expected:raise Held('terminal-claim-ancestor-vector')
    no_companions(db)
    for name,expected in ancestor_facts.items():
        s=os.lstat(name)
        if [s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid]!=expected:
            raise Held('terminal-ancestor-vector')
    for p,expected in facts.items():
        s=os.lstat(p)
        actual=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]
        if actual!=expected['signature9']:
            raise Held('terminal-file-vector')
    return {'version':1,'kind':'readonly-all-catalog-source-absence-projection',
            'catalog_path_and_physical_absence':True,'projection_sha256':digest.hexdigest(),
            'row_counts':counts,'projection_bytes':used,'database':{'path':str(db),**facts[db]},
            'source':{'path':str(src),**facts[src]},'target':{'path':str(dst),**facts[dst]},
            'writer_bound':False,'census_verified':False,'registered_originals_checked':False,
            'current_target_owner_verified':False,'quiescence_verified':False,
            'publication_acceptance':False,'mutation_authority':False,'advisory_only':True,
            'passive_claim_files':{str(p):v for p,v in claim_facts.items()},
            'passive_claim_ancestors':{str(p):v for p,v in claim_namespace.items()},
            'passive_scope_ancestors':ancestor_facts}



def close_projection(value):
    """Direct passive namespace/absence closure for owning caller's last boundary.

    Must follow ALL caller hashing/xattr/signature/SDK callbacks. Does not confer
    Writer, reader or mutation admission. No data reads or canonical callbacks.
    """
    for name,expected in value['passive_claim_files'].items():
        try:s=os.lstat(name)
        except FileNotFoundError:actual=None
        else:actual=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]
        if actual!=expected:raise Held('owning-terminal-catalog-claim')
    for group in ('passive_claim_ancestors','passive_scope_ancestors'):
        for name,expected in value[group].items():
            try:s=os.lstat(name)
            except FileNotFoundError:actual=None
            else:actual=[s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid]
            if actual!=expected:raise Held('owning-terminal-catalog-ancestor')
    db=Path(value['database']['path'])
    s=os.lstat(db)
    actual=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]
    if actual!=value['database']['signature9']:raise Held('owning-terminal-catalog-db')
    for suffix in ('-journal','-wal','-shm'):
        try:os.lstat(str(db)+suffix)
        except FileNotFoundError:continue
        raise Held('owning-terminal-catalog-companion')
