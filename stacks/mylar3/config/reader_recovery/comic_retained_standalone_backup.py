"""Private neutral standalone preservation. Observations confer no execution rights."""
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

MAX_BYTES = 512 * 1024 ** 3
MAX_ENTRIES = 100000
MAX_ARCHIVE_BYTES = 256 * 1024 ** 2
BACKUP_SECONDS = 1800
ROLES = ('native_state', 'reader_state', 'retained_source', 'existing_target')
PRIMITIVES_SHA256 = '5b3c1df6345af3fa551ee48a82711912e591a257ce0373082a53aff112e5b396'
APPDATA_PRIMITIVES_SHA256 = 'd2e209dd371e147815c7560de1b461753659afed915fbd990772290427995b8a'
_OBSERVATIONS = weakref.WeakKeyDictionary()
_BACKUP_SEALS = weakref.WeakKeyDictionary()
_PRIMITIVES = weakref.WeakKeyDictionary()


def _directory_names(fd):
    """Fresh OFD census; original directory FD and full facts remain retained."""
    z=os.fstat(fd)
    before=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
    fresh=os.open('.',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
    z=os.fstat(fresh);identity=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
    try:
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=before:raise ValueError('backup-census-original-FD')
        names=tuple(sorted(os.listdir(fresh)))
        for owned in (fd,fresh):
            z=os.fstat(owned)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=before:raise ValueError('backup-census-original-FD')
        return names
    finally:
        z=os.fstat(fresh)
        if (z.st_dev,z.st_ino)!=identity[:2]:raise ValueError('backup-census-resource-identity')
        os.close(fresh)
        if (z.st_mode,z.st_uid,z.st_gid)!=identity[2:]:raise ValueError('backup-census-resource-identity')


def need(value, reason):
    if not value:
        raise ValueError(reason)


def nine(z):
    return (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
            z.st_mode, z.st_uid, z.st_gid, z.st_nlink)


def five(z):
    return (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def attributes(path):
    names = tuple(sorted(os.listxattr(path, follow_symlinks=False)))
    need(len(names) <= 64, 'backup-xattr-count')
    result = tuple((name, os.getxattr(path, name, follow_symlinks=False)) for name in names)
    need(sum(len(value) for _, value in result) <= 1024 ** 2, 'backup-xattr-size')
    return result



def descriptor_attributes(fd):
    names = tuple(sorted(os.listxattr(fd)))
    need(len(names) <= 64, 'backup-xattr-count')
    result = tuple((name, os.getxattr(fd, name)) for name in names)
    need(sum(len(value) for _, value in result) <= 1024 ** 2, 'backup-xattr-size')
    return result


def raw(frame):
    files, nodes, spaces = frame
    for path, names in spaces:
        if tuple(sorted(os.listdir(path))) != names:
            raise ValueError('backup-original-namespace')
    for path, stamp in nodes:
        z = os.lstat(path)
        if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != stamp:
            raise ValueError('backup-original-node')
    for path, stamp in files:
        z = os.lstat(path)
        if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
                z.st_mode, z.st_uid, z.st_gid, z.st_nlink) != stamp:
            raise ValueError('backup-original-file')


def capture(roots, originals=None):
    files = dict(originals[0]) if originals is not None else {}
    nodes = dict(originals[1]) if originals is not None else {}
    spaces = {}; total = 0
    # All explicit roots and their ancestor originals precede first enumeration.
    for root in roots:
        stamp = nine(os.lstat(root))
        need(str(root) not in files or files[str(root)] == stamp, 'backup-root-conflict')
        files[str(root)] = stamp
        for parent in root.parents:
            value = five(os.lstat(parent))
            need(value[2] & 0o170000 == 0o040000, 'backup-parent-type')
            need(str(parent) not in nodes or nodes[str(parent)] == value, 'backup-parent-conflict')
            nodes[str(parent)] = value

    def walk(path):
        nonlocal total
        value = nine(os.lstat(path))
        need(str(path) not in files or files[str(path)] == value, 'backup-leaf-conflict')
        if str(path) in files and str(path) in spaces:
            return
        first = str(path) not in files
        files[str(path)] = value
        kind = value[5] & 0o170000
        need(kind in (0o100000, 0o040000), 'backup-source-kind')
        if kind == 0o040000:
            node = (value[0], value[1], value[5], value[6], value[7])
            need(str(path) not in nodes or nodes[str(path)] == node, 'backup-directory-conflict')
            nodes[str(path)] = node
            names = tuple(sorted(os.listdir(path))); spaces[str(path)] = names
            for name in names:
                walk(path / name)
        else:
            need(value[8] == 1, 'backup-source-alias')
            if first:
                total += value[2]
        need(len(files) <= MAX_ENTRIES and total <= MAX_BYTES, 'backup-fixed-bounds')
    for root in roots:
        walk(root)
    # Explicit file roots were pre-captured and must still count once.
    total = sum(value[2] for value in files.values() if value[5] & 0o170000 == 0o100000)
    need(total <= MAX_BYTES, 'backup-byte-bound')
    frame = (tuple(sorted(files.items())), tuple(sorted(nodes.items())), tuple(sorted(spaces.items())))
    raw(frame)
    return frame, total


def read_hash(path, original, deadline):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        need(nine(os.fstat(fd)) == original, 'backup-source-FD')
        digest = hashlib.sha256(); size = 0
        while True:
            need(time.monotonic() < deadline, 'backup-deadline')
            chunk = os.read(fd, 1024 ** 2)
            if not chunk:
                break
            digest.update(chunk); size += len(chunk)
        need(size == original[2] and nine(os.fstat(fd)) == original,
             'backup-source-read-drift')
        return digest.hexdigest()
    finally:
        os.close(fd)


def load_primitives(path, original_frame, *, expected_sha=PRIMITIVES_SHA256):
    originals = dict(original_frame[0]); path = Path(path)
    original = originals[str(path)]
    need(original[5] & 0o170000 == 0o100000 and original[8] == 1 and original[2] <= 1024 ** 2,
         'backup-algorithm-kind')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        need(nine(os.fstat(fd)) == original, 'backup-algorithm-FD')
        data = b''
        while chunk := os.read(fd, 1024 ** 2):
            data += chunk
        need(nine(os.fstat(fd)) == original and
             hashlib.sha256(data).hexdigest() == expected_sha, 'backup-algorithm-pin')
    finally:
        os.close(fd)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader('standalone_neutral_backup', loader=None))
    module.__file__ = str(path)
    exec(compile(data, str(path), 'exec'), module.__dict__)
    methods=tuple((name,function,function.__code__,function.__defaults__,function.__kwdefaults__,
                   None if function.__kwdefaults__ is None else tuple((key,type(value),value) for key,value in sorted(function.__kwdefaults__.items())))
                  for name,function in vars(module).items()
                  if type(function).__name__=='function' and function.__globals__ is vars(module))
    constants=tuple((name,vars(module)[name]) for name in ('MAX_FILES','MAX_MANIFEST','MAX_BYTES','DEADLINE','Held') +
                    (('APPDATA_ONLY','APPDATA_MAX_INDEX','APPDATA_MAX_FILE','APPDATA_MAX_NODES','APPDATA_MEDIA_SUFFIXES','APPDATA_MAGIC')
                     if hasattr(module,'APPDATA_ONLY') else ()))
    _PRIMITIVES[module]=(_PRIMITIVES,methods,constants)
    raw(original_frame)
    _primitive_original(module)
    return module


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


def _witness(value,expected=None):
    original=_BACKUP_SEALS.get(value)
    if type(original) is not tuple or len(original)!=5:raise ValueError('backup-original-persistent-seal')
    state,table,seals,logical,primitive=original
    if (_OBSERVATIONS is not table or _BACKUP_SEALS is not seals or table.get(value) is not state
            or (expected is not None and original is not expected) or _projection(state)!=logical):
        raise ValueError('backup-original-persistent-custody')
    _primitive_original(state['module'],primitive)
    return original



class BackupObservation:
    __slots__ = ('__weakref__',)

    def __init__(self, *args, **kwargs):
        raise ValueError('Original in-process backup observation required')

    def close(self, sources=True):
        if type(sources) is not bool:raise ValueError('backup-close-mode')
        persistent=_witness(self);state=persistent[0]
        need(state is not None and state['pid'] == os.getpid() and
             state['thread'] == threading.get_ident(), 'backup-original-owner')
        seal = state
        owner_original = (state['pid'], state['thread'], state['deadline'])
        summary_original = (state['bytes'], state['digest'])
        source_database_original = tuple((path, json.loads(encode(logical))) for path, logical in state['source_databases'])
        database_original = tuple((path, json.loads(encode(logical))) for path, logical in state['databases'])
        frames = (state['copies'], state['code']) + ((state['source'],) if sources else ())
        source_content = tuple(state['source_content']); content = tuple(state['content'])
        module = state['module']; database_function = module.database;primitive=persistent[4]
        need(time.monotonic() < state['deadline'], 'backup-deadline')
        for path, original_hash, original_attrs in content:
            need(attributes(path) == original_attrs, 'backup-copy-content')
        if sources:
            for path, digest, attrs in source_content:
                need(attributes(path) == attrs, 'backup-source-content')
        result = dict(kind='standalone-private-backup-v1', roles=list(ROLES),
                      bytes=state['bytes'], entries=len(state['source'][0]),
                      digest=state['digest'], ordinary_import=False, cleanup=False,
                      index=False, resume=False, replay=False)
        _witness(self,persistent)
        for frame in frames:
            raw(frame)
        current_owner = (os.getpid(), threading.get_ident())
        # Complete primitive final closure after all hashing/database/result helpers.
        for files, nodes, spaces in frames:
            for path, names in spaces:
                if tuple(sorted(os.listdir(path))) != names:
                    raise ValueError('backup-final-namespace')
            for path, stamp in nodes:
                z = os.lstat(path)
                if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != stamp:
                    raise ValueError('backup-final-node')
            for path, stamp in files:
                z = os.lstat(path)
                if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
                        z.st_mode, z.st_uid, z.st_gid, z.st_nlink) != stamp:
                    raise ValueError('backup-final-file')
        if state.get('restic') is not None:
            witness = state['restic']
            for path, descriptor, original, _ in witness['restore_custody']:
                z = os.fstat(descriptor)
                if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,
                        z.st_uid,z.st_gid,z.st_nlink) != tuple(original):
                    raise ValueError('backup-original-restored-node-FD')
            for path, descriptor, original in (*witness['output_ancestors'], *witness['mount_custody']):
                z = os.fstat(descriptor); current = os.lstat(path)
                if ((z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid) != tuple(original) or
                        (current.st_dev,current.st_ino,current.st_mode,current.st_uid,current.st_gid) != tuple(original)):
                    raise ValueError('backup-original-Restic-ancestor-FD')
            z = os.fstat(witness['snapshot_fd'])
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,
                    z.st_uid,z.st_gid,z.st_nlink) != tuple(witness['snapshot_signature9']):
                raise ValueError('backup-original-Restic-snapshot-FD')
        if (_OBSERVATIONS.get(self) is not seal or (seal['pid'], seal['thread'], seal['deadline']) != owner_original
                or seal['module'] is not module or module.database is not database_function
                or (seal['copies'], seal['code']) + ((seal['source'],) if sources else ()) != frames
                or tuple(seal['content']) != content or tuple(seal['source_content']) != source_content
                or tuple(seal['databases']) != database_original or tuple(seal['source_databases']) != source_database_original
                or (seal['bytes'], seal['digest']) != summary_original
                or owner_original[:2] != current_owner):
            raise ValueError('backup-final-owner')
        # Inline primitive projection: no replaceable checker/serializer runs after
        # the physical tail and before original-table/entry comparison.
        pending=[state];observed=[]
        while pending:
            item=pending.pop();kind=type(item)
            if kind is dict:
                keys=tuple(sorted(item));observed.append(('dict',keys));pending.extend(item[k] for k in reversed(keys))
            elif kind in (list,tuple):
                observed.append((kind.__name__,len(item)));pending.extend(reversed(item))
            elif kind in (str,int,float,bool,bytes,type(None)):
                observed.append((kind.__name__,item))
            else:observed.append(('identity',id(kind),id(item)))
        primitive=persistent[4]
        if _PRIMITIVES is not primitive[0] or _PRIMITIVES.get(state['module']) is not primitive:
            raise ValueError('backup-original-final-primitive-registry')
        for name,function,code,defaults,kwdict,kwdefaults in primitive[1]:
            current=vars(state['module']).get(name)
            if (current is not function or current.__code__ is not code or current.__defaults__ is not defaults
                    or current.__kwdefaults__ is not kwdict
                    or (kwdict is not None and (len(kwdict)!=len(kwdefaults) or any(type(key) is not str for key in kwdict)
                        or any(key not in kwdict or type(kwdict[key]) is not kind or kwdict[key]!=value for key,kind,value in kwdefaults)))):
                raise ValueError('backup-original-final-primitive-callable')
        for name,wanted in primitive[2]:
            current=vars(state['module']).get(name)
            if type(current) is not type(wanted) or current!=wanted:raise ValueError('backup-original-final-primitive-constant')
        if (tuple(observed)!=persistent[3] or _OBSERVATIONS is not persistent[1]
                or _BACKUP_SEALS is not persistent[2] or _OBSERVATIONS.get(self) is not state
                or _BACKUP_SEALS.get(self) is not persistent
                or time.monotonic()>=owner_original[2]):raise ValueError('backup-original-final-custody')
        return result

    def original_source_frame(self):
        """Copied original preservation facts; no mutation or ready authority."""
        persistent=_witness(self);state=persistent[0]
        if state is None:
            raise ValueError('backup-original-frame-owner')
        original = state['source']; owner = (state['pid'],state['thread'],state['deadline'])
        current_owner = (os.getpid(),threading.get_ident())
        self.close_copies()
        if (_OBSERVATIONS.get(self) is not state or state['source'] != original or
                (state['pid'],state['thread'],state['deadline']) != owner or
                owner[:2] != current_owner):
            raise ValueError('backup-original-frame-final')
        _witness(self,persistent)
        return original

    def close_copies(self):
        return self.close(sources=False)


def _restic_copy_and_verify(scopes, roots, out, source, source_content, code_original,
                            module, primitive, deadline, parent_original9, parent_names,
                            requested_scopes, scope_original):
    """Preserve four original roles while transporting only application data."""
    original_files = dict(source[0])
    selected_scopes = []
    required = []
    for role, scope, root in zip(('native_config', 'reader_config'), scopes[:2], roots[:2]):
        records, _ = _primitive_call(module, primitive, 'inventory', root, 'tree', deadline=deadline)
        for record in records:
            path = str(root if record['path'] == '.' else root / record['path'])
            need(tuple(record['stamp']) == original_files[path], 'backup-inventory-original')
        selected_scopes.append(dict(role=role, root=str(root), records=records))
        required.extend(role + ':' + relative for relative in scope['databases'])
    index = _primitive_call(module, primitive, 'appdata_make_index', selected_scopes, deadline=deadline)
    selection = _primitive_call(module, primitive, 'appdata_policy_frozen', index)
    values = _primitive_call(module, primitive, 'appdata_policy_value', index)
    binding = _primitive_call(module, primitive, 'appdata_restic_profile', deadline=deadline)
    cache = Path(binding['mounts']['/cache'])
    largest = max((row['stamp'][2] for scope in values['scopes'] for row in scope['records']
                   if row['kind'] == 'file' and not row['media']), default=0)
    space = os.statvfs(cache)
    need(space.f_bavail * space.f_frsize >= 4 * largest + 1024**2, 'backup-app-SQL-scratch-capacity')
    source_views = [dict(name=row['role'], path=row['root'], kind='tree', records=row['records'])
                    for row in selected_scopes]
    prior_scratch = tempfile.tempdir
    try:
        tempfile.tempdir = str(cache)
        sql = _primitive_call(module, primitive, 'database_rows', source_views, required, deadline=deadline)
    finally:
        tempfile.tempdir = prior_scratch
    source_databases = []
    for key, logical in sql.items():
        role, relative = key.split(':', 1)
        root = next(Path(row['root']) for row in selected_scopes if row['role'] == role)
        source_databases.append((str(root / relative), logical))
    raw(source); raw(code_original)
    need(nine(os.lstat(out.parent)) == parent_original9 and
         tuple(sorted(os.listdir(out.parent))) == parent_names and not os.path.lexists(out),
         'backup-output-parent-drift')
    witness = None
    cleanup_records = ()
    success = False
    try:
        witness = _primitive_call(module, primitive, 'appdata_restic_backup', index, out, deadline=deadline)
        cleanup_records = tuple((fd, tuple(frame)) for _, fd, frame, _ in witness['restore_custody']) + \
                          tuple((fd, tuple(frame)) for _, fd, frame in
                                (*witness['output_ancestors'], *witness['mount_custody'])) + \
                          ((witness['snapshot_fd'], tuple(witness['snapshot_signature9'])),)
        need(witness['binding'] == binding and witness['selection'] == selection ==
             _primitive_call(module, primitive, 'appdata_policy_frozen', index), 'backup-original-app-selection')
        _primitive_call(module, primitive, 'appdata_close_restore', witness['restore_custody'])
        restored = []
        content = []
        for scope in values['scopes']:
            root = out / 'restore' / scope['role']
            records, _ = _primitive_call(module, primitive, 'inventory', root, 'tree',
                                          detached=True, deadline=deadline)
            expected = [{key: value for key, value in row.items() if key not in ('stamp', 'media')}
                        for row in scope['records'] if not row['media']]
            need(_primitive_call(module, primitive, 'copied_records_match', records, expected),
                 'backup-restic-app-content')
            restored.append(dict(name=scope['role'], path=str(root), kind='tree', records=records))
            for row in expected:
                if row['kind'] == 'file':
                    attrs = tuple((key, bytes.fromhex(value)) for key, value in sorted(row['attributes']['xattrs'].items()))
                    content.append((str(root / row['path']), row['sha256'], attrs))
        prior_scratch = tempfile.tempdir
        try:
            tempfile.tempdir = str(cache)
            need(_primitive_call(module, primitive, 'database_rows', restored, required,
                                 deadline=deadline) == sql, 'backup-restic-detached-database')
        finally:
            tempfile.tempdir = prior_scratch
        databases = []
        for key, logical in sql.items():
            role, relative = key.split(':', 1)
            databases.append((str(out / 'restore' / role / relative), logical))
        _primitive_call(module, primitive, 'appdata_close_restore', witness['restore_custody'])
        _primitive_call(module, primitive, 'appdata_close_ancestors', witness['output_ancestors'])
        _primitive_call(module, primitive, 'appdata_close_ancestors', witness['mount_custody'])
        snapshot = Path(witness['snapshot_path'])
        born = witness['restore_custody']
        nodes = dict((path, tuple(frame)) for path, _, frame in witness['output_ancestors'])
        nodes.update((str(path), five(os.lstat(path))) for path in snapshot.parents)
        copied = (tuple((path, tuple(frame)) for path, _, frame, _ in born) +
                  ((str(snapshot), tuple(witness['snapshot_signature9'])),),
                  tuple(sorted(nodes.items())),
                  tuple((path, tuple(names)) for path, _, _, names in born if names is not None))
        snapshot_attrs = tuple((key, bytes.fromhex(value)) for key, value in
                               sorted(witness['snapshot_attributes']['xattrs'].items()))
        content.append((str(snapshot), witness['snapshot_id'], snapshot_attrs))
        raw(source); raw(copied); raw(code_original)
        _primitive_original(module, primitive)
        digest = hashlib.sha256(encode(dict(source=source, copies=copied, restic=witness,
                                            databases=databases, source_databases=source_databases))).hexdigest()
        observation = object.__new__(BackupObservation)
        state = dict(pid=os.getpid(), thread=threading.get_ident(), deadline=deadline,
                     source=source, copies=copied, code=code_original, module=module,
                     source_content=source_content, source_databases=source_databases,
                     content=content, databases=databases, bytes=witness['app_bytes'],
                     digest=digest, restic=witness)
        _OBSERVATIONS[observation] = state
        _BACKUP_SEALS[observation] = (state, _OBSERVATIONS, _BACKUP_SEALS, _projection(state), primitive)
        observation.close()
        if (type(requested_scopes) is not list or len(requested_scopes) != 4 or
                any(type(row) is not dict or set(row) != {'role','root','databases'} or
                    type(row['role']) is not str or type(row['root']) is not str or type(row['databases']) is not list or
                    any(type(item) is not str for item in row['databases']) for row in requested_scopes) or
                tuple((row['role'],row['root'],tuple(row['databases'])) for row in requested_scopes) != scope_original):
            raise ValueError('backup-original-request')
        success = True
        return observation
    finally:
        if not success:
            for descriptor, original in cleanup_records:
                try:
                    current = os.fstat(descriptor)
                except OSError:
                    continue
                if (current.st_dev,current.st_ino,current.st_mode & 0o170000) == \
                        (original[0],original[1],original[5 if len(original)==9 else 2] & 0o170000):
                    os.close(descriptor)


def copy_and_verify(scopes, out, *, deadline=None, restic_appdata=False):
    """Neutral preservation only; a live parent must separately own quiescence."""
    if type(restic_appdata) is not bool:
        raise ValueError('backup-copy-mode')
    # Syntactic access only precedes the complete explicit-root original capture.
    if (type(scopes) is not list or len(scopes) != 4 or
            any(type(row) is not dict or set(row) != {'role','root','databases'} or
                type(row['root']) is not str or type(row['role']) is not str or
                type(row['databases']) is not list or any(type(value) is not str for value in row['databases']) for row in scopes)):
        raise ValueError('backup-role-initial-schema')
    requested_scopes = scopes
    scope_original = tuple((row['role'],row['root'],tuple(row['databases'])) for row in scopes)
    scopes = [dict(role=role,root=root,databases=list(databases)) for role,root,databases in scope_original]
    out = Path(out)
    z = os.lstat(out.parent)
    parent_original9 = (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
    parent_original = (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
    primitive_path = Path(__file__).with_name('comic_appdata_restic_primitives.py' if restic_appdata
                                              else 'comic_reader_backup_primitives.py')
    code_paths = (Path(__file__).absolute(), primitive_path)
    early_code_files = []; early_code_nodes = {}
    for path in code_paths:
        z = os.lstat(path)
        early_code_files.append((str(path),(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)))
        for parent in path.parents:
            z = os.lstat(parent); value = (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
            if str(parent) in early_code_nodes and early_code_nodes[str(parent)] != value:
                raise ValueError('backup-code-ancestor-initial-conflict')
            early_code_nodes[str(parent)] = value
    code_original = (tuple(early_code_files),tuple(sorted(early_code_nodes.items())),())
    early_files = {}; early_nodes = {}
    for row in scopes:
        path = Path(row['root'])
        z = os.lstat(path)
        stamp = (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,
                 z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
        if str(path) in early_files and early_files[str(path)] != stamp:
            raise ValueError('backup-root-initial-conflict')
        early_files[str(path)] = stamp
        for parent in path.parents:
            z = os.lstat(parent); value = (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
            if str(parent) in early_nodes and early_nodes[str(parent)] != value:
                raise ValueError('backup-parent-initial-conflict')
            early_nodes[str(parent)] = value
    early_originals = (tuple(sorted(early_files.items())),tuple(sorted(early_nodes.items())),())
    need(type(scopes) is list and len(scopes) == 4, 'backup-role-count')
    need(all(type(row) is dict and set(row) == {'role', 'root', 'databases'} for row in scopes), 'backup-role-schema')
    need(tuple(row['role'] for row in scopes) == ROLES, 'backup-role-order')
    roots = []
    for index, row in enumerate(scopes):
        need(type(row['root']) is str and type(row['databases']) is list, 'backup-role-fields')
        root = Path(row['root'])
        need(root.is_absolute() and str(root) == row['root'], 'backup-root-spelling')
        stamp = nine(os.lstat(root))
        need(stamp[5] & 0o170000 == (0o040000 if index < 2 else 0o100000), 'backup-role-kind')
        if index >= 2:
            need(stamp[8] == 1 and stamp[2] <= MAX_ARCHIVE_BYTES and not row['databases'], 'backup-archive-bound')
        for relative in row['databases']:
            need(type(relative) is str and relative and not Path(relative).is_absolute() and
                 '..' not in Path(relative).parts and str(Path(relative)) == relative, 'backup-database-path')
        roots.append(root)
    need(roots[0] != roots[1] and not roots[0].is_relative_to(roots[1]) and
         not roots[1].is_relative_to(roots[0]), 'backup-state-overlap')
    need(roots[2] != roots[3], 'backup-archive-overlap')
    need(all(not root.is_relative_to(roots[1]) for root in roots[2:]), 'backup-reader-archive-overlap')
    need(out.is_absolute() and not os.path.lexists(out) and
         all(not out.is_relative_to(root) and not root.is_relative_to(out) for root in roots), 'backup-output-overlap')
    need(parent_original[2] & 0o170000 == 0o040000 and parent_original[2] & 0o7777 == 0o700 and
         parent_original[3] == os.geteuid(), 'backup-output-private-parent')
    local_deadline = time.monotonic() + BACKUP_SECONDS
    if deadline is not None:
        need(type(deadline) in (int,float) and math.isfinite(deadline), 'backup-deadline-type')
    deadline = local_deadline if deadline is None else min(deadline, local_deadline)
    need(time.monotonic() < deadline, 'backup-original-deadline')
    source, _ = capture(roots, early_originals)
    parent_names = tuple(sorted(os.listdir(out.parent)))
    need(nine(os.lstat(out.parent)) == parent_original9, 'backup-output-parent-initial')
    raw(source)
    total = sum(stamp[2] for root in roots for path, stamp in source[0]
                if stamp[5] & 0o170000 == 0o100000 and Path(path).is_relative_to(root))
    need(total <= MAX_BYTES, 'backup-all-role-byte-bound')
    capacity = os.statvfs(out.parent)
    if not restic_appdata:
        need(capacity.f_bavail * capacity.f_frsize >= 2 * total + 1024 ** 2, 'backup-two-copy-space')
    raw(source); raw(code_original)
    module = (load_primitives(primitive_path, code_original, expected_sha=APPDATA_PRIMITIVES_SHA256)
              if restic_appdata else load_primitives(primitive_path, code_original))
    primitive=_primitive_original(module)
    source_content = []; source_databases = []
    original_files = dict(source[0])
    for path, stamp in source[0]:
        if stamp[5] & 0o170000 == 0o100000:
            source_content.append((path, read_hash(path, stamp, deadline), attributes(path)))
    if restic_appdata:
        observation = _restic_copy_and_verify(scopes, roots, out, source, source_content,
                                             code_original, module, primitive, deadline,
                                             parent_original9, parent_names, requested_scopes, scope_original)
        return observation
    for row, root in zip(scopes[:2], roots[:2]):
        for relative in row['databases']:
            path = root / relative
            need(str(path) in original_files, 'backup-database-original')
            source_databases.append((str(path), _primitive_call(module,primitive,'database',path,deadline=deadline)))
    raw(source); raw(code_original)
    need(nine(os.lstat(out.parent)) == parent_original9 and
         tuple(sorted(os.listdir(out.parent))) == parent_names and not os.path.lexists(out), 'backup-output-parent-drift')
    created_files = {}; created_nodes = {}; created_directories = {}; created_spaces = {}; content = []; databases = []

    def check_created():
        for path, names in created_spaces.items():
            need(tuple(sorted(os.listdir(path))) == names, 'backup-created-namespace')
        for path, stamp in created_nodes.items():
            need(five(os.lstat(path)) == stamp, 'backup-created-node')
        for path, stamp in (*created_files.items(), *created_directories.items()):
            need(nine(os.lstat(path)) == stamp, 'backup-created-file')

    def close_owned(fd, identity):
        # FD numbers may be reused by a declared callback. Never close foreign identity.
        try:
            current = os.fstat(fd)
        except OSError as error:
            if error.errno == 9:
                return False
            raise
        if (current.st_dev, current.st_ino, current.st_mode & 0o170000) != identity:
            return False
        os.close(fd)
        return True

    def parent_fd(path):
        parent = str(path.parent)
        prior = created_directories[parent] if parent in created_directories else parent_original9
        names = created_spaces[parent] if parent in created_spaces else parent_names
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        opened = os.fstat(fd)
        identity = (opened.st_dev, opened.st_ino, opened.st_mode & 0o170000)
        try:
            need(_directory_names(fd) == names, 'backup-parent-namespace')
            # Complete original parent closes after namespace/open helpers, before creation.
            need(nine(os.fstat(fd)) == prior and nine(os.lstat(path.parent)) == prior,
                 'backup-parent-original')
        except BaseException:
            close_owned(fd, identity); raise
        return fd, prior, names

    def inserted(path, fd, prior, names, directory):
        # Capture only the source-owned exclusive insertion before stream/fsync callbacks.
        after = nine(os.fstat(fd))
        need((after[0],after[1],after[5],after[6],after[7]) ==
             (prior[0],prior[1],prior[5],prior[6],prior[7]) and
             after[8] == (prior[8] if prior[8] == 1 else prior[8] + int(directory)), 'backup-owned-directory-transition')
        parent = str(path.parent)
        if parent in created_directories:
            created_directories[parent] = after
            created_spaces[parent] = tuple(sorted((*names, path.name)))
        need(_directory_names(fd) == tuple(sorted((*names,path.name))) and
             nine(os.fstat(fd)) == after and nine(os.lstat(path.parent)) == after,
             'backup-owned-insertion-final')

    def directory(path):
        fd, prior, names = parent_fd(path)
        try:
            os.mkdir(path.name, 0o700, dir_fd=fd)
            original9 = nine(os.stat(path.name, dir_fd=fd, follow_symlinks=False))
            value = (original9[0],original9[1],original9[5],original9[6],original9[7])
            need(value[2] & 0o170000 == 0o040000 and value[2] & 0o7777 == 0o700 and value[3] == os.geteuid() and
                 original9[8] in (1,2) and original9[0] == prior[0] and (original9[8] == 1) == (prior[8] == 1), 'backup-created-directory')
            created_nodes[str(path)] = value; created_directories[str(path)] = original9; created_spaces[str(path)] = ()
            inserted(path, fd, prior, names, True)
            child = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                need(nine(os.fstat(child)) == original9 and _directory_names(child) == (), 'backup-created-directory-FD')
                os.fsync(child)
                need(nine(os.fstat(child)) == original9 and nine(os.lstat(path)) == original9, 'backup-created-directory-sync')
            finally:
                os.close(child)
        finally:
            os.close(fd)
        check_created()

    def copy_file(source_path, destination, original, digest, attrs):
        check_created(); raw(source)
        # Every acquired FD is under cleanup before the next open/helper.
        incoming = None; parent = None; outgoing = None
        incoming_identity = None; parent_identity = None; outgoing_identity = None
        finished = False; lost = False
        try:
            incoming = os.open(source_path, os.O_RDONLY | os.O_NOFOLLOW)
            acquired = os.fstat(incoming)
            incoming_identity = (acquired.st_dev, acquired.st_ino, acquired.st_mode & 0o170000)
            parent, prior, names = parent_fd(destination)
            parent_identity = (prior[0], prior[1], prior[5] & 0o170000)
            outgoing = os.open(destination.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            acquired = os.fstat(outgoing)
            outgoing_identity = (acquired.st_dev, acquired.st_ino, acquired.st_mode & 0o170000)
            initial = nine(acquired)
            inserted(destination, parent, prior, names, False)
            if not close_owned(parent, parent_identity):
                raise ValueError("backup-parent-FD-ownership")
            parent = None
            need(initial[5] & 0o170000 == 0o100000 and initial[5] & 0o7777 == 0o600 and
                 initial[6] == os.geteuid() and initial[8] == 1 and initial[2] == 0,
                 'backup-created-file-security')
            need(nine(os.fstat(incoming)) == original, 'backup-copy-source-FD')
            initial_attrs = dict(descriptor_attributes(outgoing))
            acl = initial_attrs.get('system.nfs4_acl')
            private_acl = _primitive_call(module, primitive, 'mode_nfs4_acl', 0o600, 'file')
            need(dict(attrs).get('system.nfs4_acl') in (None, private_acl),
                 'backup-private-source-nfs4-acl')
            need(acl in (None, private_acl), 'backup-created-file-ACL')
            need(nine(os.fstat(outgoing)) == initial, 'backup-created-file-initial-FD')
            observed = hashlib.sha256(); count = 0
            while chunk := os.read(incoming, 1024 ** 2):
                need(time.monotonic() < deadline, 'backup-deadline')
                observed.update(chunk); count += len(chunk)
                offset = 0
                while offset < len(chunk):
                    written = os.write(outgoing, chunk[offset:]); need(written > 0, 'backup-copy-write'); offset += written
            for name, value in attrs:
                if name == 'system.nfs4_acl' and initial_attrs.get(name) == value:
                    continue
                os.setxattr(outgoing, name, value)
            copied_attrs = descriptor_attributes(outgoing)
            # Copies intentionally retain the private creation mode/owner, not
            # source permissions. Only the checked server ACL transport differs.
            expected_attrs = dict(mode=0o600, uid=initial[6], gid=initial[7],
                                  xattrs={name:value.hex() for name,value in attrs})
            actual_attrs = dict(expected_attrs, xattrs={name:value.hex() for name,value in copied_attrs})
            need(_primitive_call(module, primitive, 'copied_attributes_match', actual_attrs, expected_attrs, 'file'),
                 'backup-created-file-attributes')
            os.fsync(outgoing)
            final = nine(os.fstat(outgoing))
            need((final[0], final[1], final[5], final[6], final[7], final[8]) ==
                 (initial[0], initial[1], initial[5], initial[6], initial[7], initial[8]) and
                 final[2] == count == original[2] and observed.hexdigest() == digest and
                 nine(os.lstat(destination)) == final and nine(os.fstat(incoming)) == original,
                 'backup-created-file-drift')
            created_files[str(destination)] = final
            content.append((str(destination), digest, copied_attrs))
            finished = True
        finally:
            try:
                if outgoing is not None and outgoing_identity is not None:
                    lost = not close_owned(outgoing, outgoing_identity) or lost
            finally:
                try:
                    if parent is not None and parent_identity is not None:
                        lost = not close_owned(parent, parent_identity) or lost
                finally:
                    if incoming is not None and incoming_identity is not None:
                        lost = not close_owned(incoming, incoming_identity) or lost
            if finished and lost:
                raise ValueError("backup-copy-FD-ownership")
        check_created()

    directory(out)
    for phase in ('backup', 'restore'):
        phase_root = out / phase; directory(phase_root)
        for role, root in zip(ROLES, roots):
            role_root = phase_root / role
            if original_files[str(root)][5] & 0o170000 == 0o100000:
                item = next(item for item in source_content if item[0] == str(root))
                copy_file(root, role_root, original_files[str(root)], item[1], item[2])
            else:
                directory(role_root)
                for path, stamp in source[0]:
                    relative = Path(path).relative_to(root) if Path(path).is_relative_to(root) else None
                    if relative is None or str(relative) == '.':
                        continue
                    target = role_root / relative
                    if stamp[5] & 0o170000 == 0o040000:
                        check_created(); directory(target)
                    else:
                        item = next(item for item in source_content if item[0] == path)
                        copy_file(Path(path), target, stamp, item[1], item[2])
        for row, root in zip(scopes[:2], roots[:2]):
            for relative in row['databases']:
                destination = phase_root / row['role'] / relative
                logical = dict(source_databases)[str(root / relative)]
                need(_primitive_call(module,primitive,'database',destination,deadline=deadline) == logical, 'backup-detached-readback')
                databases.append((str(destination), logical))
        check_created(); raw(source); raw(code_original)
    # No refreshed leaf or directory incarnation is used to establish copies.
    copied = (tuple(sorted((*created_files.items(), *created_directories.items()))), tuple(sorted(created_nodes.items())), tuple(sorted(created_spaces.items())))
    # Publish only after actual independent copy readback. Later closure checks
    # reuse this in-memory proof against the exact original frames and attrs;
    # they never rebase a copy or hydrate verification from a saved receipt.
    copied_files=dict(copied[0])
    for path,expected_hash,expected_attrs in content:
        need(read_hash(path,copied_files[path],deadline)==expected_hash
             and attributes(path)==expected_attrs,'backup-copy-content')
    raw(copied);raw(source);raw(code_original)
    _primitive_original(module,primitive)
    digest = hashlib.sha256(encode(dict(source=source, copies=copied, content=[(p, h) for p, h, _ in content], databases=databases))).hexdigest()
    observation = object.__new__(BackupObservation)
    _OBSERVATIONS[observation] = dict(pid=os.getpid(), thread=threading.get_ident(), deadline=deadline,
                                    source=source, copies=copied, code=code_original, module=module,
                                    source_content=source_content, source_databases=source_databases,
                                    content=content, databases=databases, bytes=total, digest=digest)
    state=_OBSERVATIONS[observation]
    _BACKUP_SEALS[observation]=(state,_OBSERVATIONS,_BACKUP_SEALS,_projection(state),primitive)
    observation.close()
    if (type(requested_scopes) is not list or len(requested_scopes)!=4 or
            any(type(row) is not dict or set(row)!={'role','root','databases'} or
                type(row['role']) is not str or type(row['root']) is not str or type(row['databases']) is not list or
                any(type(item) is not str for item in row['databases']) for row in requested_scopes) or
            tuple((row['role'],row['root'],tuple(row['databases'])) for row in requested_scopes) != scope_original):
        raise ValueError('backup-original-request')
    return observation
