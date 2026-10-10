#!/usr/bin/env python3
"""Private quiesced-state backup/restore proof; no services, media or cleanup.

Usage: helper backup --scope-file PRIVATE_JSON
       helper verify --operation-root PRIVATE_DIRECTORY [--check-source]
No source/output paths, rows, configuration or exceptions are printed.
"""
import argparse
from contextlib import closing
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import sys
import struct
import tempfile
import time

MAX_FILES = 100000
MAX_MANIFEST = 64 * 1024**2
MAX_BYTES = 512 * 1024**3
DEADLINE = 180


class Held(Exception):
    pass


def exact(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise Held('schema')


def absolute(value):
    if (not isinstance(value, str) or not value or '\0' in value
            or len(value.encode()) > 4096):
        raise Held('path')
    result = Path(value)
    if not result.is_absolute() or '..' in result.parts:
        raise Held('path')
    if any(p.is_symlink() for p in (result, *result.parents)):
        raise Held('linked-root')
    return result


def private(path, directory=False):
    path = absolute(str(path));info = path.lstat()
    if (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600)
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            or (not directory and info.st_nlink != 1)):
        raise Held('privacy')
    return path


def decode(path):
    private(path)
    if path.stat().st_size > MAX_MANIFEST:
        raise Held('bounds')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:raise Held('duplicate')
            result[key] = value
        return result
    return json.loads(path.read_bytes(), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(Held('number')))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def stamp(path):
    s = path.lstat()
    return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]


def ancestor_identity(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode):raise Held('ancestor-type')
    return [info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid]


def capture_ownership(paths):
    # Guard only admitted roots and their directory ancestors. Inventory leaf
    # symlinks (such as .env inside a scope) retain their existing link proof.
    roots = tuple(dict.fromkeys(Path(path) for path in paths))
    ancestors = {}
    for path in roots:
        if absolute(str(path)) != path:raise Held('root-admission')
        chain = (path,*path.parents) if path.is_dir() else path.parents
        for parent in chain:
            ancestors.setdefault(parent,ancestor_identity(parent))
    if len(ancestors) > 4096:raise Held('bounds')
    guard = roots,ancestors
    check_ownership(guard)
    return guard


def check_ownership(guard):
    roots,ancestors = guard
    for path in roots:
        if absolute(str(path)) != path:raise Held('root-admission')
    for path,expected in ancestors.items():
        if ancestor_identity(path) != expected:raise Held('ancestor-changed')
    # Repeat canonical admission after ancestor reads, followed only by cheap
    # incarnation checks. No manifest hashing/copy/receipt write follows this
    # final boundary before the caller checks its node stamps and acknowledges.
    for path in roots:
        if absolute(str(path)) != path:raise Held('root-admission')
    if any(ancestor_identity(path) != expected for path,expected in ancestors.items()):
        raise Held('ancestor-changed')


def attrs(path):
    s = path.lstat();names = os.listxattr(path, follow_symlinks=False)
    if len(names) > 64:raise Held('attributes')
    values = {key:os.getxattr(path,key,follow_symlinks=False).hex() for key in names}
    if sum(len(value) for value in values.values()) > 1024**2:raise Held('attributes')
    return dict(mode=stat.S_IMODE(s.st_mode),uid=s.st_uid,gid=s.st_gid,mtime_ns=s.st_mtime_ns,xattrs=values)


def hash_file(path):
    before = stamp(path)
    fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise Held('special-file')
        result = hashlib.sha256()
        for block in iter(lambda:stream.read(1024**2),b''):result.update(block)
    if stamp(path) != before:raise Held('source-changed')
    return result.hexdigest()


def inventory(root, kind, *, detached=False):
    if kind not in ('tree','file'):raise Held('kind')
    before = stamp(root)
    if not (stat.S_ISDIR(before[5]) if kind == 'tree' else stat.S_ISREG(before[5])):
        raise Held('scope-type')
    nodes = [root]
    if kind == 'tree':
        def failed(_):raise Held('walk')
        for directory, folders, files in os.walk(root,followlinks=False,onerror=failed):
            for name in list(folders):
                if (Path(directory)/name).is_symlink():folders.remove(name);files.append(name)
            nodes.extend(Path(directory)/name for name in folders+files)
            if len(nodes) > MAX_FILES:raise Held('bounds')
    rows = [];total = 0
    for node in sorted(nodes):
        initial = stamp(node);mode = initial[5]
        if stat.S_ISREG(mode):
            if initial[8] < 1 or (detached and initial[8] != 1):raise Held('physical-alias')
            total += initial[2]
            if total > MAX_BYTES:raise Held('bounds')
            form, sha, link = 'file',hash_file(node),None
        elif stat.S_ISDIR(mode):form,sha,link = 'directory',None,None
        elif stat.S_ISLNK(mode):form,sha,link = 'symlink',None,os.readlink(node)
        else:raise Held('special-file')
        metadata = attrs(node)
        if stamp(node) != initial:raise Held('source-changed')
        rows.append(dict(path='.' if node == root else str(node.relative_to(root)),
                         kind=form,sha256=sha,link=link,attributes=metadata,stamp=initial))
    if stamp(root) != before:raise Held('source-changed')
    return rows,total


def logical(rows):
    return [{key:value for key,value in row.items() if key != 'stamp'} for row in rows]


def apply_attrs(path, value):
    os.chown(path,value['uid'],value['gid'],follow_symlinks=False)
    if not path.is_symlink():os.chmod(path,value['mode'])
    current = os.listxattr(path,follow_symlinks=False)
    for name in set(current)-set(value['xattrs']):os.removexattr(path,name,follow_symlinks=False)
    for name, encoded in value['xattrs'].items():os.setxattr(path,name,bytes.fromhex(encoded),follow_symlinks=False)
    os.utime(path,ns=(value['mtime_ns'],value['mtime_ns']),follow_symlinks=False)


def sync(path):
    fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def copy_scope(source, target, rows):
    for row in sorted(rows,key=lambda value:(len(Path(value['path']).parts),value['path'])):
        node = source if row['path'] == '.' else source/row['path']
        dest = target if row['path'] == '.' else target/row['path']
        if row['kind'] == 'directory':dest.mkdir(mode=0o700)
        elif row['kind'] == 'symlink':os.symlink(row['link'],dest)
        else:
            fd = os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            incoming = os.open(node,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            with os.fdopen(fd,'wb') as out, os.fdopen(incoming,'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise Held('special-file')
                shutil.copyfileobj(stream,out,1024**2);out.flush();os.fsync(out.fileno())
    for row in sorted(rows,key=lambda value:len(Path(value['path']).parts),reverse=True):
        dest = target if row['path'] == '.' else target/row['path']
        apply_attrs(dest,row['attributes'])
        if not dest.is_symlink():sync(dest)
    sync(target.parent)


def wal_header(path, database_path):
    """Validate the committed readable WAL prefix; retain stale reset frames.

    SQLite fileformat2.html §§4.1–4.4 specify salts/checksums and stale tails.
    Matching-salt corruption, partial frames or unknown format remains held.
    """
    size = path.stat().st_size
    if size == 0:return dict(valid_frames=0,committed_frames=0,stale_frames=0)
    with path.open('rb') as stream:
        raw = stream.read(32)
        if len(raw) != 32:raise Held('malformed-wal')
        magic,version,pagesize,_,salt1,salt2,c0,c1 = struct.unpack('>8I',raw)
        if (magic not in (0x377f0682,0x377f0683) or version != 3007000
                or pagesize < 512 or pagesize > 65536 or pagesize & (pagesize-1)
                or (size-32) % (24+pagesize)):raise Held('malformed-wal')
        with database_path.open('rb') as base:header=base.read(100)
        if len(header) < 100 or header[:16] != b'SQLite format 3\0':raise Held('database-integrity')
        base_pagesize = int.from_bytes(header[16:18],'big')
        if (65536 if base_pagesize==1 else base_pagesize) != pagesize:raise Held('mismatched-wal')
        endian = '<' if magic==0x377f0682 else '>'
        def checksum(data, current):
            words = struct.unpack(endian+str(len(data)//4)+'I',data)
            a,b = current
            for i in range(0,len(words),2):
                a = (a+words[i]+b)&0xffffffff;b = (b+words[i+1]+a)&0xffffffff
            return a,b
        current = checksum(raw[:24],(0,0))
        if current != (c0,c1):raise Held('malformed-wal')
        valid=committed=stale=0
        frames = (size-32)//(24+pagesize)
        if frames > 1000000:raise Held('database-bounds')
        for index in range(frames):
            frame = stream.read(24);page = stream.read(pagesize)
            page_number,commit,s1,s2,a,b = struct.unpack('>6I',frame)
            if (s1,s2) != (salt1,salt2):
                stale = frames-index;break
            current = checksum(frame[:8]+page,current)
            if page_number==0 or current != (a,b):raise Held('malformed-wal')
            valid += 1
            if commit:committed=valid
        return dict(valid_frames=valid,committed_frames=committed,stale_frames=stale)


def database(path):
    """Only a detached temporary SQLite pair may perform WAL-index recovery."""
    path = absolute(str(path))
    if os.path.lexists(str(path)+'-journal'):raise Held('rollback-journal-retained')
    companions = [Path(str(path)+suffix) for suffix in ('-wal','-shm')
                  if os.path.lexists(str(path)+suffix)]
    if any(item.name.endswith('-shm') for item in companions) and not any(item.name.endswith('-wal') for item in companions):
        raise Held('orphan-shm')
    sources = [path,*companions]
    states = {}
    for source in sources:
        absolute(str(source));before=stamp(source)
        if not stat.S_ISREG(before[5]) or before[8] < 1:raise Held('database-companion')
        states[source] = dict(stamp=before,sha256=hash_file(source))
    wal = next((item for item in companions if item.name.endswith('-wal')),None)
    wal_proof = None if wal is None else wal_header(wal,path)
    deadline = time.monotonic()+DEADLINE
    with tempfile.TemporaryDirectory(prefix='owned-publication-db-') as work:
        root = Path(work);root.chmod(0o700);isolated=root/path.name
        for source in sources:
            fd = os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            with os.fdopen(fd,'rb') as incoming,(root/source.name).open('xb') as target:
                shutil.copyfileobj(incoming,target,1024**2)
            (root/source.name).chmod(0o600)
            if hash_file(root/source.name) != states[source]['sha256']:raise Held('database-copy-drift')
        with closing(sqlite3.connect(isolated.as_uri()+'?mode=ro',uri=True)) as db:
            db.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
            db.execute('PRAGMA query_only=ON')
            if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:raise Held('database-integrity')
            schema = db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name,tbl_name,sql").fetchall()
            tables = {}
            for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
                quoted = '"'+name.replace('"','""')+'"'
                hashes = []
                for row in db.execute('SELECT * FROM '+quoted):
                    hashes.append(digest([dict(blob=item.hex()) if isinstance(item,bytes) else item for item in row]))
                    if len(hashes) > 1000000:raise Held('database-bounds')
                tables[name] = dict(rows=len(hashes),digest=digest(sorted(hashes)))
    expected = {str(item) for item in companions}
    present = {str(Path(str(path)+suffix)) for suffix in ('-wal','-shm') if os.path.lexists(str(path)+suffix)}
    if present != expected or os.path.lexists(str(path)+'-journal'):raise Held('database-companion-drift')
    for source,before in states.items():
        if stamp(source) != before['stamp'] or hash_file(source) != before['sha256']:raise Held('database-source-drift')
    return dict(schema=digest(schema),tables=tables,
                companions={item.name[len(path.name):]:states[item]['sha256'] for item in companions},wal=wal_proof)


def database_rows(scopes, required):
    result = {}
    for scope in scopes:
        source = Path(scope['path'])
        for row in scope['records']:
            if row['kind'] != 'file':continue
            path = source if row['path'] == '.' else source/row['path']
            with path.open('rb') as stream:is_db = stream.read(16) == b'SQLite format 3\0'
            key = scope['name']+':'+row['path']
            if is_db or key in required:
                declared = {row['path'] for row in scope['records'] if row['kind']=='file'}
                for suffix in ('-wal','-shm','-journal'):
                    sibling=Path(str(path)+suffix)
                    if os.path.lexists(sibling):
                        if scope['kind'] != 'tree' or str(sibling.relative_to(source)) not in declared:
                            raise Held('missing-database-companion-scope')
                result[key] = database(path)
    if not set(required).issubset(result):raise Held('missing-database')
    return result


def write_json(path, value):
    raw = json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
    if len(raw) > MAX_MANIFEST:raise Held('bounds')
    fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    sync(path.parent)


def configuration(scope_file):
    return validated_configuration(decode(scope_file))


def validated_configuration(value):
    exact(value,('version','scopes','required_databases','writer_lock','output_root','forbidden_roots','quiesced'))
    if type(value['version']) is not int or value['version'] != 1:raise Held('schema')
    exact(value['quiesced'],('mylar','worker'))
    if any(item is not True for item in value['quiesced'].values()):raise Held('not-quiesced')
    if not isinstance(value['scopes'],list) or not 1 <= len(value['scopes']) <= 64:raise Held('scope')
    if not isinstance(value['forbidden_roots'],list) or not value['forbidden_roots']:raise Held('scope')
    forbidden = [absolute(item) for item in value['forbidden_roots']]
    roots = [];names = []
    for scope in value['scopes']:
        exact(scope,('name','path','kind'))
        if not isinstance(scope['name'],str) or not re.fullmatch('[a-z][a-z0-9-]{0,31}',scope['name']):raise Held('scope')
        root = absolute(scope['path']);roots.append(root);names.append(scope['name'])
        if scope['kind'] not in ('file','tree') or any(root.is_relative_to(item) or item.is_relative_to(root) for item in forbidden):raise Held('library-scope')
    if len(set(names)) != len(names):raise Held('scope')
    if any(a.is_relative_to(b) or b.is_relative_to(a) for i,a in enumerate(roots) for b in roots[i+1:]):raise Held('overlap')
    output = absolute(value['output_root'])
    if any(output.is_relative_to(item) or item.is_relative_to(output) for item in roots+forbidden):raise Held('overlap')
    lock = absolute(value['writer_lock'])
    if not any(scope['kind']=='tree' and lock.is_relative_to(Path(scope['path'])) for scope in value['scopes']):raise Held('lock-scope')
    if not isinstance(value['required_databases'],list) or not value['required_databases']:raise Held('database-scope')
    for key in value['required_databases']:
        if (not isinstance(key,str) or ':' not in key or key.split(':',1)[0] not in names
                or Path(key.split(':',1)[1]).is_absolute() or '..' in Path(key.split(':',1)[1]).parts):raise Held('database-scope')
    return value,output,lock


def backup(scope_file):
    value,root,lock = configuration(scope_file)
    source_ownership = capture_ownership([Path(scope['path']) for scope in value['scopes']]+[root.parent])
    fd = os.open(lock,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        initial = os.fstat(fd)
        lock_state = [initial.st_dev,initial.st_ino,initial.st_size,initial.st_mtime_ns,
                      initial.st_ctime_ns,initial.st_mode,initial.st_uid,initial.st_gid,initial.st_nlink]
        if not stat.S_ISREG(initial.st_mode) or initial.st_nlink != 1:raise Held('lock')
        def lock_proof():
            current = os.fstat(fd)
            observed = [current.st_dev,current.st_ino,current.st_size,current.st_mtime_ns,
                        current.st_ctime_ns,current.st_mode,current.st_uid,current.st_gid,current.st_nlink]
            if absolute(str(lock)) != lock or stamp(lock) != lock_state or observed != lock_state:
                raise Held('lock-changed')
        lock_proof()
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        lock_proof()
        scopes = [];total = 0
        for scope in value['scopes']:
            rows,size = inventory(Path(scope['path']),scope['kind']);total += size
            scopes.append(dict(scope,records=rows))
        if sum(len(scope['records']) for scope in scopes) > MAX_FILES:raise Held('bounds')
        if total > MAX_BYTES or shutil.disk_usage(root.parent).free < total*2+1024**2:raise Held('space')
        lock_proof()
        baselines = database_rows(scopes,value['required_databases'])
        lock_proof()
        root.mkdir(mode=0o700);private(root,directory=True)
        (root/'backup').mkdir(mode=0o700);(root/'restore').mkdir(mode=0o700)
        for scope in scopes:
            lock_proof();copy_scope(Path(scope['path']),root/'backup'/scope['name'],scope['records']);lock_proof()
        for scope in scopes:
            lock_proof();copy_scope(root/'backup'/scope['name'],root/'restore'/scope['name'],scope['records']);lock_proof()
        manifest = dict(version=1,kind='owned-publication-state',scope=value,scopes=scopes,
                        databases=baselines,bytes=total,created=int(time.time()))
        lock_proof();write_json(root/'manifest.json',manifest);lock_proof()
        late_evidence = []
        final_ownership = capture_ownership([Path(scope['path']) for scope in value['scopes']]+[root,root/'backup',root/'restore'])
        answer = verify(root,check_source=True,_captured=late_evidence)
        root_identity = stamp(root)[:2]
        lock_proof();write_json(root/'verification.json',answer);lock_proof()
        private(root,directory=True)
        if hash_file(root/'manifest.json') != answer['manifest_sha256']:raise Held('manifest-changed')
        lock_proof()
        check_ownership(source_ownership)
        check_ownership(final_ownership)
        if stamp(root)[:2] != root_identity or any(stamp(path) != expected for path,expected in late_evidence):
            raise Held('evidence-changed')
        return answer
    finally:os.close(fd)


def verify(root, check_source=False, *, _captured=None):
    private(root,directory=True);manifest_path = root/'manifest.json'
    before_manifest = stamp(manifest_path);before_sha = hash_file(manifest_path)
    manifest = decode(manifest_path)
    exact(manifest,('version','kind','scope','scopes','databases','bytes','created'))
    if type(manifest['version']) is not int or manifest['version'] != 1 or manifest['kind'] != 'owned-publication-state':raise Held('schema')
    _,declared_root,_ = validated_configuration(manifest['scope'])
    if declared_root != root:raise Held('scope')
    if not isinstance(manifest['scopes'],list) or len(manifest['scopes']) != len(manifest['scope']['scopes']):raise Held('scope')
    for declared,recorded in zip(manifest['scope']['scopes'],manifest['scopes']):
        exact(recorded,('name','path','kind','records'))
        if {key:recorded[key] for key in declared} != declared:raise Held('scope')
        if not isinstance(recorded['records'],list) or not 1 <= len(recorded['records']) <= MAX_FILES:raise Held('bounds')
        for row in recorded['records']:
            exact(row,('path','kind','sha256','link','attributes','stamp'))
            if (not isinstance(row['path'],str) or Path(row['path']).is_absolute()
                    or '..' in Path(row['path']).parts or row['kind'] not in ('file','directory','symlink')):raise Held('scope')
    ownership = capture_ownership([root,root/'backup',root/'restore']+
                                  ([Path(scope['path']) for scope in manifest['scopes']] if check_source else []))
    totals = dict(files=0,directories=0,symlinks=0)
    for base in ('backup','restore'):
        private(root/base,directory=True)
        if {path.name for path in (root/base).iterdir()} != {scope['name'] for scope in manifest['scopes']}:raise Held('copy-mismatch')
        observed = []
        for scope in manifest['scopes']:
            rows,_ = inventory(root/base/scope['name'],scope['kind'],detached=True)
            if logical(rows) != logical(scope['records']):raise Held('copy-mismatch')
            observed.append(dict(scope,path=str(root/base/scope['name']),records=rows))
            source_records = scope['records']
            for old,new in zip(source_records,rows):
                if old['kind']=='file' and old['stamp'][:2] == new['stamp'][:2]:raise Held('shared-copy')
            if base == 'restore':
                for row in rows:totals[{'file':'files','directory':'directories','symlink':'symlinks'}[row['kind']]] += 1
        if database_rows(observed,manifest['scope']['required_databases']) != manifest['databases']:raise Held('database-mismatch')
    if check_source and database_rows(manifest['scopes'],manifest['scope']['required_databases']) != manifest['databases']:raise Held('database-mismatch')
    final_stamps = [(root/base,stamp(root/base)) for base in ('backup','restore')]
    for scope in manifest['scopes']:
        one,_ = inventory(root/'backup'/scope['name'],scope['kind'],detached=True)
        two,_ = inventory(root/'restore'/scope['name'],scope['kind'],detached=True)
        if logical(one) != logical(scope['records']) or logical(two) != logical(scope['records']):raise Held('copy-mismatch')
        for base,rows in ((root/'backup'/scope['name'],one),(root/'restore'/scope['name'],two)):
            final_stamps.extend((base if row['path']=='.' else base/row['path'],row['stamp']) for row in rows)
        if any(a['kind']=='file' and a['stamp'][:2] == b['stamp'][:2] for a,b in zip(one,two)):raise Held('shared-copy')
        if check_source:
            current,_ = inventory(Path(scope['path']),scope['kind'])
            if current != scope['records']:raise Held('source-changed')
            source = Path(scope['path'])
            final_stamps.extend((source if row['path']=='.' else source/row['path'],row['stamp']) for row in current)
    if stamp(manifest_path) != before_manifest or hash_file(manifest_path) != before_sha:raise Held('manifest-changed')
    check_ownership(ownership)
    if any(stamp(path) != recorded for path,recorded in final_stamps):raise Held('evidence-changed')
    if _captured is not None:_captured.extend(final_stamps+[(manifest_path,before_manifest)])
    return dict(version=1,restore_verified=True,manifest_sha256=before_sha,
                records=totals,database_checks=len(manifest['databases']),source_checked=check_source,
                external_symlink_targets_included=False,application_recovery_verified=False)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description='Private quiesced-state backup and offline restore proof')
    commands = parser.add_subparsers(dest='action',required=True)
    create = commands.add_parser('backup');create.add_argument('--scope-file',type=Path,required=True)
    check = commands.add_parser('verify');check.add_argument('--operation-root',type=Path,required=True);check.add_argument('--check-source',action='store_true')
    args = parser.parse_args()
    try:
        result = backup(args.scope_file) if args.action=='backup' else verify(args.operation_root, args.check_source)
        print(json.dumps(result,sort_keys=True));return 0
    except (Held,OSError,ValueError,TypeError,KeyError,sqlite3.Error):
        print(json.dumps(dict(version=1,verified=False,reason='backup-or-restore-held',partial_evidence_retained=True)))
        return 2


if __name__ == '__main__':sys.exit(main())
