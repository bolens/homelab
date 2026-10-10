"""Durable archive observations. Saved history never grants import or custody."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import time
import threading

from mylar import publication_archive_owned as o

NAME = 'archive-history-v1'
KINDS = ('prepared', 'execute-observed', 'terminal-observed', 'rollback-observed')
MAX_RECORDS = 32
MAX_BYTES = 8 * 1024**2


def nine(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns,
            value.st_ctime_ns, value.st_mode, value.st_uid, value.st_gid, value.st_nlink)


def five(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid)


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode()


def decode(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            o.check(key not in value, 'archive-history-duplicate-key')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: o.check(False, 'archive-history-number'))


def _early(controller):
    """Read the fixed journal before SDK/owner/verifier callbacks; no saved grant."""
    path = Path(controller.root) / NAME
    nodes = []
    for current in (path.parent, *path.parent.parents):
        info = os.lstat(current)
        nodes.append((str(current), (info.st_dev, info.st_ino, info.st_mode,
                                     info.st_uid, info.st_gid)))
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return {'files9': [], 'nodes5': nodes, 'namespaces': [],
                'absent': [str(path)], 'claims': []}
    if (info.st_mode & 0o170000 != 0o040000 or info.st_mode & 0o7777 != 0o700
            or (info.st_uid, info.st_gid) != (os.geteuid(), os.getegid())):
        raise o.Held('archive-history-early-directory')
    nodes.append((str(path), (info.st_dev, info.st_ino, info.st_mode,
                             info.st_uid, info.st_gid)))
    names = tuple(sorted(os.listdir(path)))
    if len(names) > MAX_RECORDS:
        raise o.Held('archive-history-early-bound')
    files = []
    size = 0
    for name in names:
        current = path / name
        info = os.lstat(current)
        stamp = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
                 info.st_ctime_ns, info.st_mode, info.st_uid, info.st_gid, info.st_nlink)
        if (info.st_mode & 0o170000 != 0o100000 or info.st_mode & 0o7777 != 0o600
                or (info.st_uid, info.st_gid, info.st_nlink) != (os.geteuid(), os.getegid(), 1)):
            raise o.Held('archive-history-early-leaf')
        size += info.st_size
        if size > MAX_RECORDS * MAX_BYTES:
            raise o.Held('archive-history-early-byte-bound')
        files.append((str(current), stamp))
    hashes = []
    for current, stamp in files:
        fd = os.open(current, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            actual = (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,
                      info.st_mode,info.st_uid,info.st_gid,info.st_nlink)
            if actual != stamp:
                raise o.Held('archive-history-early-fd')
            digest = hashlib.sha256()
            remaining = stamp[2]
            while remaining:
                block = os.read(fd, min(remaining, 1024*1024))
                if not block:
                    raise o.Held('archive-history-early-short-read')
                digest.update(block);remaining -= len(block)
            if os.read(fd,1):
                raise o.Held('archive-history-early-size')
            info = os.fstat(fd)
            actual = (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,
                      info.st_mode,info.st_uid,info.st_gid,info.st_nlink)
            if actual != stamp:
                raise o.Held('archive-history-early-read-drift')
            hashes.append((current,digest.hexdigest()))
        finally:
            os.close(fd)
    return {'files9': files, 'nodes5': nodes, 'namespaces': [(str(path), names)],
            'absent': [], 'claims': [], '_hashes': hashes}


def _carry(vectors, early):
    # Conflict refusal comes from original_vectors; retain the FIRST admission.
    close(early)
    originals = dict(early['files9'])
    for current, digest in early.get('_hashes', ()):
        stamp = originals[current]
        raw = o.read_checked(Path(current), list(stamp), max(1, stamp[2]), time.monotonic()+120)
        o.check(hashlib.sha256(raw).hexdigest() == digest, 'archive-history-early-original-bytes')
    for field in ('files9', 'nodes5', 'absent', 'namespaces', 'claims'):
        vectors[field] = list(vectors[field]) + list(early[field])
    return vectors


def directory(controller, writer, *, initialize=False):
    first = _early(controller)
    modules = o.sdk()
    o.writer_pair(controller, writer, modules)
    root = o.canonical(controller.root)
    parents = {p: five(os.lstat(p)) for p in (root, *root.parents)}
    path = root / NAME
    if initialize:
        # Owning preflight only, before backup/custody proof lifetime.
        modules[2].ordinary_purpose(writer)
        close(first)
        try:
            os.mkdir(path, 0o700)
        except FileExistsError:
            pass
    path = o.canonical(path)
    info = os.lstat(path)
    o.check((info.st_mode & 0o170000) == 0o040000 and
            (info.st_mode & 0o7777) == 0o700 and
            (info.st_uid, info.st_gid) == (os.geteuid(), os.getegid()),
            'archive-history-private-directory')
    parents[path] = five(info)
    for p, vector in parents.items():
        o.check(five(os.lstat(p)) == vector, 'archive-history-original-parent')
    return path, parents


def initialize(controller, writer):
    """Explicit preflight; it must precede every protected backup/custody proof."""
    early = _early(controller)
    path, parents = directory(controller, writer, initialize=True)
    initialized_path = path
    early['absent'] = []  # This explicit preflight owns only the absent->created transition.
    close(early)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    child=None
    try:
        o.check(five(os.fstat(fd))==parents[path.parent],'archive-history-initialize-parent-fd')
        child=os.open(path.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
        o.check(five(os.fstat(child))==parents[path],'archive-history-initialize-directory-fd')
        os.fsync(child);os.fsync(fd)
    finally:
        if child is not None:os.close(child)
        os.close(fd)
    for p, vector in parents.items():
        info = os.lstat(p)
        if (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid) != vector:
            raise o.Held('archive-history-initialize-parent')
    for path, names in early['namespaces']:
        if tuple(sorted(os.listdir(path))) != tuple(names):
            raise o.Held('archive-history-original-census')
    for path, vector in early['nodes5']:
        s = os.lstat(path)
        if (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid) != tuple(vector):
            raise o.Held('archive-history-original-node')
    for path, vector in early['files9']:
        s = os.lstat(path)
        if (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns,
                s.st_mode, s.st_uid, s.st_gid, s.st_nlink) != tuple(vector):
            raise o.Held('archive-history-original-file')
    for path in early['absent']:
        try:
            os.lstat(path)
        except FileNotFoundError:
            continue
        raise o.Held('archive-history-original-absence')
    for path, vector in early['claims']:
        try:
            s = os.lstat(path)
        except FileNotFoundError:
            if vector is not None:
                raise o.Held('archive-history-original-claim')
            continue
        claim = (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid,
                 None if (s.st_mode & 0o170000) == 0o040000 else s.st_nlink)
        if claim != (None if vector is None else tuple(vector)):
            raise o.Held('archive-history-original-claim')

    return initialized_path


def close(vectors):
    # Helpers/serialization must run BEFORE this copied complete raw closure.
    for path, names in vectors['namespaces']:
        if tuple(sorted(os.listdir(path))) != tuple(names):
            raise o.Held('archive-history-original-census')
    for path, vector in vectors['nodes5']:
        s = os.lstat(path)
        if (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid) != tuple(vector):
            raise o.Held('archive-history-original-node')
    for path, vector in vectors['files9']:
        s = os.lstat(path)
        if (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns,
                s.st_mode, s.st_uid, s.st_gid, s.st_nlink) != tuple(vector):
            raise o.Held('archive-history-original-file')
    for path in vectors['absent']:
        try:
            os.lstat(path)
        except FileNotFoundError:
            continue
        raise o.Held('archive-history-original-absence')
    for path, vector in vectors['claims']:
        try:
            s = os.lstat(path)
        except FileNotFoundError:
            if vector is not None:
                raise o.Held('archive-history-original-claim')
            continue
        claim = (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid,
                 None if (s.st_mode & 0o170000) == 0o040000 else s.st_nlink)
        if claim != (None if vector is None else tuple(vector)):
            raise o.Held('archive-history-original-claim')


def original_vectors(value):
    o.check(type(value) is dict and set(value) ==
            {'files9', 'nodes5', 'absent', 'namespaces', 'claims'},
            'archive-history-complete-vectors')
    o.check(all(type(item) in (dict,list,tuple,set,frozenset) and len(item)<=4096 for item in value.values()),
            'archive-history-finite-vectors')
    original = {key: list(item.items()) if type(item) is dict else list(item)
                for key, item in value.items()}
    original = copy.deepcopy(original)
    for path in original['absent']:
        o.check(type(path) is str and Path(path).is_absolute() and '..' not in Path(path).parts,
                'archive-history-absence-path')
    for path, names in original['namespaces']:
        o.check(type(path) is str and Path(path).is_absolute() and '..' not in Path(path).parts
                and type(names) in (list,tuple,set,frozenset) and len(names)<=4096
                and all(type(name) is str and name not in ('.','..') and '/' not in name for name in names),
                'archive-history-finite-census')
    seen = {}
    for field, length in (('files9', 9), ('nodes5', 5), ('claims', 6)):
        for path, vector in original[field]:
            o.check(type(path) is str and Path(path).is_absolute() and '..' not in Path(path).parts,
                    'archive-history-vector-path')
            o.check(field == 'claims' and vector is None or
                    type(vector) in (list,tuple) and len(vector) == length and all(type(n) is int or
                        field == 'claims' and index == 5 and n is None and
                        vector[2] & 0o170000 == 0o040000
                        for index, n in enumerate(vector)),
                    'archive-history-vector-types')
            key = (field, path)
            o.check(key not in seen or seen[key] == vector,
                    'archive-history-vector-conflict')
            seen[key] = vector
    close(original)
    return original


def _append(controller, writer, owner, operation_id, kind, evidence, vectors):
    path, parents = directory(controller, writer)
    o.check(kind in KINDS and type(operation_id) is str and
            re.fullmatch('[0-9a-f]{64}', operation_id), 'archive-history-fixed-key')
    owner = o.sdk()[2].exact_owner(owner)
    names = tuple(sorted(os.listdir(path)))
    o.check(len(names) < MAX_RECORDS and all(re.fullmatch(
        '[0-9a-f]{64}\\.(prepared|execute-observed|terminal-observed|rollback-observed)\\.json',
        n) for n in names), 'archive-history-bounded-census')
    name = operation_id + '.' + kind + '.json'
    o.check(name not in names, 'archive-history-exclusive-no-replay')
    # Existing journal leaves are original controls, not a census-only promise.
    prior = []
    for entry in names:
        target = path / entry
        stamp = nine(os.lstat(target))
        o.check(stamp[5] & 0o170000 == 0o100000 and stamp[5] & 0o7777 == 0o600
                and stamp[6:9] == (os.geteuid(), os.getegid(), 1),
                'archive-history-existing-leaf')
        prior.append((str(target), stamp))
    original = original_vectors(vectors)
    original['files9'] += prior
    original['nodes5'] += [(str(p), v) for p, v in parents.items()]
    for field in ('files9', 'nodes5'):
        admitted = {}
        for p, v in original[field]:
            o.check(p not in admitted or tuple(admitted[p]) == tuple(v),
                    'archive-history-early-original-conflict')
            admitted[p] = tuple(v)
        original[field] = list(admitted.items())
    # Hash only the already admitted original regular files, never restat/rebase.
    hashes = []
    deadline = time.monotonic() + 120
    for p, vector in original['files9']:
        if vector[5] & 0o170000 == 0o100000:
            raw = o.read_checked(Path(p), list(vector), max(1, vector[2]), deadline)
            hashes.append((p, hashlib.sha256(raw).hexdigest()))
    close(original)
    expected_names = tuple(sorted((*names, name)))
    original['namespaces'] = [(p, expected_names if p == str(path) else n)
                              for p, n in original['namespaces']]
    vectors['namespaces'] = [(p, expected_names if p == str(path) else n)
                             for p, n in vectors['namespaces']]
    value = {'version': 1, 'kind': kind, 'owner': owner,
             'operation_id': operation_id, 'evidence': copy.deepcopy(evidence),
             'original_vectors': original, 'hashes': hashes,
             'mutation_authority': False, 'publication_acceptance': False,
             'ordinary_import_grant': False, 'reader_index_acceptance': False,
             'automatic_replay': False}
    raw = encoded(value)
    o.check(len(raw) <= MAX_BYTES, 'archive-history-record-bound')
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    leaf = None
    try:
        o.check(five(os.fstat(fd)) == parents[path], 'archive-history-directory-fd')
        leaf = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                       0o600, dir_fd=fd)
        created = nine(os.fstat(leaf))
        o.check(created[5] & 0o170000 == 0o100000 and created[5] & 0o7777 == 0o600
                and created[6:9] == (os.geteuid(), os.getegid(), 1),
                'archive-history-created-metadata')
        view = memoryview(raw)
        while view:
            count = os.write(leaf, view)
            o.check(count > 0, 'archive-history-short-write')
            view = view[count:]
        os.fsync(leaf)
        os.lseek(leaf, 0, 0)
        o.check(os.read(leaf, len(raw) + 1) == raw, 'archive-history-intended-bytes')
        stamp = nine(os.fstat(leaf))
        o.check(stamp[:2] == created[:2] and stamp[5:] == created[5:],
                'archive-history-created-fd-identity')
        o.check(stamp[5] & 0o170000 == 0o100000 and stamp[5] & 0o7777 == 0o600
                and stamp[6:9] == (os.geteuid(), os.getegid(), 1),
                'archive-history-intended-metadata')
        o.check(nine(os.stat(name, dir_fd=fd, follow_symlinks=False)) == stamp,
                'archive-history-leaf-fd')
        os.fsync(fd)
    finally:
        if leaf is not None:
            os.close(leaf)
        os.close(fd)
    reference = {'path': str(path / name), 'signature9': list(stamp),
                 'sha256': hashlib.sha256(raw).hexdigest()}
    o.check(tuple(sorted(os.listdir(path))) == tuple(sorted((*names, name))),
            'archive-history-created-only-record')
    for p, vector in parents.items():
        s = os.lstat(p)
        if (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid) != vector:
            raise o.Held('archive-history-final-parent')
    s = os.lstat(path / name)
    if nine(s) != stamp:
        raise o.Held('archive-history-final-record')
    # Helpers/serialization must run BEFORE this copied complete raw closure.
    for path, names in original['namespaces']:
        if tuple(sorted(os.listdir(path))) != tuple(names):
            raise o.Held('archive-history-original-census')
    for path, vector in original['nodes5']:
        s = os.lstat(path)
        if (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid) != tuple(vector):
            raise o.Held('archive-history-original-node')
    for path, vector in original['files9']:
        s = os.lstat(path)
        if (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns,
                s.st_mode, s.st_uid, s.st_gid, s.st_nlink) != tuple(vector):
            raise o.Held('archive-history-original-file')
    for path in original['absent']:
        try:
            os.lstat(path)
        except FileNotFoundError:
            continue
        raise o.Held('archive-history-original-absence')
    for path, vector in original['claims']:
        try:
            s = os.lstat(path)
        except FileNotFoundError:
            if vector is not None:
                raise o.Held('archive-history-original-claim')
            continue
        claim = (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid,
                 None if (s.st_mode & 0o170000) == 0o040000 else s.st_nlink)
        if claim != (None if vector is None else tuple(vector)):
            raise o.Held('archive-history-original-claim')
    s = os.lstat(reference['path'])
    if (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode, s.st_uid, s.st_gid, s.st_nlink) != stamp:
        raise o.Held('archive-history-final-original-record')
    return reference


def _bind(controller, writer, custody, scope, owner, operation_id, baseline):
    from mylar import publication_reader_lifecycle as lifecycle
    from mylar import publication_native_configured_scope as configured
    o.check(type(custody) is lifecycle.StoppedReaderCustody and
            type(scope) is configured.NativeConfiguredScope and scope._custody is custody,
            'archive-history-exact-bound-scope')
    o.check(lifecycle.bind_archive_preparation(custody, scope, owner, operation_id) is custody,
            'archive-history-original-bound-custody')
    files, nodes, absent = custody.vectors()
    original_files = tuple((str(p), tuple(v)) for p, v in files.items())
    original_nodes = tuple((str(p), tuple(v)) for p, v in nodes.items())
    original_absent = tuple(map(str, absent))
    ref = custody.proofs.get('archive_execution_originals')
    o.check(type(ref) is dict and set(ref) == {'path', 'sha256', 'signature9'},
            'archive-history-parent-execute-reference')
    path = Path(ref['path'])
    original = dict(original_files)
    o.check(str(path) in original, 'archive-history-parent-execute-file9')
    o.check(tuple(ref['signature9']) == original[str(path)] and
            all(type(n) is int for n in ref['signature9']), 'archive-history-original-proof-nine')
    raw = o.read_checked(path, list(original[str(path)]), MAX_BYTES, time.monotonic() + 120)
    o.check(hashlib.sha256(raw).hexdigest() == ref['sha256'],
            'archive-history-original-execute-hash')
    value = decode(raw)
    expected = {'version', 'kind', 'owner', 'operation_id', 'baseline', 'preparation',
                'preparation_directory9', 'reader', 'publication_acceptance', 'mutation_authority'}
    o.check(type(value) is dict and set(value) == expected and type(value['version']) is int
            and value['version'] == 1 and value['kind'] == 'archive-one-original-custody'
            and value['owner'] == owner and value['operation_id'] == operation_id
            and value['publication_acceptance'] is False and value['mutation_authority'] is False,
            'archive-history-original-execute-join')
    for role in ('baseline', 'preparation'):
        declared = value[role]
        o.check(type(declared) is dict and set(declared) == {'path', 'sha256', 'signature9'}
                and type(declared['path']) is str and type(declared['sha256']) is str
                and re.fullmatch('[0-9a-f]{64}', declared['sha256'])
                and type(declared['signature9']) is list and len(declared['signature9']) == 9
                and all(type(n) is int for n in declared['signature9']),
                'archive-history-original-reference-types')
    stage = Path(controller.root) / ('archive-repair-' + operation_id)
    metadata = stage / 'preparation.json'
    o.check(value['preparation']['path'] == str(metadata)
            and original.get(str(metadata)) == tuple(value['preparation']['signature9'])
            and original.get(str(stage)) == tuple(value['preparation_directory9'])
            and value['baseline']['path'] == str(baseline)
            and original.get(str(baseline)) == tuple(value['baseline']['signature9']),
            'archive-history-original-stage-baseline')
    o.check(o.sdk()[2].exact_owner(owner) == owner, 'archive-history-exact-owner')
    o.writer_pair(controller, writer, o.sdk())
    return {'files9': original_files, 'nodes5': original_nodes, 'absent': original_absent,
            'claims': (), 'namespaces': ()}, value


def _bind_live(controller, writer, custody, scope, cap, owner, operation_id, baseline):
    from mylar import publication_reader_lifecycle as lifecycle
    actual = lifecycle.archive_terminal_original_vectors(custody, scope, cap)
    terminal = actual['terminal']
    o.check(cap.preparation._controller is controller and cap.preparation._writer is writer
            and dict(terminal['owner']) == owner and terminal['operation_id'] == operation_id
            and terminal['baseline'][0] == str(baseline), 'archive-history-exact-live-owner')
    o.writer_pair(controller, writer, o.sdk())
    inherited = original_vectors(actual['custody_originals'])
    terminal_vectors = {'files9': terminal['files'], 'nodes5': terminal['nodes'],
                        'absent': terminal['absent'], 'claims': terminal['claims'],
                        'namespaces': terminal['namespaces']}
    for field in ('files9', 'nodes5', 'claims', 'namespaces'):
        current = dict(inherited[field])
        for path, value in terminal_vectors[field]:
            o.check(path not in current or current[path] == value,
                    'archive-history-live-original-conflict')
            current[path] = value
        inherited[field] = list(current.items())
    inherited['absent'] = tuple(set(inherited['absent']) | set(terminal_vectors['absent']))
    return original_vectors(inherited), {'baseline': {'sha256': terminal['baseline'][2]}}


def observe_terminal(controller, writer, custody, scope, owner, operation_id,
                     baseline, scratch, *, rollback=False, with_vectors=False, live_cap=None):
    """Invoke genuine fresh verifier; no caller-supplied receipt or DTO is admitted."""
    early = _early(controller)
    from mylar import publication_archive_verifier as verifier
    o.check(type(rollback) is bool and type(with_vectors) is bool, 'archive-history-finite-terminal-kind')
    history_path, history_nodes = directory(controller, writer)  # Existing before proof lifetime.
    if live_cap is None:
        inherited, execute = _bind(controller, writer, custody, scope, owner, operation_id, baseline)
    else:
        from mylar import publication_reader_lifecycle as lifecycle
        from mylar import publication_archive_adoption as adoption
        inherited, execute = _bind_live(controller, writer, custody, scope, live_cap,
                                       owner, operation_id, baseline)
        registered = lifecycle._ARCHIVE_TERMINALS[custody]
        handle = registered[1]; export_record = adoption._TERMINAL_RECORDS[handle]
        record_snapshot = tuple(export_record.items()); core_projection = export_record['core_projection']
        original_custody_seal = registered[4]; original_custody_projection = registered[7]; original_pipe = custody.channel
        original_pipe_seal = custody.channel_seal
        o.check(live_cap._phase == ('rollback-complete' if rollback else 'complete'),
                'archive-history-live-terminal-kind')
    inherited = original_vectors(inherited)
    observed = (verifier.verify_rollback_existing_with_vectors if rollback else
                verifier.verify_existing_with_vectors)(controller, writer, custody,
                                                       baseline, scratch)
    summary = observed['summary']
    o.check(summary['owner'] == owner and summary['operation_id'] == operation_id
            and summary['baseline_sha256'] == execute['baseline']['sha256'],
            'archive-history-fresh-original-result-join')
    vectors = original_vectors(observed['original_vectors'])
    for field in ('files9', 'nodes5'):
        current = dict(vectors[field])
        for p, v in inherited[field]:
            o.check(p not in current or tuple(current[p]) == tuple(v),
                    'archive-history-verifier-original-conflict')
            current[p] = v
        vectors[field] = list(current.items())
    vectors['absent'] = list(set(vectors['absent']) | set(inherited['absent']))
    vectors = _carry(vectors, early)
    reference = _append(controller, writer, summary['owner'], summary['operation_id'],
                        'rollback-observed' if rollback else 'terminal-observed',
                        summary, vectors)
    vectors['files9'] = list(vectors['files9']) + [(reference['path'], tuple(reference['signature9']))]
    vectors['nodes5'] = list(vectors['nodes5']) + [(str(p), v) for p, v in history_nodes.items()]
    answer = {'summary': copy.deepcopy(summary), 'original_vectors': copy.deepcopy(vectors),
              'history': copy.deepcopy(reference)} if with_vectors else reference
    final_vectors={k:tuple((p,None if v is None else tuple(v)) for p,v in vectors[k]) for k in ('files9','nodes5','claims','namespaces')}
    final_absent=tuple(vectors['absent'])
    custody.revalidate_stopped()
    close(vectors)
    if live_cap is not None:
        lifecycle.archive_terminal_original_vectors(custody, scope, live_cap)
    # Helpers/serialization must run BEFORE this copied complete raw closure.
    for path, names in vectors['namespaces']:
        if tuple(sorted(os.listdir(path))) != tuple(names):
            raise o.Held('archive-history-original-census')
    for path, vector in vectors['nodes5']:
        s = os.lstat(path)
        if (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid) != tuple(vector):
            raise o.Held('archive-history-original-node')
    for path, vector in vectors['files9']:
        s = os.lstat(path)
        if (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns,
                s.st_mode, s.st_uid, s.st_gid, s.st_nlink) != tuple(vector):
            raise o.Held('archive-history-original-file')
    for path in vectors['absent']:
        try:
            os.lstat(path)
        except FileNotFoundError:
            continue
        raise o.Held('archive-history-original-absence')
    for path, vector in vectors['claims']:
        try:
            s = os.lstat(path)
        except FileNotFoundError:
            if vector is not None:
                raise o.Held('archive-history-original-claim')
            continue
        claim = (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid,
                 None if (s.st_mode & 0o170000) == 0o040000 else s.st_nlink)
        if claim != (None if vector is None else tuple(vector)):
            raise o.Held('archive-history-original-claim')
    if live_cap is not None:
        for descriptor, value in zip(original_pipe_seal[:2], original_pipe_seal[3]):
            z = os.fstat(descriptor)
            if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != value:
                raise o.Held('archive-history-final-live-pipe-FD')
        final_pid=os.getpid();final_thread=threading.get_ident();final_now=time.monotonic()
        for descriptor,value in zip(original_pipe_seal[:2],original_pipe_seal[3]):
            z=os.fstat(descriptor)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise o.Held('archive-history-final-live-pipe-FD')
        # The final original physical loop follows all actual pipe/time helpers.
        for path,names in final_vectors['namespaces']:
            if tuple(sorted(os.listdir(path)))!=names:raise o.Held('archive-history-original-census')
        for path,v in final_vectors['claims']:
            try:z=os.lstat(path)
            except FileNotFoundError:
                if v is not None:raise o.Held('archive-history-original-claim')
                continue
            if v is None or (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)!=v:raise o.Held('archive-history-original-claim')
        for path in final_absent:
            try:os.lstat(path)
            except FileNotFoundError:continue
            raise o.Held('archive-history-original-absence')
        for path,v in final_vectors['nodes5']:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise o.Held('archive-history-original-node')
        for path,v in final_vectors['files9']:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise o.Held('archive-history-original-file')
        if lifecycle._ARCHIVE_TERMINALS.get(custody) is not registered or registered[0]() is not live_cap or registered[2] is not scope or lifecycle._SEALS.get(custody) != original_custody_seal or custody.core != original_custody_seal or custody.channel is not original_pipe or custody.channel_seal != original_pipe_seal or lifecycle._PIPE_SEALS.get(original_pipe) != original_pipe_seal or (original_pipe.input, original_pipe.output, original_pipe.thread, original_pipe.facts) != original_pipe_seal or adoption._TERMINAL_EXPORTS.get(live_cap) is not handle or adoption._TERMINAL_RECORDS.get(handle) is not export_record or tuple(export_record.items()) != record_snapshot or adoption._SEALS.get(live_cap) != export_record['cap_seal']:
            raise o.Held('archive-history-final-live-registry')
        p=live_cap.preparation
        physical=(id(controller),id(writer),id(p),id(live_cap.reader),id(writer.local),str(controller.root),tuple(map(str,controller.roots)),str(controller.tool_root),str(writer.root),str(controller.database),str(controller.native_database),tuple(p._identity))
        if physical!=export_record['physical'] or tuple(writer.root_identity)+tuple(writer.lock_identity)!=export_record['physical'][-1]:raise o.Held('archive-history-final-live-physical')
        if live_cap.preparation._controller is not controller or live_cap.preparation._writer is not writer or writer.local is not live_cap.preparation._local or not getattr(writer.local[1], 'depth', 0) or any(getattr(writer.local[1], k, False) for k in ('allow_pending', 'allow_tagger_pending', 'allow_release_pending')) or final_pid != export_record['pid'] or final_thread != export_record['thread'] or final_now >= export_record['deadline']:
            raise o.Held('archive-history-final-live-purpose')
        logical=dict(command=custody.command, paths=[str(custody.input), str(custody.control), str(custody.config_root), str(custody.main), str(custody.tasks), str(custody.restore_root), str(custody.scratch)], deadline=custody.deadline, backup_manifest=custody.backup_manifest, backup_acceptance=custody.backup_acceptance, input_sha=custody.input_sha, nonce=custody.nonce, parent_sha=custody.parent_sha, thread=custody.thread, channel=id(custody.channel), channel_seal=custody.channel_seal, reader=custody.reader, invocation=custody.invocation, proofs=custody.proofs, files={str(p): v for p, v in custody.files.items()}, reader_files={str(p): v for p, v in custody.reader_files.items()}, nodes={str(p): v for p, v in custody.nodes.items()}, absent=list(map(str, custody.absent)), reader_absent=list(map(str, custody.reader_absent)))
        pending=[logical];projection=[]
        while pending:
         value=pending.pop();kind=type(value)
         if kind is dict:
          keys=tuple(sorted(value));projection.append(('dict',keys))
          for name in reversed(keys):pending.append(value[name])
         elif kind in (list,tuple):
          projection.append((kind.__name__,len(value)));pending.extend(reversed(value))
         elif kind in (str,int,bool,float,type(None)):projection.append((kind.__name__,value))
         else:raise o.Held('archive-terminal-custody-projection-type')
        if tuple(projection)!=original_custody_projection:raise o.Held('archive-history-final-live-custody')
        logical = {'objects':live_cap._objects,'phase':live_cap._phase,'thread':live_cap._thread,'paths':list(map(str,(live_cap.root,live_cap.source,live_cap.stage,live_cap.journal))),'files':{str(p):v for p,v in live_cap._files.items()},'nodes':{str(p):v for p,v in live_cap._nodes.items()},'absent':sorted(map(str,live_cap._absent)),'before':live_cap._before,'after':live_cap._after,'owner':live_cap._owner,'source_attrs':live_cap._source_attrs,'stage_attrs':live_cap._stage_attrs,'census':live_cap._census,'records':live_cap._records,'claims':{str(p):v for p,v in live_cap._claims.items()},'names':sorted(live_cap._names),'receipt':live_cap._receipt,'dirs':{str(p):v for p,v in live_cap._dirs.items()},'contents':{str(p):v for p,v in live_cap._contents.items()},'source_names':sorted(live_cap._source_names)}
        pending=[logical];projection=[]
        while pending:
            value=pending.pop();kind=type(value)
            if kind is dict:
                keys=tuple(sorted(value));projection.append(('dict',keys))
                for name in reversed(keys):pending.append(value[name])
            elif kind in (list,tuple):
                projection.append((kind.__name__,len(value)));pending.extend(reversed(value))
            elif kind in (str,int,bool,float,type(None)):projection.append((kind.__name__,value))
            else:raise o.Held('repair-terminal-core-projection-type')
        if tuple(projection)!=core_projection:raise o.Held('archive-history-final-live-complete-core')
    return answer


def prepared(preparation):
    """Record only a genuine, freshly revalidated owning preparation."""
    if type(preparation) is not o.RepairPreparation:
        raise o.Held('archive-history-exact-preparation')
    early = _early(preparation._controller)
    history_path, history_nodes = directory(preparation._controller, preparation._writer)
    files = [(str(p), tuple(f['signature9'])) for p, f in preparation._files.items()]
    files.append((str(preparation._operation), tuple(preparation._directory)))
    vectors = {'files9': files,
               'nodes5': [(str(p), tuple(v)) for p, v in preparation._nodes.items()],
               'claims': [(str(p), None if v is None else tuple(v))
                          for p, v in preparation._claims.items()],
               'namespaces': [(str(preparation._operation), tuple(sorted(preparation._names)))],
               'absent': [str(db) + suffix for db in
                          (preparation._controller.database, preparation._controller.native_database)
                          for suffix in ('-journal', '-wal', '-shm')]}
    vectors = original_vectors(vectors)
    vectors = _carry(vectors, early)
    binding = preparation.revalidate()
    reference = _append(preparation._controller, preparation._writer, binding['owner'],
                        binding['operation_id'], 'prepared',
                        {'preparation_token': binding['token'],
                         'metadata': copy.deepcopy(preparation._files[
                             preparation._operation / 'preparation.json'])}, vectors)
    vectors['files9'] = list(vectors['files9']) + [(reference['path'], tuple(reference['signature9']))]
    vectors['nodes5'] = list(vectors['nodes5']) + [(str(p), v) for p, v in history_nodes.items()]
    preparation.close_passive()
    close(vectors)
    # Helpers/serialization must run BEFORE this copied complete raw closure.
    for path, names in vectors['namespaces']:
        if tuple(sorted(os.listdir(path))) != tuple(names):
            raise o.Held('archive-history-original-census')
    for path, vector in vectors['nodes5']:
        s = os.lstat(path)
        if (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid) != tuple(vector):
            raise o.Held('archive-history-original-node')
    for path, vector in vectors['files9']:
        s = os.lstat(path)
        if (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns,
                s.st_mode, s.st_uid, s.st_gid, s.st_nlink) != tuple(vector):
            raise o.Held('archive-history-original-file')
    for path in vectors['absent']:
        try:
            os.lstat(path)
        except FileNotFoundError:
            continue
        raise o.Held('archive-history-original-absence')
    for path, vector in vectors['claims']:
        try:
            s = os.lstat(path)
        except FileNotFoundError:
            if vector is not None:
                raise o.Held('archive-history-original-claim')
            continue
        claim = (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid,
                 None if (s.st_mode & 0o170000) == 0o040000 else s.st_nlink)
        if claim != (None if vector is None else tuple(vector)):
            raise o.Held('archive-history-original-claim')
    return reference


def executed(cap):
    """Owning completed effect is factual; independent verification remains required."""
    from mylar import publication_archive_adoption as adoption
    if type(cap) is not adoption.RepairAdoption:
        raise o.Held('archive-history-exact-adoption')
    early = _early(cap.preparation._controller)
    history_path, history_nodes = directory(cap.preparation._controller, cap.preparation._writer)
    o.check(cap._phase in ('complete', 'rollback-complete'), 'archive-history-completed-owning-effect')
    vectors = {'files9': [(str(p), tuple(v)) for p, v in {**cap._files, **cap._dirs}.items()],
               'nodes5': [(str(p), tuple(v)) for p, v in cap._nodes.items()],
               'claims': [(str(p), None if v is None else tuple(v)) for p, v in cap._claims.items()],
               'absent': tuple(map(str, cap._absent)),
               'namespaces': [(str(cap.root), tuple(sorted(cap._names))),
                              (str(cap.journal), tuple(sorted(p.name for p in cap._files
                                                             if p.parent == cap.journal)))]}
    # The source claim has the actual owning exchanged identity after completion.
    source = cap._files[cap.source]
    vectors['claims'] = [(p, (source[0], source[1], source[5], source[6], source[7], source[8])
                          if p == str(cap.source) else v) for p, v in vectors['claims']]
    vectors['files9'].append((str(cap.preparation._operation), tuple(cap.preparation._directory)))
    vectors = original_vectors(vectors)
    vectors = _carry(vectors, early)
    binding = cap.binding
    reference = _append(cap.preparation._controller, cap.preparation._writer,
                        binding['owner'], binding['operation_id'], 'execute-observed',
                        binding, vectors)
    vectors['files9'] = list(vectors['files9']) + [(reference['path'], tuple(reference['signature9']))]
    vectors['nodes5'] = list(vectors['nodes5']) + [(str(p), v) for p, v in history_nodes.items()]
    cap.close()
    close(vectors)
    # Helpers/serialization must run BEFORE this copied complete raw closure.
    for path, names in vectors['namespaces']:
        if tuple(sorted(os.listdir(path))) != tuple(names):
            raise o.Held('archive-history-original-census')
    for path, vector in vectors['nodes5']:
        s = os.lstat(path)
        if (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid) != tuple(vector):
            raise o.Held('archive-history-original-node')
    for path, vector in vectors['files9']:
        s = os.lstat(path)
        if (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns,
                s.st_mode, s.st_uid, s.st_gid, s.st_nlink) != tuple(vector):
            raise o.Held('archive-history-original-file')
    for path in vectors['absent']:
        try:
            os.lstat(path)
        except FileNotFoundError:
            continue
        raise o.Held('archive-history-original-absence')
    for path, vector in vectors['claims']:
        try:
            s = os.lstat(path)
        except FileNotFoundError:
            if vector is not None:
                raise o.Held('archive-history-original-claim')
            continue
        claim = (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid,
                 None if (s.st_mode & 0o170000) == 0o040000 else s.st_nlink)
        if claim != (None if vector is None else tuple(vector)):
            raise o.Held('archive-history-original-claim')
    return reference


def status(controller, writer, owner, operation_id, *, with_vectors=False):
    """Passively display current retained observations; no saved grant is consumed."""
    early = _early(controller)
    path, parents = directory(controller, writer)
    close(early)
    owner = o.sdk()[2].exact_owner(owner)
    o.check(type(operation_id) is str and re.fullmatch('[0-9a-f]{64}', operation_id),
            'archive-history-status-key')
    names = tuple(sorted(os.listdir(path)))
    o.check(len(names) <= MAX_RECORDS and all(re.fullmatch(
        '[0-9a-f]{64}\\.(prepared|execute-observed|terminal-observed|rollback-observed)\\.json', n)
        for n in names), 'archive-history-status-census')
    records = {}
    leaves = []
    deadline = time.monotonic() + 120
    total = 0
    for kind in KINDS:
        name = operation_id + '.' + kind + '.json'
        if name not in names:
            continue
        leaf = path / name
        stamp = nine(os.lstat(leaf))
        o.check(stamp[5] & 0o170000 == 0o100000 and stamp[5] & 0o7777 == 0o600
                and stamp[6:9] == (os.geteuid(), os.getegid(), 1),
                'archive-history-private-status-record')
        total += stamp[2]
        o.check(total <= MAX_BYTES, 'archive-history-status-byte-bound')
        raw = o.read_checked(leaf, list(stamp), MAX_BYTES, deadline)
        value = decode(raw)
        o.check(type(value) is dict and set(value) ==
                {'version', 'kind', 'owner', 'operation_id', 'evidence', 'original_vectors',
                 'hashes', 'mutation_authority', 'publication_acceptance', 'ordinary_import_grant',
                 'reader_index_acceptance', 'automatic_replay'}
                and type(value['version']) is int and value['version'] == 1
                and value['kind'] == kind and value['owner'] == owner
                and value['operation_id'] == operation_id
                and all(value[field] is False for field in
                        ('mutation_authority', 'publication_acceptance', 'ordinary_import_grant',
                         'reader_index_acceptance', 'automatic_replay')),
                'archive-history-status-record-schema')
        records[kind] = value
        leaves.append((str(leaf), stamp))
    o.check(not ('terminal-observed' in records and 'rollback-observed' in records),
            'archive-history-ambiguous-terminal')
    if not records:
        close(early)
        # No helper follows this full closure of the original journal.
        for path, names in early['namespaces']:
            if tuple(sorted(os.listdir(path))) != tuple(names):
                raise o.Held('archive-history-original-census')
        for path, vector in early['nodes5']:
            s = os.lstat(path)
            if (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid) != tuple(vector):
                raise o.Held('archive-history-original-node')
        for path, vector in early['files9']:
            s = os.lstat(path)
            if (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns,
                    s.st_mode, s.st_uid, s.st_gid, s.st_nlink) != tuple(vector):
                raise o.Held('archive-history-original-file')
        for path in early['absent']:
            try:
                os.lstat(path)
            except FileNotFoundError:
                continue
            raise o.Held('archive-history-original-absence')
        for path, vector in early['claims']:
            try:
                s = os.lstat(path)
            except FileNotFoundError:
                if vector is not None:
                    raise o.Held('archive-history-original-claim')
                continue
            claim = (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid,
                     None if (s.st_mode & 0o170000) == 0o040000 else s.st_nlink)
            if claim != (None if vector is None else tuple(vector)):
                raise o.Held('archive-history-original-claim')
        return None
    kind = next(candidate for candidate in reversed(KINDS) if candidate in records)
    current = records[kind]
    vectors = original_vectors(current['original_vectors'])
    expected_files = dict(vectors['files9'])
    metadata = str(Path(controller.root) / ('archive-repair-' + operation_id) / 'preparation.json')
    required = {str(controller.database), str(controller.native_database), str(writer.lock),
                str(writer.root / 'publication-v1.json'), metadata,
                str(Path(metadata).parent)}
    o.check(required <= set(expected_files), 'archive-history-status-owning-controls')
    evidence = current['evidence']
    if kind in ('terminal-observed', 'rollback-observed'):
        rollback_kind = kind == 'rollback-observed'
        fields = {'version', 'kind', 'operation_id', 'owner', 'source_sha256',
                  'reader_reference_preservation', 'native_only_size_cell_transition',
                  'baseline_sha256', 'reader_index_acceptance', 'mutation_authority',
                  'publication_acceptance', 'ordinary_import_grant'}
        if rollback_kind:
            fields |= {'native_preimage_restored', 'rollback_verified'}
        o.check(type(evidence) is dict and set(evidence) == fields
                and type(evidence['version']) is int and evidence['version'] == 1
                and evidence['kind'] == ('fresh-repair-rollback-observation' if rollback_kind
                                          else 'fresh-repair-terminal-observation')
                and evidence['owner'] == owner and evidence['operation_id'] == operation_id
                and evidence['reader_reference_preservation'] is True
                and evidence['native_only_size_cell_transition'] is (not rollback_kind)
                and all(evidence[key] is False for key in
                        ('reader_index_acceptance', 'mutation_authority',
                         'publication_acceptance', 'ordinary_import_grant'))
                and (not rollback_kind or evidence['native_preimage_restored'] is True
                     and evidence['rollback_verified'] is True),
                'archive-history-status-terminal-evidence')
        baselines = [p for p in expected_files if Path(p).name == 'baseline.json'
                     and Path(p).parent.name == 'journal'
                     and Path(p).parent.parent.name == 'adopt-' + operation_id]
        o.check(len(baselines) == 1, 'archive-history-status-exact-baseline')
        summary, _, _ = o.catalog(controller, owner, o.sdk()[2], deadline)
        actual_source = summary['owner']['path']
        o.check(actual_source in expected_files, 'archive-history-status-catalog-source')
        declared_hashes = dict(current['hashes'])
        o.check(declared_hashes.get(actual_source) == evidence['source_sha256']
                and declared_hashes.get(baselines[0]) == evidence['baseline_sha256'],
                'archive-history-status-terminal-hash-joins')
    elif kind == 'prepared':
        o.check(type(evidence) is dict and set(evidence) == {'preparation_token', 'metadata'}
                and type(evidence['preparation_token']) is str
                and re.fullmatch('[0-9a-f]{64}', evidence['preparation_token'])
                and evidence['metadata']['path'] == metadata
                and tuple(evidence['metadata']['signature9']) == tuple(expected_files[metadata]),
                'archive-history-status-preparation-join')
        raw = o.read_checked(Path(metadata), list(expected_files[metadata]), MAX_BYTES, deadline)
        body = decode(raw)
        o.check(body['kind'] == 'owned-archive-repair-preparation'
                and type(body['version']) is int and body['version'] == 1
                and body['owner'] == owner and body['operation_id'] == operation_id
                and body['token'] == evidence['preparation_token']
                and body['token'] == o.digest({key: value for key, value in body.items()
                                               if key != 'token'})
                and hashlib.sha256(raw).hexdigest() == evidence['metadata']['sha256'],
                'archive-history-status-current-preparation-token')
    else:
        o.check(type(evidence) is dict and type(evidence['version']) is int
                and evidence['version'] == 1 and evidence['kind'] == 'same-path-owned-archive-repair'
                and evidence['owner'] == owner and evidence['operation_id'] == operation_id
                and evidence['phase'] in ('complete', 'rollback-complete')
                and evidence['ordinary_import_grant'] is False
                and evidence['publication_acceptance'] is False
                and evidence['reader_index_acceptance'] is False,
                'archive-history-status-execute-join')
        ref = evidence['receipt']
        o.check(type(ref) is dict and set(ref) == {'path', 'sha256', 'signature9'}
                and type(ref['path']) is str and type(ref['sha256']) is str
                and re.fullmatch('[0-9a-f]{64}', ref['sha256'])
                and type(ref['signature9']) is list and len(ref['signature9']) == 9
                and all(type(n) is int for n in ref['signature9'])
                and tuple(ref['signature9']) == tuple(expected_files[ref['path']])
                and dict(current['hashes']).get(ref['path']) == ref['sha256'],
                'archive-history-status-original-owning-receipt')
    hashes = current['hashes']
    o.check(type(hashes) is list and len(hashes) == len({p for p, _ in hashes}),
            'archive-history-status-hash-shape')
    expected_hashes = {p for p, v in vectors['files9'] if v[5] & 0o170000 == 0o100000}
    o.check({p for p, _ in hashes} == expected_hashes, 'archive-history-status-complete-hashes')
    for p, digest in hashes:
        o.check(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest),
                'archive-history-status-digest')
        raw = o.read_checked(Path(p), list(expected_files[p]), max(1, expected_files[p][2]), deadline)
        o.check(hashlib.sha256(raw).hexdigest() == digest, 'archive-history-status-original-bytes')
    result = {'version': 1, 'owner': copy.deepcopy(owner), 'operation_id': operation_id,
              'outcome': kind, 'mutation_authority': False, 'publication_acceptance': False,
              'ordinary_import_grant': False, 'reader_index_acceptance': False,
              'reader_preservation_verified': False, 'automatic_replay': False}
    vectors = _carry(vectors, early)
    vectors['files9'] = list(vectors['files9']) + leaves
    vectors['nodes5'] = list(vectors['nodes5']) + [(str(p), v) for p, v in parents.items()]
    vectors['namespaces'] = list(vectors['namespaces']) + [(str(path), names)]
    o.check(time.monotonic() < deadline, 'archive-history-status-deadline')
    answer = {'summary': copy.deepcopy(result), 'original_vectors': copy.deepcopy(vectors)} if with_vectors else result
    close(vectors)
    # Complete raw originals after the last replaceable passive helper.
    for current, census in vectors['namespaces']:
        if tuple(sorted(os.listdir(current))) != tuple(census):
            raise o.Held('archive-history-status-census-final')
    for current, expected in vectors['nodes5']:
        info = os.lstat(current)
        if (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid) != tuple(expected):
            raise o.Held('archive-history-status-node-final')
    for current, expected in vectors['files9']:
        info = os.lstat(current)
        if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
                info.st_mode, info.st_uid, info.st_gid, info.st_nlink) != tuple(expected):
            raise o.Held('archive-history-status-file-final')
    for current in vectors['absent']:
        try:
            os.lstat(current)
        except FileNotFoundError:
            continue
        raise o.Held('archive-history-status-absence-final')
    for current, expected in vectors['claims']:
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            if expected is not None:
                raise o.Held('archive-history-status-missing-claim-final')
            continue
        if (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
                None if info.st_mode & 0o170000 == 0o040000 else info.st_nlink) != (
                    None if expected is None else tuple(expected)):
            raise o.Held('archive-history-status-claim-final')
    return answer


def record_vectors(reference):
    """Read the exact just-created record; return factual original declarations only."""
    o.check(type(reference) is dict and set(reference) == {'path','signature9','sha256'},
            'archive-history-exact-record-reference')
    vector = tuple(reference['signature9'])
    raw = o.read_checked(Path(reference['path']), list(vector), MAX_BYTES, time.monotonic()+120)
    o.check(hashlib.sha256(raw).hexdigest() == reference['sha256'], 'archive-history-record-hash')
    value = decode(raw)
    vectors = original_vectors(value['original_vectors'])
    vectors['files9'].append((reference['path'], vector))
    close(vectors)
    # Complete raw originals after the last replaceable passive helper.
    for current, census in vectors['namespaces']:
        if tuple(sorted(os.listdir(current))) != tuple(census):
            raise o.Held('archive-history-status-census-final')
    for current, expected in vectors['nodes5']:
        info = os.lstat(current)
        if (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid) != tuple(expected):
            raise o.Held('archive-history-status-node-final')
    for current, expected in vectors['files9']:
        info = os.lstat(current)
        if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
                info.st_mode, info.st_uid, info.st_gid, info.st_nlink) != tuple(expected):
            raise o.Held('archive-history-status-file-final')
    for current in vectors['absent']:
        try:
            os.lstat(current)
        except FileNotFoundError:
            continue
        raise o.Held('archive-history-status-absence-final')
    for current, expected in vectors['claims']:
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            if expected is not None:
                raise o.Held('archive-history-status-missing-claim-final')
            continue
        if (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
                None if info.st_mode & 0o170000 == 0o040000 else info.st_nlink) != (
                    None if expected is None else tuple(expected)):
            raise o.Held('archive-history-status-claim-final')
    return vectors
