"""Finite explicit device-edge validation. Authenticated commit is not wired."""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import threading
from contextlib import contextmanager

if __package__:
    from . import publication_guard as guard
else:
    import publication_guard as guard

COMMIT_BINDINGS = None
_NORMALIZER_READ = threading.local()
MAX_EDGES = 8
MAX_RECORD_BYTES = 256 * 1024
FIELDS = {'database_identity', 'writer_identity'}
PENDING = ('normalizer-v1.pending', 'tagger-v2.pending', 'release-v1.pending', 'publication-recovery-v1.json', 'tagger-publication-v1.json', 'nested-derivative-v1.json', 'tagger-recovery-v1.pending')


def need(ok, reason):
    if not ok:
        raise guard.Unavailable(reason)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(value):
    need(type(value) is dict and set(value) == FIELDS, 'identity-exact-fields')
    for name, size in (('database_identity', 2), ('writer_identity', 4)):
        values = value[name]
        need(type(values) is list and len(values) == size
             and all(type(x) is int and x >= 0 for x in values)
             and all(values[i] > 0 for i in range(1, size, 2)), 'identity-exact-integers')
    return value


def device_edge(old, new):
    identity(old)
    identity(new)
    old_devices = [old['database_identity'][0], old['writer_identity'][0], old['writer_identity'][2]]
    new_devices = [new['database_identity'][0], new['writer_identity'][0], new['writer_identity'][2]]
    need(len(set(old_devices)) == len(set(new_devices)) == 1
         and old_devices[0] != new_devices[0], 'one-explicit-device-substitution')
    need(old['database_identity'][1] == new['database_identity'][1]
         and old['writer_identity'][1::2] == new['writer_identity'][1::2], 'device-only-inode-preservation')


def capture_prefix(db, *, pending=None, current_identity=None):
    need(type(db) is sqlite3.Connection and db.in_transaction, 'original-SQLite-read-transaction')
    census, _ = guard.complete_census(db, pending=pending)
    schema = guard.workflow_schema(db)
    intents, attestations, bootstrap, bindings = {}, {}, [], {}
    for kind, key, raw in db.execute("SELECT kind,key,value FROM records WHERE substr(kind,1,12)='publication_' ORDER BY kind,key"):
        if kind == 'publication_intent':
            value = guard.decode_json(raw)
            plan = guard.intent_record(key, value)
            if value['outcome'] == 'accepted':
                need(key == pending and plan['action'] == 'register' and current_identity is not None
                     and {name: list(plan['binding'][name]) for name in FIELDS} == current_identity,
                     'accepted-initialization-unfinished')
            if value['outcome'] == 'committed':
                intents[key] = digest(raw.encode())
                bindings[key] = {name: list(plan['binding'][name]) for name in FIELDS}
                identity(bindings[key])
                if plan['action'] == 'bootstrap':
                    bootstrap.append(key)
        elif kind == 'publication_attestation':
            attestations[key] = digest(raw.encode())
    need(len(bootstrap) == 1, 'one-original-bootstrap')
    return dict(schema=schema, epoch=census['epoch'], bootstrap_token=bootstrap[0],
                census=json.loads(encoded(census)), committed_intents=intents, committed_bindings=bindings, attestations=attestations)


def evidence_value(value):
    need(type(value) is dict and set(value) in ({'backup_digest', 'restore_digest', 'review_digest', 'current_state_digest', 'prospective_fs'}, {'backup_digest', 'restore_digest', 'review_digest', 'current_state_digest', 'prospective_fs', 'tagger'}), 'identity-migration-evidence-fields')
    for name in ('backup_digest', 'restore_digest', 'review_digest', 'current_state_digest'):
        need(type(value[name]) is str and re.fullmatch('[a-f0-9]{64}', value[name]), 'identity-migration-evidence-digest')
    stable = value['prospective_fs']
    if stable is not None:
        need(type(stable) is dict and set(stable) == {'fstype', 'filesystem_uuid', 'subvolume', 'path_anchor_digest'}
             and stable['fstype'] == 'btrfs' and type(stable['filesystem_uuid']) is str
             and re.fullmatch('[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', stable['filesystem_uuid'])
             and type(stable['subvolume']) is str and 1 <= len(stable['subvolume'].encode()) <= 128
             and type(stable['path_anchor_digest']) is str and re.fullmatch('[a-f0-9]{64}', stable['path_anchor_digest']), 'identity-prospective-filesystem-binding')
    tagger = value.get('tagger')
    if tagger is not None:
        need(type(tagger) is dict and set(tagger) == {'binding_sha256', 'binding_inode', 'directory_inodes'}
             and guard.digest_value(tagger['binding_sha256']) and type(tagger['binding_inode']) is int and tagger['binding_inode'] > 0
             and type(tagger['directory_inodes']) is list and len(tagger['directory_inodes']) == 4
             and all(type(x) is int and x > 0 for x in tagger['directory_inodes']), 'identity-reviewed-tagger-evidence')
    return value


def prepare_plan(db, old_identity, new_identity, evidence, previous=None):
    """Pure plan; evidence digests are NOT verified-backup/authentication grants."""
    device_edge(old_identity, new_identity)
    evidence_value(evidence)
    need(previous is None or type(previous) is str and re.fullmatch('[a-f0-9]{64}', previous), 'identity-predecessor-token')
    prefix = capture_prefix(db)
    need(all(b['database_identity'][1] == old_identity['database_identity'][1] and b['writer_identity'][1::2] == old_identity['writer_identity'][1::2] for b in prefix['committed_bindings'].values()), 'identity-committed-inode-binding')
    if previous is None:
        need(all(b == old_identity for b in prefix['committed_bindings'].values()), 'identity-original-root-binding')
    return json.loads(encoded(dict(version=1, kind='reviewed-device-identity-edge', previous=previous,
                                   old=old_identity, new=new_identity, prefix=prefix, evidence=evidence)))


def record_bytes(plan):
    """Format a source-test/approved-producer record; this performs no acceptance."""
    validate_plan(plan)
    raw = encoded(dict(version=1, kind='prepared-device-identity-edge', token=digest(encoded(plan)), accepted=False, plan=plan))
    need(len(raw) <= MAX_RECORD_BYTES, 'identity-record-bound')
    return raw


def validate_plan(plan):
    need(type(plan) is dict and set(plan) == {'version', 'kind', 'previous', 'old', 'new', 'prefix', 'evidence'}
         and type(plan['version']) is int and plan['version'] == 1
         and plan['kind'] == 'reviewed-device-identity-edge', 'identity-plan-schema')
    device_edge(plan['old'], plan['new'])
    evidence_value(plan['evidence'])
    need(plan['previous'] is None or type(plan['previous']) is str and re.fullmatch('[a-f0-9]{64}', plan['previous']), 'identity-predecessor-token')
    prefix = plan['prefix']
    need(type(prefix) is dict and set(prefix) == {'schema', 'epoch', 'bootstrap_token', 'census', 'committed_intents', 'committed_bindings', 'attestations'}, 'identity-prefix-schema')
    for name in ('schema', 'epoch', 'bootstrap_token'):
        need(type(prefix[name]) is str and re.fullmatch('[a-f0-9]{64}', prefix[name]), 'identity-prefix-token')
    guard.census_value(prefix['census'])
    need(prefix['census']['epoch'] == prefix['epoch'], 'identity-prefix-epoch')
    for name, bound in (('committed_intents', guard.INTENT_LIMIT + guard.REGISTRATION_INTENT_LIMIT), ('attestations', guard.REGISTRY_LIMIT)):
        rows = prefix[name]
        need(type(rows) is dict and len(rows) <= bound and all(type(k) is str and type(v) is str and re.fullmatch('[a-f0-9]{64}', k) and re.fullmatch('[a-f0-9]{64}', v) for k, v in rows.items()), 'identity-prefix-row-hashes')
    need(type(prefix['committed_bindings']) is dict and set(prefix['committed_bindings']) == set(prefix['committed_intents']), 'identity-prefix-bindings-complete')
    for binding in prefix['committed_bindings'].values():
        identity(binding)
    need(prefix['bootstrap_token'] in prefix['committed_intents'] and set(prefix['attestations']) == set(prefix['census']['keys']), 'identity-prefix-complete-census')


def check_prefix(db, prefix, *, pending=None, current_identity=None):
    """Commit-time whole state may evolve; adopted immutable rows may not."""
    current = capture_prefix(db, pending=pending, current_identity=current_identity)
    need(all(current[name] == prefix[name] for name in ('schema', 'epoch', 'bootstrap_token')), 'identity-current-authority-root')
    for name in ('committed_intents', 'committed_bindings', 'attestations'):
        need(all(current[name].get(key) == value for key, value in prefix[name].items()), 'identity-adopted-history-prefix-changed')
    need(set(prefix['census']['keys']) <= set(current['census']['keys'])
         and current['census']['revision'] >= prefix['census']['revision'], 'identity-census-not-descendant')
    return current


def _read_ledger(directory):
    directory = Path(directory)
    need(directory.is_absolute() and all(x not in ('', '.', '..') for x in str(directory).split('/')[1:]), 'identity-ledger-canonical')
    nodes, files = {}, {}
    for parent in (directory, *directory.parents):
        z = os.lstat(parent)
        need(stat.S_ISDIR(z.st_mode), 'identity-ledger-ancestor')
        nodes[str(parent)] = (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid)
    root = os.lstat(directory)
    need(root.st_uid == os.geteuid() and stat.S_IMODE(root.st_mode) == 0o700, 'identity-ledger-private-root')
    names = set(os.listdir(directory))
    need(1 <= len(names) <= MAX_EDGES and all(re.fullmatch(r'[a-f0-9]{64}\.json', name) for name in names), 'identity-ledger-finite-namespace')
    records = {}
    for name in sorted(names):
        path = directory/name
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            z = os.fstat(fd)
            original = (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode, z.st_uid, z.st_gid, z.st_nlink)
            need(stat.S_ISREG(z.st_mode) and z.st_nlink == 1 and z.st_uid == os.geteuid()
                 and stat.S_IMODE(z.st_mode) == 0o600 and 0 < z.st_size <= MAX_RECORD_BYTES, 'identity-original-private-record')
            raw = b''
            while len(raw) < z.st_size:
                block = os.read(fd, min(65536, z.st_size-len(raw)))
                need(bool(block), 'identity-record-short')
                raw += block
            end = os.fstat(fd)
            now = os.lstat(path)
            vector = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode, s.st_uid, s.st_gid, s.st_nlink)
            need(vector(end) == original and vector(now) == original, 'identity-record-original9')
        finally:
            os.close(fd)
        value = guard.decode_json(raw.decode())
        need(type(value) is dict and set(value) == {'version', 'kind', 'token', 'accepted', 'plan'}
             and type(value['version']) is int and value['version'] == 1
             and value['kind'] == 'committed-device-identity-edge' and value['accepted'] is True, 'identity-record-schema')
        validate_plan(value['plan'])
        need(value['token'] == name[:-5] == digest(encoded(value['plan'])), 'identity-record-token')
        files[str(path)] = original
        records[value['token']] = value
    return records, nodes, files, names



def pending_state(root):
    """All markers hold except one fresh marker of this exact currently held Writer."""
    root=Path(root)
    value=getattr(_NORMALIZER_READ,'value',None)
    if value is None:
        need(not any(os.path.lexists(root/name) for name in PENDING), 'identity-pending-state-held')
        return
    writer,local,original,markerfd,lockfd,nodes,thread=value
    if __package__:
        from .media_writer import Writer, file_signature, _REGISTRY, deny_negative_phase
    else:
        from media_writer import Writer, file_signature, _REGISTRY, deny_negative_phase
    need(type(writer) is Writer and threading.get_ident()==thread
         and writer.local[1] is local and _REGISTRY.get(str(writer.root)) is writer.local
         and getattr(local,'depth',0)>0 and local.allow_pending is True
         and getattr(local,'normalizer_pending_original',None) is original
         and original[0] is writer, 'identity-normalizer-original-held-owner')
    deny_negative_phase(writer.root)
    need(not any(os.path.lexists(root/name) or os.path.lexists(writer.root/name)
                 for name in PENDING if name!='normalizer-v1.pending'), 'identity-other-pending-held')
    z=os.lstat(root)
    need((z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)==original[2], 'identity-normalizer-root-alias')
    # Every callback/namespace check precedes raw original FD/path/node closure.
    need(getattr(_NORMALIZER_READ,'value',None) is value
         and getattr(local,'normalizer_pending_original',None) is original
         and threading.get_ident()==thread and getattr(local,'depth',0)>0 and local.allow_pending is True,
         'identity-normalizer-owner-changed')
    for name,row in nodes:
        z=os.lstat(name)
        need((z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)==row, 'identity-normalizer-original-node5')
    need(file_signature(os.fstat(lockfd))==original[3]
         and file_signature(os.lstat(writer.lock))==original[3], 'identity-normalizer-original-lock9')
    need(file_signature(os.fstat(markerfd))==original[1]
         and file_signature(os.lstat(writer.pending))==original[1]
         and file_signature(os.lstat(root/'normalizer-v1.pending'))==original[1], 'identity-normalizer-original-marker9')


@contextmanager
def normalizer_pending_read(writer):
    """Read-side fact only; never acquires a Writer or admits a crashed fence."""
    if __package__:
        from .media_writer import Writer, checked_file, deny_negative_phase
    else:
        from media_writer import Writer, checked_file, deny_negative_phase
    need(type(writer) is Writer and getattr(_NORMALIZER_READ,'value',None) is None,
         'identity-normalizer-exact-owner')
    local=writer.local[1]
    original=getattr(local,'normalizer_pending_original',None)
    need(type(original) is tuple and len(original)==4 and original[0] is writer
         and getattr(local,'depth',0)>0 and local.allow_pending is True,
         'identity-normalizer-fresh-owned-marker-required')
    thread=threading.get_ident()
    nodes=[]
    for name in (writer.root,*writer.root.parents):
        z=os.lstat(name)
        need(stat.S_ISDIR(z.st_mode), 'identity-normalizer-linked-ancestor')
        nodes.append((str(name),(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)))
    nodes=tuple(nodes)
    markerfd=checked_file(writer.pending)
    try:
        lockfd=checked_file(writer.lock)
        try:
            _NORMALIZER_READ.value=(writer,local,original,markerfd,lockfd,nodes,threading.get_ident())
            try:
                pending_state(writer.root)
                yield
                pending_state(writer.root)
            finally:_NORMALIZER_READ.value=None
        finally:os.close(lockfd)
    finally:os.close(markerfd)
    # Descriptor-close callbacks must not introduce another publication fence.
    deny_negative_phase(writer.root)
    if any(os.path.lexists(writer.root/name) for name in PENDING if name!='normalizer-v1.pending'):
        raise guard.Unavailable('identity-normalizer-final-pending-held')
    # Closing descriptors and the final reader callbacks cannot refresh originals.
    if (getattr(local,'normalizer_pending_original',None) is not original
            or threading.get_ident()!=thread or getattr(local,'depth',0)<=0 or local.allow_pending is not True):
        raise guard.Unavailable('identity-normalizer-final-owner')
    for name,row in nodes:
        z=os.lstat(name)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=row:
            raise guard.Unavailable('identity-normalizer-final-node5')
    for name,row in ((writer.lock,original[3]),(writer.pending,original[1])):
        z=os.lstat(name)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=row:
            raise guard.Unavailable('identity-normalizer-final-original9')


def resolve(db, ledger_dir, historical_identity, current_identity, *, boundary=lambda: None, pending=None, writer_owner=None):
    """Exact optional historical projection, not an operational authorization."""
    identity(historical_identity)
    identity(current_identity)
    input_tape = encoded([historical_identity, current_identity])
    historical_original, current_original = historical_identity, current_identity
    historical_identity, current_identity = json.loads(input_tape)
    path = Path(ledger_dir)
    if not os.path.lexists(path):
        need(historical_identity == current_identity, 'foreign-durable-identity-no-adoption')
        result = json.loads(encoded(current_identity))
        need(encoded([historical_original, current_original]) == input_tape, 'identity-original-input-changed')
        return result
    pending_state(path.parent)
    records, nodes, files, names = _read_ledger(path)
    original_authority = capture_prefix(db, pending=pending, current_identity=current_identity)
    accepted_original = {key: raw for key, raw in db.execute("SELECT key,value FROM records WHERE kind='publication_intent'") if guard.decode_json(raw).get('outcome') == 'accepted'}
    roots = [token for token, value in records.items() if value['plan']['previous'] is None]
    need(len(roots) == 1, 'identity-one-chain-root')
    children = {}
    for token, value in records.items():
        parent = value['plan']['previous']
        if parent is not None:
            need(parent in records and parent not in children, 'identity-no-foreign-branch')
            children[parent] = token
    ordered, seen, token = [], set(), roots[0]
    while True:
        need(token not in seen, 'identity-no-cycle')
        seen.add(token)
        ordered.append(records[token]['plan'])
        if token not in children:
            break
        token = children[token]
    need(seen == set(records), 'identity-no-orphan-history')
    previous = None
    recognized = [ordered[0]['old']]
    need(all(b == ordered[0]['old'] for b in ordered[0]['prefix']['committed_bindings'].values()), 'identity-root-witness-bindings')
    for plan in ordered:
        if previous is not None:
            need(plan['old'] == previous['new'] and plan['prefix']['bootstrap_token'] == previous['prefix']['bootstrap_token']
                 and plan['prefix']['epoch'] == previous['prefix']['epoch'] and plan['prefix']['schema'] == previous['prefix']['schema'], 'identity-linked-transition')
            for kind in ('committed_intents', 'committed_bindings', 'attestations'):
                need(all(plan['prefix'][kind].get(k) == v for k, v in previous['prefix'][kind].items()), 'identity-edge-prefix-not-descendant')
        need(all(b in recognized for b in plan['prefix']['committed_bindings'].values()), 'identity-edge-unknown-binding')
        check_prefix(db, plan['prefix'], pending=pending, current_identity=current_identity)
        recognized.append(plan['new'])
        previous = plan
    stable_observation = None
    tip = ordered[-1]['new']
    later_aliases = []
    unknown_bindings = [(key, value) for key, value in original_authority['committed_bindings'].items() if value not in recognized]
    if tip != current_identity or unknown_bindings:
        if tip != current_identity:
            device_edge(tip, current_identity)
        expected_fs = ordered[-1]['evidence']['prospective_fs']
        need(expected_fs is not None, 'identity-current-tip-exact')
        if __package__:
            from .publication_filesystem_binding import observe, database_observation
        else:
            from publication_filesystem_binding import observe, database_observation
        databases = db.execute('PRAGMA database_list').fetchall()
        main = [row[2] for row in databases if row[1] == 'main']
        need(len(main) == 1 and main[0], 'identity-original-main-database-path')
        if __package__:
            from .media_writer import Writer
        else:
            from media_writer import Writer
        actual_current = dict(database_identity=database_observation(main[0], held_writer=writer_owner, transaction=db)[:2],
                              writer_identity=guard.writer_identity(Writer(path.parent, create=False)))
        need(actual_current == current_identity, 'identity-prospective-current-physical-pair')
        stable_observation = observe(main[0], path.parent, held_writer=writer_owner, transaction=db)
        need(stable_observation == expected_fs, 'identity-prospective-stable-filesystem-differs')
        recognized.append(current_identity)
        for key, value in unknown_bindings:
            need(key not in ordered[-1]['prefix']['committed_intents'], 'identity-adopted-binding-not-reprojectable')
            device_edge(tip, value)
            later_aliases.append(value)
            recognized.append(value)
    need(all(b in recognized for b in original_authority['committed_bindings'].values()), 'identity-current-mixed-binding')
    effective, used = json.loads(encoded(historical_identity)), False
    for plan in ordered:
        if effective == plan['old']:
            effective, used = plan['new'], True
    if stable_observation is not None and (effective == ordered[-1]['new'] or historical_identity in later_aliases):
        effective, used = current_identity, True
    need(effective == current_identity and (used or historical_identity == current_identity), 'identity-unexplained-historical-binding')
    boundary()
    need(capture_prefix(db, pending=pending, current_identity=current_identity) == original_authority, 'identity-authority-changed-during-read')
    need({key: raw for key, raw in db.execute("SELECT key,value FROM records WHERE kind='publication_intent'") if guard.decode_json(raw).get('outcome') == 'accepted'} == accepted_original, 'identity-original-accepted-row-changed')
    need(encoded([historical_original, current_original]) == input_tape, 'identity-original-input-changed')
    pending_state(path.parent)
    if stable_observation is not None:
        need(observe(main[0], path.parent, held_writer=writer_owner, transaction=db) == stable_observation, 'identity-stable-filesystem-changed')
    # Every callback precedes complete original namespace/node/file9 closure.
    result = json.loads(encoded(current_identity))
    need(set(os.listdir(path)) == names, 'identity-final-ledger-namespace')
    for name, original in nodes.items():
        z = os.lstat(name)
        if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != original:
            raise guard.Unavailable('identity-final-original-node5')
    for name, original in files.items():
        z = os.lstat(name)
        if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode, z.st_uid, z.st_gid, z.st_nlink) != original:
            raise guard.Unavailable('identity-final-original-file9')
    return result
