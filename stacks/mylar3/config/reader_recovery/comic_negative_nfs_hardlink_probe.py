"""Finite disposable NFS hardlink probe; no native/library/reader grant.

An owning active-reader parent must supply the reviewed scope and continuous
Writer lease. This kernel alone observes local syscalls, never that custody.
"""
import base64
import copy
import errno
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import subprocess
import threading
import time
import weakref

_KEY = object()
_SEALS = weakref.WeakKeyDictionary()
MAX = 1024 * 1024


class Held(ValueError):
    pass


def need(value, reason):
    if not value:
        raise Held(reason)


def nine(z):
    return (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
            z.st_mode, z.st_uid, z.st_gid, z.st_nlink)


def five(z):
    return (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def decode(raw):
    def unique(items):
        value = {}
        for key, item in items:
            need(key not in value, 'duplicate-json')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(Held('number')))


def canonical(value):
    p = Path(value)
    need(p.is_absolute() and '..' not in p.parts and str(p) == str(value), 'path')
    for q in (p, *p.parents):
        need(not stat.S_ISLNK(os.lstat(q).st_mode), 'linked-path')
    return p


def ancestors(paths):
    result = {}
    for path in paths:
        for node in Path(path).parents:
            z = os.lstat(node)
            need(stat.S_ISDIR(z.st_mode), 'ancestor-type')
            old = result.setdefault(str(node), five(z))
            need(old == five(z), 'ancestor-conflict')
    return result


def raw_close(files, nodes, names, absent):
    for path, expected in names:
        if tuple(sorted(os.listdir(path))) != expected:
            raise Held('namespace-final')
    for path, expected in nodes:
        z = os.lstat(path)
        if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != expected:
            raise Held('ancestor-final')
    for path, expected in files:
        z = os.lstat(path)
        if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
                z.st_mode, z.st_uid, z.st_gid, z.st_nlink) != expected:
            raise Held('file-final')
    for path in absent:
        try:
            os.lstat(path)
        except FileNotFoundError:
            continue
        raise Held('absence-final')


def read_at(fd, name, expected, maximum=MAX):
    leaf = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
    try:
        need(nine(os.fstat(leaf)) == expected and stat.S_ISREG(expected[5])
             and expected[2] <= maximum, 'read-FD')
        blocks = []; remaining = expected[2]
        while remaining:
            part = os.read(leaf, min(65536, remaining))
            need(bool(part), 'read-short'); blocks.append(part); remaining -= len(part)
        raw = b''.join(blocks)
        names = sorted(os.listxattr(leaf))
        need(len(names) <= 64 and sum(len(os.fsencode(n)) for n in names) <= 65536, 'xattr-names')
        attrs = {}; total = 0
        for attr in names:
            value = os.getxattr(leaf, attr); total += len(value)
            need(total <= MAX, 'xattr-values')
            attrs[attr] = base64.b64encode(value).decode()
        need(nine(os.fstat(leaf)) == expected
             and nine(os.stat(name, dir_fd=fd, follow_symlinks=False)) == expected, 'read-final')
        return raw, attrs
    finally:
        os.close(leaf)


def checked_file(path, expected):
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        return read_at(parent, path.name, expected)[0]
    finally:
        os.close(parent)


def mount_namespace(host, rows, host_root, child_root, expected9, actual9, *, binding=None, retention9=None):
    """Join one original export to this exact owned RW subdirectory bind."""
    from pathlib import PurePosixPath
    keys={'source','target','fstype','fsroot','options','maj:min'}
    need(type(host) is dict and set(host)==keys and type(rows) is dict
         and set(rows)=={'source','target'},'namespace-mount-schema')
    def absolute(value):
        need(type(value) is str and value.startswith('/') and '\\' not in value
             and '\0' not in value and '..' not in value.split('/')
             and str(PurePosixPath(value))==value,'namespace-canonical-path')
        return PurePosixPath(value)
    for row in (host,*rows.values()):
        need(type(row) is dict and set(row)==keys and all(type(v) is str and v for v in row.values())
             and row['fstype']=='nfs4','namespace-nfs-row')
        absolute(row['target']);absolute(row['fsroot'])
    original=absolute(host_root);target=absolute(child_root);mountpoint=absolute(host['target'])
    need(original!=mountpoint and mountpoint in original.parents,'namespace-selected-host-subtree')
    bind_original,bind_target=original,target
    if binding is not None:
        need(type(binding) is dict and set(binding)=={'host_root','child_root','root5'},'namespace-retention-binding-schema')
        bind_original=absolute(binding['host_root']);bind_target=absolute(binding['child_root'])
        need(original==target and bind_original==bind_target and bind_original.name=='R'
             and re.fullmatch('archive-publication-[a-f0-9]{64}',bind_original.parent.name) is not None
             and original.parent.parent==bind_original
             and re.fullmatch(r'\.comic-nfs-private-[a-f0-9]{32}',original.parent.name) is not None
             and re.fullmatch(r'\.comic-nfs-probe-[a-f0-9]{32}',original.name) is not None
             and mountpoint in bind_original.parents,'namespace-exact-retention-subtree')
        root5=binding['root5']
        need(type(root5) is list and len(root5)==5 and all(type(v) is int for v in root5)
             and type(retention9) in (list,tuple) and len(retention9)==9
             and all(type(v) is int for v in retention9)
             and [retention9[i] for i in (0,1,5,6,7)]==root5
             and root5[0]>0 and root5[1]>0 and stat.S_ISDIR(root5[2])
             and stat.S_IMODE(root5[2])==0o700 and root5[3:]==[1000,1000],
             'namespace-original-retention-identity')
    else:need(retention9 is None,'namespace-unrequested-retention')
    expected_root=str(absolute(host['fsroot'])/bind_original.relative_to(mountpoint))
    def export(row):
        suffix='['+row['fsroot']+']'
        source=row['source']
        return source[:-len(suffix)] if source.endswith(suffix) else source
    need(type(expected9) in (list,tuple) and len(expected9)==9
         and all(type(v) is int for v in expected9)
         and type(actual9) in (list,tuple) and list(actual9)==list(expected9)
         and expected9[0]>0 and expected9[1]>0 and stat.S_ISDIR(expected9[5])
         and stat.S_IMODE(expected9[5])==0o700 and expected9[6]==1000,
         'namespace-original-root9')
    if binding is not None:need(retention9[0]==expected9[0] and retention9[1]!=expected9[1] and expected9[7]==1000,'namespace-distinct-retention-fixture')
    need(host['maj:min']==str(os.major(expected9[0]))+':'+str(os.minor(expected9[0])),'namespace-original-device-number')
    need(rows['source']==rows['target'],'namespace-one-child-bind')
    row=rows['source']
    need(row['target']==str(bind_target) and row['fsroot']==expected_root
         and export(row)==export(host) and row['maj:min']==host['maj:min']
         and row['options']==host['options']
         and 'rw' in row['options'].split(',') and 'ro' not in row['options'].split(','),
         'namespace-original-export-bind')
    proof=dict(version=1,kind='original-nfs-bind-namespace-v1',host=copy.deepcopy(host),
               rows=copy.deepcopy(rows),host_root=str(original),child_root=str(target),root9=list(expected9))
    if binding is not None:
        proof.update(version=2,kind='original-nfs-retention-bind-namespace-v2',binding=copy.deepcopy(binding),retention9=list(retention9))
    return proof


def mount(path):
    r = subprocess.run(['findmnt', '--json', '--target', str(path), '--output',
                        'SOURCE,TARGET,FSTYPE,FSROOT,OPTIONS,MAJ:MIN'], capture_output=True,
                       timeout=30, check=False)
    need(r.returncode == 0 and len(r.stdout) <= MAX and len(r.stderr) <= MAX, 'findmnt')
    value = decode(r.stdout)
    need(set(value) == {'filesystems'} and len(value['filesystems']) == 1, 'mount-shape')
    row = value['filesystems'][0]
    need(set(row) == {'source', 'target', 'fstype', 'fsroot', 'options', 'maj:min'}
         and row['fstype'] == 'nfs4', 'nfs-export')
    return row


def nfs_magic(path):
    # Same Linux statfs contract as the reviewed NFS V3 kernel.
    import ctypes
    class Statfs(ctypes.Structure):
        _fields_ = [('kind', ctypes.c_long), ('rest', ctypes.c_byte * 248)]
    value = Statfs(); libc = ctypes.CDLL(None, use_errno=True)
    need(libc.statfs(os.fsencode(path), ctypes.byref(value)) == 0, 'statfs')
    return value.kind


def observe_namespace(plan):
    root=canonical(plan['root']);src=root/'source';dst=root/'target'
    original=tuple(plan['root9']);actual=nine(os.lstat(root))
    rows={'source':mount(src),'target':mount(dst)}
    need(nfs_magic(src)==nfs_magic(dst)==0x6969,'namespace-actual-nfs-statfs')
    binding=None;retention9=None
    if rows['source']['target']!=str(root):
        retention=canonical(rows['source']['target']);retention9=nine(os.lstat(retention))
        binding=dict(host_root=str(retention),child_root=str(retention),root5=[retention9[i] for i in (0,1,5,6,7)])
    proof=mount_namespace(plan['mount'],rows,str(root),str(root),original,actual,binding=binding,retention9=retention9)
    if binding is not None:need(nine(os.lstat(retention))==retention9,'namespace-final-retention9')
    need(nine(os.lstat(root))==original,'namespace-final-original-root9')
    return proof


class HardlinkCanaryObservation:
    """Exact process-local syscall facts. No active-parent or mutation authority."""
    __slots__ = ('_binding', '_files', '_nodes', '_names', '_absent', '_thread', '__weakref__')

    def __init__(self, key, binding, files, nodes, names, absent):
        need(key is _KEY, 'owning-syscall-factory')
        self._binding = binding; self._files = files; self._nodes = nodes
        self._names = names; self._absent = absent; self._thread = threading.get_ident()
        _SEALS[self] = self._core()

    def _core(self):
        return encode((self._binding, self._files, self._nodes, self._names, self._absent, self._thread))

    def close(self):
        original = _SEALS.get(self)
        files = tuple(self._files); nodes = tuple(self._nodes)
        names = tuple(self._names); absent = tuple(self._absent)
        need(original == self._core() and threading.get_ident() == self._thread, 'observation-lifetime')
        if _SEALS.get(self) != original or self._core() != original:
            raise Held('observation-seal-final')
        raw_close(files, nodes, names, absent)
        for path, expected in names:
            if tuple(sorted(os.listdir(path))) != expected:raise Held('namespace-final')
        for path, expected in nodes:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=expected:raise Held('ancestor-final')
        for path, expected in files:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=expected:raise Held('file-final')
        for path in absent:
            try:os.lstat(path)
            except FileNotFoundError:continue
            raise Held('absence-final')

    @property
    def binding(self):
        value = copy.deepcopy(self._binding); self.close(); return value


def run(plan_ref, source_ref, *, namespace=None):
    """Fresh single diagnostic; existing output/fixtures refuse, never replay."""
    namespace_caller=namespace
    namespace_tape=None if namespace is None else encode(namespace)
    if namespace is not None:namespace=decode(namespace_tape)
    started = time.monotonic()
    own = Path(__file__).absolute(); inp = Path(plan_ref['path'])
    nodes = ancestors([own, inp])
    files = {str(own): nine(os.lstat(own)), str(inp): nine(os.lstat(inp))}
    need(source_ref['path'] == str(own) and tuple(source_ref['signature9']) == files[str(own)], 'own-source')
    for ref in (source_ref, plan_ref):
        need(set(ref) == {'path', 'signature9', 'sha256'}, 'original-ref')
        p = canonical(ref['path']); expected = files[str(p)]
        need(tuple(ref['signature9']) == expected and expected[8] == 1
             and expected[6] == os.geteuid() == 1000, 'original-ref-identity')
        raw = checked_file(p, expected)
        need(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'original-ref-hash')
    need(stat.S_IMODE(files[str(inp)][5]) == 0o600, 'private-input')
    plan = decode(checked_file(inp, files[str(inp)]))
    need(set(plan) == {'version', 'kind', 'nonce', 'root', 'source_parent9', 'target_parent9',
                       'root9', 'device', 'mount', 'forbidden_roots', 'seconds'}, 'plan-schema')
    need(type(plan['version']) is int and plan['version'] == 1
         and plan['kind'] == 'reviewed-disposable-hardlink-nfs-canary'
         and type(plan['nonce']) is str and len(plan['nonce']) == 64
         and all(x in '0123456789abcdef' for x in plan['nonce']), 'plan-kind')
    need(type(plan['seconds']) is int and 1 <= plan['seconds'] <= 120, 'deadline-bound')
    deadline = started + plan['seconds']
    root9 = tuple(plan['root9']); src9 = tuple(plan['source_parent9']); dst9 = tuple(plan['target_parent9'])
    root = canonical(plan['root']); src = root / 'source'; dst = root / 'target'
    protected = tuple(canonical(p) for p in plan['forbidden_roots'])
    need(1 <= len(protected) <= 32 and len(set(protected)) == len(protected), 'protected-roots')
    for p in (root, src, dst, *protected):
        more = ancestors([p / 'child'])
        for name, value in more.items():
            need(name not in nodes or nodes[name] == value, 'original-ancestor-conflict'); nodes[name] = value
    for p, v in ((root, root9), (src, src9), (dst, dst9)):
        need(nine(os.lstat(p)) == v and stat.S_ISDIR(v[5]) and stat.S_IMODE(v[5]) == 0o700
             and v[6] == os.geteuid() and v[0] == plan['device'], 'private-parent-original')
    need(src9[:2] != dst9[:2] and all(not root.is_relative_to(p) and not p.is_relative_to(root)
         and tuple(nine(os.lstat(p))[:2]) not in (src9[:2], dst9[:2]) for p in protected), 'protected-overlap')
    roots = {str(p): nine(os.lstat(p)) for p in protected}
    need(os.listdir(root) == ['source', 'target'] or set(os.listdir(root)) == {'source', 'target'}, 'new-root')
    need(not os.listdir(src) and not os.listdir(dst), 'empty-parents')
    if namespace is None:
        need(mount(src) == plan['mount'] == mount(dst) and nfs_magic(src) == nfs_magic(dst) == 0x6969, 'same-nfs-export')
    else:
        need(type(namespace) is dict and type(namespace.get('version')) is int and namespace==observe_namespace(plan),'namespace-original-local-rows')
        need(encode(namespace_caller)==namespace_tape,'namespace-original-caller-tape')
    retention_original=() if namespace is None or namespace['version']==1 else ((namespace['binding']['child_root'],tuple(namespace['retention9'])),)
    original = tuple(files.items()) + tuple(roots.items()) + retention_original + ((str(root), root9), (str(src), src9), (str(dst), dst9))
    raw_close(original, tuple(nodes.items()), ((str(root), ('source', 'target')), (str(src), ()), (str(dst), ())), ())
    fds = []
    try:
        for path, expected in ((root, root9), (src, src9), (dst, dst9)):
            fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            fds.append(fd)
            z = os.fstat(fd)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink) != expected:
                raise Held('opened-parent-original-FD')
        # Every descriptor is bound before the first file creation. A transient
        # ancestor alias opening a foreign FD cannot write through this gate.
        raw_close(original, tuple(nodes.items()), ((str(root), ('source', 'target')), (str(src), ()), (str(dst), ())), ())
        for path, expected in original:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=expected:
                raise Held('prewrite-original-file')
        for path, expected in nodes.items():
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=expected:raise Held('prewrite-original-ancestor')
        for path, names in ((root, ('source','target')), (src, ()), (dst, ())):
            if tuple(sorted(os.listdir(path)))!=names:raise Held('prewrite-original-namespace')
        for fd, expected in zip(fds, (root9, src9, dst9)):
            z=os.fstat(fd)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=expected:
                raise Held('prewrite-original-FD-final')
    except BaseException:
        for fd in fds:os.close(fd)
        raise
    rfd, sfd, tfd = fds
    parent_values = {str(root): root9, str(src): src9, str(dst): dst9}; control_names = set()
    expected_names = {str(src): set(), str(dst): set()}; leaves = {}; records = []

    def close_current():
        admitted = tuple(files.items()) + tuple(roots.items()) + retention_original + tuple(parent_values.items()) + tuple(leaves.items())
        captured_nodes = tuple(nodes.items())
        captured_names = ((str(root), tuple(sorted({'source', 'target'} | control_names))),
                          *( (p, tuple(sorted(v))) for p, v in expected_names.items()))
        missing = tuple(str(p / n) for p, ns in ((src, ('source.bin', 'collision.bin')), (dst, ('retained.bin', 'foreign.bin')))
                        for n in ns if n not in expected_names[str(p)])
        need(time.monotonic() < deadline, 'probe-deadline')
        for fd, p in zip(fds, (root, src, dst)):
            need(five(os.fstat(fd)) == nodes[str(p)], 'parent-FD')
        raw_close(admitted, captured_nodes, captured_names, missing)
        return admitted, captured_nodes, captured_names, missing

    def write(fd, parent, name, raw):
        expected = parent_values[str(parent)]
        z=os.fstat(fd)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=expected:
            raise Held('write-parent-original-FD')
        z=os.lstat(parent)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=expected:
            raise Held('write-parent-original-path')
        leaf = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=fd)
        # Creation is the sole owned directory metadata transition. Capture its
        # actual full9 immediately, before write/fsync/readback callbacks.
        z=os.fstat(fd)
        parent_values[str(parent)]=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
        try:
            need(os.write(leaf, raw) == len(raw), 'write-short'); os.fsync(leaf)
        finally:
            os.close(leaf)
        os.fsync(fd)
        value = nine(os.stat(name, dir_fd=fd, follow_symlinks=False))
        need(stat.S_ISREG(value[5]) and stat.S_IMODE(value[5])==0o600 and value[6]==os.geteuid() and value[8]==1, 'exclusive-created-attributes')
        readback, attrs = read_at(fd, name, value)
        need(readback == raw, 'exclusive-readback')
        return value, attrs

    def observe_transition(previous, link_count):
        value = nine(os.stat('source.bin' if 'source.bin' in expected_names[str(src)] else 'retained.bin',
                            dir_fd=sfd if 'source.bin' in expected_names[str(src)] else tfd, follow_symlinks=False))
        need(tuple(value[i] for i in (0, 1, 2, 3, 5, 6, 7)) == tuple(previous[i] for i in (0, 1, 2, 3, 5, 6, 7))
             and value[8] == link_count and value[4] >= previous[4], 'finite-link-metadata')
        for fd, p, name in ((sfd, src, 'source.bin'), (tfd, dst, 'retained.bin')):
            if name not in expected_names[str(p)]:
                leaves.pop(str(p / name), None); continue
            need(nine(os.stat(name, dir_fd=fd, follow_symlinks=False)) == value, 'same-link-incarnation')
            raw, attrs = read_at(fd, name, value)
            need(raw == source_bytes and attrs == source_attrs, 'source-byte-xattr-preservation')
            leaves[str(p / name)] = value
        parent_values.update({str(src): nine(os.fstat(sfd)), str(dst): nine(os.fstat(tfd))})
        close_current(); return value

    try:
        source_bytes = b'owned NFS hardlink canary\x00'
        source9, source_attrs = write(sfd, src, 'source.bin', source_bytes)
        collision9, _ = write(sfd, src, 'collision.bin', b'owned collision source\x01')
        foreign9, foreign_attrs = write(tfd, dst, 'foreign.bin', b'foreign collision destination\x02')
        leaves.update({str(src/'source.bin'): source9, str(src/'collision.bin'): collision9, str(dst/'foreign.bin'): foreign9})
        expected_names[str(src)] = {'source.bin', 'collision.bin'}; expected_names[str(dst)] = {'foreign.bin'}
        close_current()
        current = source9
        for action, count in (('stage', 2), ('collision', 2), ('retire', 1), ('restore', 2), ('unstage', 1)):
            intent = dict(version=1, phase=action, source9=current, nonce=plan['nonce'], publication_authority=False)
            name = action + '-intent.json'; raw = encode(intent)
            value, _ = write(rfd, root, name, raw); files[str(root/name)] = value; control_names.add(name)
            # All encoding/readback/FD callbacks end before the syscall closure.
            vectors = close_current()
            for path, expected in vectors[2]:
                if tuple(sorted(os.listdir(path))) != expected:raise Held('namespace-final')
            for path, expected in vectors[1]:
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=expected:raise Held('ancestor-final')
            for path, expected in vectors[0]:
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=expected:raise Held('file-final')
            for path in vectors[3]:
                try:os.lstat(path)
                except FileNotFoundError:continue
                raise Held('absence-final')
            if action == 'stage':
                os.link('source.bin', 'retained.bin', src_dir_fd=sfd, dst_dir_fd=tfd, follow_symlinks=False)
                expected_names[str(dst)].add('retained.bin')
            elif action == 'collision':
                try:
                    os.link('collision.bin', 'foreign.bin', src_dir_fd=sfd, dst_dir_fd=tfd, follow_symlinks=False)
                except OSError as error:
                    need(error.errno == errno.EEXIST, 'collision-not-EEXIST')
                else:
                    raise Held('collision-overwrite')
                need(read_at(tfd, 'foreign.bin', foreign9) == (b'foreign collision destination\x02', foreign_attrs)
                     and nine(os.stat('collision.bin', dir_fd=sfd, follow_symlinks=False)) == collision9, 'foreign-collision-preservation')
            elif action == 'retire':
                os.unlink('source.bin', dir_fd=sfd); expected_names[str(src)].remove('source.bin')
            elif action == 'restore':
                os.link('retained.bin', 'source.bin', src_dir_fd=tfd, dst_dir_fd=sfd, follow_symlinks=False)
                expected_names[str(src)].add('source.bin')
            else:
                os.unlink('retained.bin', dir_fd=tfd); expected_names[str(dst)].remove('retained.bin')
            os.fsync(sfd); os.fsync(tfd)
            current = observe_transition(current, count); records.append(dict(action=action, source9=current, nlink=count))
        result = dict(version=1, kind='disposable-hardlink-nfs-syscall-observation', nonce=plan['nonce'],
                      transitions=records, collision_errno=errno.EEXIST, source_sha256=hashlib.sha256(source_bytes).hexdigest(),
                      source_original9=source9, source_xattrs=source_attrs, foreign_original9=foreign9,
                      mount=plan['mount'], device=plan['device'], fixtures_retained=True,
                      actual_library_platform_verified=False, native_grant=False, publication_authority=False,
                      reader_resume_authority=False, active_parent_custody_verified=False)
        raw = encode(result); value, _ = write(rfd, root, 'result.json', raw)
        files[str(root/'result.json')] = value; control_names.add('result.json')
        vectors = close_current()
        observation = HardlinkCanaryObservation(_KEY, result, *vectors)
        for fd in fds:
            os.close(fd)
        fds.clear()
        # Object encoding and descriptor close precede the final raw closure.
        need(time.monotonic() < deadline, 'terminal-deadline')
        raw_close(*vectors)
        for path, expected in vectors[2]:
            if tuple(sorted(os.listdir(path))) != expected:raise Held('namespace-final')
        for path, expected in vectors[1]:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=expected:raise Held('ancestor-final')
        for path, expected in vectors[0]:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=expected:raise Held('file-final')
        for path in vectors[3]:
            try:os.lstat(path)
            except FileNotFoundError:continue
            raise Held('absence-final')
        return observation
    except BaseException:
        raise Held('canary-uncertain-fixtures-and-intents-retained-no-replay') from None
    finally:
        for fd in fds:
            os.close(fd)


if __name__ == '__main__':
    raise SystemExit('Default-off: owning active-parent/Writer and reviewed NFS scope required')
