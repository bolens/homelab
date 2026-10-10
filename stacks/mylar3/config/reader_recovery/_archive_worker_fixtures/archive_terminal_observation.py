"""Disabled bounded worker facts over original pipes; never grants authority."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import select
import secrets
import sqlite3
import sys
import threading
import time
import weakref

ENABLED = False
PROTOCOL = 'archive-terminal-worker-facts-v1'
LIMIT = 4 * 1024 ** 2
COUNT = 8192
STREAM = 512 * 1024 ** 2
READ_ROOTS = ('/state', '/mylar', '/mylar-writer', '/data/comics', '/data/manga',
              '/completed-comics', '/ddl-cache')
RIGHTS = dict.fromkeys(('publication', 'ordinary_import', 'index', 'cleanup', 'replay', 'resume'), False)
VECTORS = frozenset(('files9', 'nodes5', 'namespaces', 'claims', 'absent', 'hashes'))
_CHANNEL_ORIGINALS = weakref.WeakKeyDictionary()
_SPENT = weakref.WeakSet()
_LAUNCH_KEY = object()
_LAUNCHES = weakref.WeakKeyDictionary()
WIRE2 = 'archive-terminal-worker-facts-v2'


class _Launch:
    __slots__ = ('nonce', 'operation', 'bind_roots', 'argv', 'pid', 'thread', 'orig_argv', '__weakref__')
    def __init__(self, key, nonce, operation, roots, argv, orig_argv):
        if key is not _LAUNCH_KEY: raise Held('owning-launch-only')
        self.nonce=nonce;self.operation=operation;self.bind_roots=roots;self.argv=argv
        self.pid=os.getpid();self.thread=threading.get_ident();self.orig_argv=orig_argv
        _LAUNCHES[self]=(nonce,operation,roots,argv,self.pid,self.thread,orig_argv)


def reviewed_launch(argv):
    original_argv=tuple(sys.orig_argv)
    # Exact fixed owning CLI, never a saved DTO or caller-chosen module/FD.
    need(type(argv) is tuple and len(argv)==8 and argv[1]=='--reviewed-original-parent-v1'
         and argv[2]=='--nonce' and argv[4]=='--operation-id' and argv[6]=='--bind-roots', 'fixed-launch-argv')
    nonce=digest(argv[3]);operation=digest(argv[5]);need(len(argv[7].encode())<=4096,'launch-root-bound')
    wrapped=decode(b'{"roots":'+argv[7].encode()+b'}');need(set(wrapped)=={'roots'},'launch-root-wrapper');roots=wrapped['roots']
    need(type(roots) is list and 0<len(roots)<=len(READ_ROOTS) and all(type(r) is str for r in roots)
         and roots==sorted(set(roots)), 'launch-root-schema')
    for value in roots:
        root=path(value)
        need(any(root==Path(r) or Path(r) in root.parents for r in READ_ROOTS), 'launch-root-scope')
    need(Path(argv[0]).absolute()==Path(__file__).absolute(), 'installed-owning-entry')
    need(tuple(sys.orig_argv)==original_argv,'original-interpreter-argv')
    return _Launch(_LAUNCH_KEY,nonce,operation,tuple(roots),argv,original_argv)



class Held(ValueError):
    pass


def need(value, reason):
    if not value:
        raise Held(reason)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def decode(raw):
    need(type(raw) is bytes and 0 < len(raw) <= LIMIT, 'frame-size')
    # Bound nesting before parser recursion; brackets inside strings do not count.
    depth = 0; quoted = False; escaped = False
    for byte in raw:
        if quoted:
            if escaped: escaped = False
            elif byte == 92: escaped = True
            elif byte == 34: quoted = False
        elif byte == 34: quoted = True
        elif byte in (91, 123):
            depth += 1; need(depth <= 24, 'frame-depth')
        elif byte in (93, 125):
            depth -= 1; need(depth >= 0, 'frame-depth')
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'duplicate-key'); result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_constant=lambda _: need(False, 'nonfinite'))
    except (UnicodeError, RecursionError, ValueError) as exc:
        raise Held('malformed-frame') from exc
    need(type(value) is dict and encode(value) == raw, 'canonical-frame')
    return value


def nine(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns,
            s.st_mode, s.st_uid, s.st_gid, s.st_nlink)


def five(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid)


def path(value, source=False):
    need(type(value) is str and 0 < len(value.encode()) <= 4096 and '\0' not in value,
         'path-type')
    p = Path(value)
    need(p.is_absolute() and '..' not in p.parts and str(p) == value, 'path-spelling')
    need(source or any(p == Path(root) or Path(root) in p.parents for root in READ_ROOTS),
         'existing-bind-scope')
    return p


def vector(value, size):
    need(type(value) is list and len(value) == size and all(type(n) is int for n in value),
         'vector-type')
    return tuple(value)


def digest(value):
    need(type(value) is str and re.fullmatch('[a-f0-9]{64}', value) is not None, 'digest-type')
    return value


def owner(value):
    need(type(value) is dict and set(value) == {'table', 'issueid', 'parentcomicid', 'releasecomicid'}
         and value['table'] in ('issues', 'annuals'), 'exact-owner')
    need(all(type(value[k]) is str and re.fullmatch('[1-9][0-9]{0,15}', value[k]) for k in
             ('issueid', 'parentcomicid', 'releasecomicid')), 'exact-owner')
    need(value['table'] == 'annuals' or value['parentcomicid'] == value['releasecomicid'], 'release-owner')
    return value


def frame(value, *, local):
    need(type(value) is dict and set(value) == VECTORS, 'frame-keys')
    result = {k: [] for k in VECTORS}
    for key in VECTORS:
        rows = value[key]; need(type(rows) is list and len(rows) <= COUNT, 'vector-count')
        seen = set()
        for row in rows:
            if key == 'absent':
                p = str(path(row, source=not local)); val = p
            else:
                need(type(row) is list and len(row) == 2, 'vector-row')
                p = str(path(row[0], source=not local or key == 'nodes5')); v = row[1]
                if local and key == 'nodes5':
                    need(any(Path(p) == Path(root) or Path(root) in Path(p).parents or Path(p) in Path(root).parents
                             for root in READ_ROOTS), 'node-existing-bind-ancestor')
                if key == 'files9': val = (p, vector(v, 9))
                elif key == 'nodes5': val = (p, vector(v, 5))
                elif key == 'claims':
                    if v is None: val = (p, None)
                    else:
                        need(type(v) is list and len(v) == 6 and all(type(n) is int for n in v[:5])
                             and (type(v[5]) is int or v[5] is None and v[2] & 0o170000 == 0o040000), 'claim-type')
                        val = (p, tuple(v))
                elif key == 'hashes': val = (p, digest(v))
                else:
                    need(type(v) is list and len(v) <= COUNT
                         and all(type(n) is str and n not in ('.', '..') and '/' not in n and '\0' not in n for n in v)
                         and v == sorted(set(v)), 'namespace-type')
                    val = (p, tuple(v))
            need(p not in seen, 'duplicate-vector'); seen.add(p); result[key].append(val)
    need(set(dict(result['hashes'])) <= set(dict(result['files9'])), 'hash-original-missing')
    return {k: tuple(v) for k, v in result.items()}


def raw_close(f):
    # No digest/SQL/serialization helper follows this primitive closure.
    for p, names in f['namespaces']:
        if tuple(sorted(os.listdir(p))) != names: raise Held('namespace-drift')
    for p, v in f['nodes5']:
        z = os.lstat(p)
        if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != v: raise Held('node-drift')
    for p, v in f['files9']:
        z = os.lstat(p)
        if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode,
                z.st_uid, z.st_gid, z.st_nlink) != v: raise Held('file-drift')
    for p in f['absent']:
        try: os.lstat(p)
        except FileNotFoundError: continue
        raise Held('absence-drift')
    for p, v in f['claims']:
        try: z = os.lstat(p)
        except FileNotFoundError:
            if v is None: continue
            raise Held('claim-drift')
        got = (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid,
               None if z.st_mode & 0o170000 == 0o040000 else z.st_nlink)
        if got != v: raise Held('claim-drift')


def read_file(p, expected):
    need(expected[5] & 0o170000 == 0o100000 and expected[8] == 1
         and 0 <= expected[2] <= STREAM, 'selected-regular-file')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        need(nine(os.fstat(fd)) == expected, 'original-file-FD')
        h = hashlib.sha256(); size = 0
        while block := os.read(fd, 1024 ** 2):
            size += len(block); need(size <= STREAM, 'stream-bound'); h.update(block)
        need(size == expected[2] and nine(os.fstat(fd)) == expected
             and nine(os.lstat(p)) == expected, 'file-read-drift')
        return h.hexdigest()
    finally: os.close(fd)


def sql_snapshot(p, expected):
    companions = [str(p) + suffix for suffix in ('-journal', '-wal', '-shm')]
    need(not any(os.path.lexists(c) for c in companions), 'sqlite-companion-present')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        need(nine(os.fstat(fd)) == expected, 'catalog-FD')
        db = sqlite3.connect('file:/proc/self/fd/' + str(fd) + '?mode=ro&immutable=1', uri=True)
        try:
            db.execute('PRAGMA query_only=ON')
            need(db.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'catalog-integrity')
            schema = db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').fetchall()
            need(len(schema) <= 128, 'schema-bound'); tables = {}; count = 0
            for kind, name, _, _ in schema:
                if kind != 'table': continue
                need(re.fullmatch('[a-zA-Z_][a-zA-Z0-9_]*', name), 'table-name')
                columns = [r[1] for r in db.execute('PRAGMA table_info("' + name + '")')]
                rows = []
                for row in db.execute('SELECT * FROM "' + name + '"'):
                    count += 1; need(count <= 100000, 'row-bound')
                    need(all(type(v) in (str, int, float, bytes) or v is None for v in row)
                         and all(type(v) is not float or math.isfinite(v) for v in row), 'SQL-value')
                    rows.append([{'blob': v.hex()} if type(v) is bytes else v for v in row])
                rows.sort(key=encode); tables[name] = {'columns': columns, 'rows': rows}
            answer = {'schema': schema, 'tables': tables}
            need(len(encode(answer)) <= 64 * 1024 ** 2, 'catalog-bytes')
        finally: db.close()
        need(nine(os.fstat(fd)) == expected and nine(os.lstat(p)) == expected
             and not any(os.path.lexists(c) for c in companions), 'catalog-read-drift')
        return answer
    finally: os.close(fd)


def catalog_owner(snapshot, selected, native_target):
    rows = []
    for table in ('issues', 'annuals'):
        t = snapshot['tables'].get(table)
        need(t is not None, 'complete-catalog-tables')
        need({'IssueID', 'ComicID', 'Location', 'Status'} <= set(t['columns']), 'catalog-columns')
        for row in t['rows']:
            d = dict(zip(t['columns'], row))
            if d['IssueID'] == selected['issueid']: rows.append((table, d))
    need(len(rows) == 1 and rows[0][0] == selected['table'], 'unique-current-owner')
    t, row = rows[0]
    need(row['ComicID'] == selected['parentcomicid'] and row['Status'] in ('Downloaded', 'Archived')
         and (t == 'issues' or row.get('ReleaseComicID') == selected['releasecomicid']
              and row.get('Deleted') in (None, 0)), 'current-release-owner')
    comics = snapshot['tables'].get('comics'); need(comics is not None, 'catalog-parent')
    parents = [dict(zip(comics['columns'], r)) for r in comics['rows']]
    parents = [r for r in parents if r.get('ComicID') == selected['parentcomicid']]
    need(len(parents) == 1 and type(parents[0].get('ComicLocation')) is str
         and type(row['Location']) is str and str(Path(parents[0]['ComicLocation']) / row['Location']) == native_target,
         'current-catalog-target')
    return {'table': t, 'issueid': row['IssueID'], 'parentcomicid': row['ComicID'],
            'releasecomicid': selected['releasecomicid'], 'status': row['Status'], 'native_path': native_target}


class ParentChannel:
    """Actual inherited pipe; a caller packet cannot construct a closed observation."""
    __slots__ = ('read_fd', 'write_fd', 'facts', 'pid', 'thread', 'deadline', 'source',
                 'roots', 'used', 'implementation', 'constants', 'launch', 'birth', '__weakref__')

    def __init__(self, read_fd=0, write_fd=1, *, launch=None):
        self.launch=launch;self.birth=None
        if launch is None and ENABLED is not True:raise Held('disabled')
        self.source = _source_original()
        if launch is None: pass
        else:
            need(type(launch) is _Launch and _LAUNCHES.get(launch)==(launch.nonce,launch.operation,launch.bind_roots,launch.argv,launch.pid,launch.thread,launch.orig_argv)
                 and tuple(sys.argv)==launch.argv and tuple(sys.orig_argv)==launch.orig_argv and os.getpid()==launch.pid and threading.get_ident()==launch.thread, 'original-owning-launch')
            # All receiver-only ancestor facts are captured before source/helper reads.
            nodes={}
            source_nodes=dict(self.source['nodes5'])
            for value in launch.bind_roots:
                for n in Path(value).parents:
                    if any(n==Path(r) or Path(r) in n.parents for r in launch.bind_roots): continue
                    v=five(os.lstat(n));need(v[2]&0o170000==0o040000, 'receiver-parent-directory')
                    need(str(n) not in source_nodes or source_nodes[str(n)]==v, 'receiver-source-parent-conflict')
                    need(str(n) not in nodes or nodes[str(n)]==v, 'receiver-parent-conflict');nodes[str(n)]=v
            self.birth=tuple(sorted(nodes.items()))
        self.read_fd = read_fd; self.write_fd = write_fd
        self.facts = (five(os.fstat(read_fd)), five(os.fstat(write_fd)))
        need(all(v[2] & 0o170000 == 0o010000 for v in self.facts), 'inherited-pipes')
        self.pid = os.getpid(); self.thread = threading.get_ident()
        self.deadline = time.monotonic() + 90; self.roots = tuple(READ_ROOTS)
        self.used = False; self.implementation = _PINNED_IMPLEMENTATIONS
        self.constants = (ENABLED, PROTOCOL, WIRE2, LIMIT, COUNT, STREAM, tuple(READ_ROOTS),
                          frozenset(VECTORS), tuple(sorted(RIGHTS.items())), str(__file__))
        _CHANNEL_ORIGINALS[self] = (self.read_fd, self.write_fd, self.facts, self.pid, self.thread,
            self.deadline, self.roots, tuple((k, self.source[k]) for k in sorted(VECTORS)), self.implementation, self.constants, self.launch, self.birth, None if launch is None else _LAUNCHES.get(launch))

    def read(self):
        data = bytearray()
        while not data.endswith(b'\n'):
            need(time.monotonic() < self.deadline and len(data) <= LIMIT, 'pipe-bound')
            ready = select.select([self.read_fd], [], [], max(0, self.deadline - time.monotonic()))[0]
            need(bool(ready), 'parent-timeout')
            b = os.read(self.read_fd, 1); need(bool(b), 'parent-lost'); data.extend(b)
        need(len(data) <= LIMIT + 1, 'pipe-bound')
        return bytes(data[:-1])

    def send(self, raw, *, local=None):
        need(type(raw) is bytes and 0 < len(raw) <= LIMIT, 'reply-size')
        original=_CHANNEL_ORIGINALS.get(self);need(original is not None,'send-original-channel')
        channel=self
        combined={k:tuple(v) for k,v in (local or {k:() for k in VECTORS}).items()}
        for key in ('files9','nodes5'):
            rows=dict(combined[key])
            for p,v in dict(original[7])[key]:
                need(p not in rows or rows[p]==v,'send-original-source-conflict');rows[p]=v
            if key=='nodes5' and original[10] is not None:
                for p,v in original[11]:need(p not in rows or rows[p]==v,'send-original-birth-conflict');rows[p]=v
            combined[key]=tuple(rows.items())
        pending=memoryview(raw+b'\n')
        while pending:
            remaining=original[5]-time.monotonic()
            need(remaining>0 and bool(select.select([],[original[1]],[],remaining)[1]),'reply-timeout')
            close_originals(channel,original,combined)
            # Helper/FD/time callbacks have finished BEFORE the inline closure.
            observed_pid=os.getpid();observed_thread=threading.get_ident();observed_time=time.monotonic()
            # Complete helper work precedes the final inline primitive closure. It uses
            # the same detached originals, never newly observed replacement vectors.
            for p, names in combined['namespaces']:
                if tuple(sorted(os.listdir(p))) != names: raise Held('final-namespace-drift')
            for p, v in combined['claims']:
                try: z = os.lstat(p)
                except FileNotFoundError:
                    if v is None: continue
                    raise Held('final-claim-drift')
                got = (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid,
                       None if z.st_mode & 0o170000 == 0o040000 else z.st_nlink)
                if got != v: raise Held('final-claim-drift')
            for p in combined['absent']:
                try: os.lstat(p)
                except FileNotFoundError: continue
                raise Held('final-absence-drift')
            for p, v in combined['nodes5']:
                z = os.lstat(p)
                if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != v: raise Held('final-node-drift')
            for p, v in combined['files9']:
                z = os.lstat(p)
                if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode,
                        z.st_uid, z.st_gid, z.st_nlink) != v: raise Held('final-file-drift')
            # No parser/hash/SQL/serializer/config/helper closure follows these loops.
            if (channel.read_fd, channel.write_fd, channel.facts, channel.pid, channel.thread,
                channel.deadline, channel.roots, tuple((k, channel.source[k]) for k in sorted(VECTORS)), channel.implementation, channel.constants, channel.launch, channel.birth, original[12]) != original:
                raise Held('original-channel-drift')
            if observed_pid != original[3] or observed_thread != original[4] or tuple(READ_ROOTS) != original[6]:
                raise Held('original-process-or-config-drift')
            if observed_time >= original[5]: raise Held('deadline')
            if _CHANNEL_ORIGINALS.get(channel) is not original or channel not in _SPENT: raise Held('original-channel-registry')
            if not channel.used or (original[10] is None and ENABLED is not True) or (ENABLED, PROTOCOL, WIRE2, LIMIT, COUNT, STREAM, tuple(READ_ROOTS),
                    frozenset(VECTORS), tuple(sorted(RIGHTS.items())), str(__file__)) != original[9]: raise Held('original-constant-drift')
            launch=original[10]
            if launch is not None and (type(launch) is not _Launch or _LAUNCHES.get(launch) is not original[12] or (launch.nonce,launch.operation,launch.bind_roots,launch.argv,launch.pid,launch.thread,launch.orig_argv)!=original[12]
                    or tuple(sys.argv)!=launch.argv or tuple(sys.orig_argv)!=launch.orig_argv or launch.pid!=observed_pid or launch.thread!=observed_thread):raise Held('original-launch-registry')
            for n, function, code in original[8]:
                got = _Launch.__init__ if n=='launch_init' else getattr(ParentChannel, '__init__' if n == 'init' else n) if n in ('init', 'read', 'send') else globals().get(n)
                if got is not function or got.__code__ is not code: raise Held('implementation-drift')
            n=os.write(original[1],pending[:4096]);need(n>0,'reply-lost');pending=pending[n:]


def _source_original():
    p = Path(__file__).absolute()
    files = ((str(p), nine(os.lstat(p))),)
    nodes = tuple((str(n), five(os.lstat(n))) for n in p.parents)
    need(files[0][1][5] & 0o170000 == 0o100000 and files[0][1][8] == 1
         and all(v[2] & 0o170000 == 0o040000 for _, v in nodes), 'source-original')
    return {'files9': files, 'nodes5': nodes, 'namespaces': (), 'claims': (), 'absent': (), 'hashes': ()}


def _implementation():
    names = ('need', 'nine', 'five', 'encode', 'decode', 'path', 'vector', 'digest', 'owner', 'frame', 'raw_close',
             'read_file', 'sql_snapshot', 'catalog_owner', 'exchange', '_source_original',
             'close_originals', '_implementation', 'reviewed_launch')
    return tuple((n, globals()[n], globals()[n].__code__) for n in names) + (
        ('init', ParentChannel.__init__, ParentChannel.__init__.__code__),
        ('launch_init', _Launch.__init__, _Launch.__init__.__code__),
        ('read', ParentChannel.read, ParentChannel.read.__code__),
        ('send', ParentChannel.send, ParentChannel.send.__code__))


def close_originals(channel, original, local):
    # Original channel/implementation tuple was retained BEFORE any callbacks.
    for n, function, code in channel.implementation:
        got = _Launch.__init__ if n=='launch_init' else getattr(ParentChannel, '__init__' if n == 'init' else n) if n in ('init', 'read', 'send') else globals().get(n)
        if got is not function or got.__code__ is not code: raise Held('implementation-drift')
    combined = {k: tuple(v) for k, v in local.items()}
    original_source = dict(original[7])
    for key in ('files9', 'nodes5'):
        rows = dict(combined[key])
        for p, v in original_source[key]:
            if p in rows and rows[p] != v: raise Held('original-source-conflict')
            rows[p] = v
        combined[key] = tuple(rows.items())
    if original[10] is not None:
        rows=dict(combined['nodes5'])
        for p,v in original[11]:
            if p in rows and rows[p]!=v:raise Held('receiver-original-node-conflict')
            rows[p]=v
        combined['nodes5']=tuple(rows.items())
    raw_close(combined)
    for fd, expected in zip(original[:2], original[2]):
        z = os.fstat(fd)
        if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != expected: raise Held('pipe-FD-drift')
    observed_pid = os.getpid(); observed_thread = threading.get_ident(); observed_time = time.monotonic()
    # Complete helper work precedes the final inline primitive closure. It uses
    # the same detached originals, never newly observed replacement vectors.
    for p, names in combined['namespaces']:
        if tuple(sorted(os.listdir(p))) != names: raise Held('final-namespace-drift')
    for p, v in combined['claims']:
        try: z = os.lstat(p)
        except FileNotFoundError:
            if v is None: continue
            raise Held('final-claim-drift')
        got = (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid,
               None if z.st_mode & 0o170000 == 0o040000 else z.st_nlink)
        if got != v: raise Held('final-claim-drift')
    for p in combined['absent']:
        try: os.lstat(p)
        except FileNotFoundError: continue
        raise Held('final-absence-drift')
    for p, v in combined['nodes5']:
        z = os.lstat(p)
        if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != v: raise Held('final-node-drift')
    for p, v in combined['files9']:
        z = os.lstat(p)
        if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode,
                z.st_uid, z.st_gid, z.st_nlink) != v: raise Held('final-file-drift')
    # No parser/hash/SQL/serializer/config/helper closure follows these loops.
    if (channel.read_fd, channel.write_fd, channel.facts, channel.pid, channel.thread,
        channel.deadline, channel.roots, tuple((k, channel.source[k]) for k in sorted(VECTORS)), channel.implementation, channel.constants, channel.launch, channel.birth, original[12]) != original:
        raise Held('original-channel-drift')
    if observed_pid != original[3] or observed_thread != original[4] or tuple(READ_ROOTS) != original[6]:
        raise Held('original-process-or-config-drift')
    if observed_time >= original[5]: raise Held('deadline')
    if _CHANNEL_ORIGINALS.get(channel) is not original or channel not in _SPENT: raise Held('original-channel-registry')
    if not channel.used or (original[10] is None and ENABLED is not True) or (ENABLED, PROTOCOL, WIRE2, LIMIT, COUNT, STREAM, tuple(READ_ROOTS),
            frozenset(VECTORS), tuple(sorted(RIGHTS.items())), str(__file__)) != original[9]: raise Held('original-constant-drift')
    launch=original[10]
    if launch is not None and (type(launch) is not _Launch or _LAUNCHES.get(launch) is not original[12] or (launch.nonce,launch.operation,launch.bind_roots,launch.argv,launch.pid,launch.thread,launch.orig_argv)!=original[12]
            or tuple(sys.argv)!=launch.argv or tuple(sys.orig_argv)!=launch.orig_argv or launch.pid!=observed_pid or launch.thread!=observed_thread):raise Held('original-launch-registry')
    for n, function, code in original[8]:
        got = _Launch.__init__ if n=='launch_init' else getattr(ParentChannel, '__init__' if n == 'init' else n) if n in ('init', 'read', 'send') else globals().get(n)
        if got is not function or got.__code__ is not code: raise Held('implementation-drift')


def exchange(channel):
    """One-use factual dialogue. Only parent aggregate can assert producer provenance."""
    need(type(channel) is ParentChannel and channel not in _SPENT, 'original-live-channel')
    original = _CHANNEL_ORIGINALS.get(channel)
    need(original is not None and os.getpid() == original[3] and threading.get_ident() == original[4],
         'same-original-process')
    _SPENT.add(channel); channel.used = True  # Error/lost reply spends original registry identity.
    empty = {k: () for k in VECTORS}
    close_originals(channel, original, empty)
    wire=PROTOCOL if channel.launch is None else WIRE2;birth_sha=None
    if channel.launch is not None:
        source=dict(channel.source);source['hashes']=tuple((p,read_file(p,v)) for p,v in source['files9'])
        birth=encode(dict(protocol=wire,type='receiver-birth',nonce=channel.launch.nonce,operation_id=channel.launch.operation,sequence=0,
                          source_map_sha256=hashlib.sha256(encode(dict(source['hashes']))).hexdigest(),receiver_only_nodes5=channel.birth,
                          source_originals=source,source_originals_sha256=hashlib.sha256(encode(source)).hexdigest(),rights=dict(RIGHTS)))
        birth_sha=hashlib.sha256(birth).hexdigest();close_originals(channel,original,empty);channel.send(birth)
    bootstrap_raw = channel.read(); boot = decode(bootstrap_raw)
    need(set(boot) == ({'protocol', 'type', 'nonce', 'operation_id', 'owner', 'roles',
                      'local_originals', 'source_map'}|({'receiver_birth_sha256'} if channel.launch is not None else set())) and boot['protocol'] == wire
         and boot['type'] == 'bootstrap', 'bootstrap-schema')
    nonce = digest(boot['nonce']); operation = digest(boot['operation_id']); selected = owner(boot['owner'])
    if channel.launch is not None:
        need(nonce==channel.launch.nonce and operation==channel.launch.operation and boot['receiver_birth_sha256']==birth_sha, 'birth-original-request')
    roles = boot['roles']; need(type(roles) is dict and set(roles) == {'archive', 'catalog', 'authority',
                                            'marker', 'catalog_native_target'}, 'role-schema')
    for role in ('archive', 'catalog', 'authority', 'marker'): path(roles[role])
    path(roles['catalog_native_target'], source=True)
    local = frame(boot['local_originals'], local=True)
    known = dict(local['files9']); wanted = dict(local['hashes'])
    need(all(roles[n] in known and roles[n] in wanted for n in ('archive', 'catalog', 'authority', 'marker')), 'role-originals')
    need(all(str(p) in dict(local['nodes5']) for name in known for p in Path(name).parents), 'complete-original-ancestors')
    need(all(roles[role] + suffix in local['absent'] for role in ('catalog', 'authority')
             for suffix in ('-journal', '-wal', '-shm')), 'complete-SQL-companions')
    if channel.launch is not None:
        for p,v in channel.birth:need(dict(local['nodes5']).get(p)==v, 'bootstrap-original-receiver-node')
    raw_close(local)
    sources = boot['source_map']; own = str(Path(__file__).absolute())
    need(type(sources) is dict and set(sources) == {own}, 'exact-own-source-map')
    source_files = tuple((str(path(p, source=True)), nine(os.lstat(p))) for p in sources)
    source_nodes = {}
    for p, _ in source_files:
        need(Path(p).parent == Path(own).parent and Path(p).suffix == '.py', 'installed-source-scope')
        for n in Path(p).parents:
            v = five(os.lstat(n)); need(v[2] & 0o170000 == 0o040000, 'source-parent')
            need(str(n) not in source_nodes or source_nodes[str(n)] == v, 'source-node-conflict'); source_nodes[str(n)] = v
    need(dict(source_files)[own] == dict(channel.source['files9'])[own], 'source-not-recaptured')
    source_frame = {'files9': source_files, 'nodes5': tuple(source_nodes.items()),
                    'namespaces': (), 'claims': (), 'absent': (), 'hashes': ()}
    for p, v in source_files: need(read_file(p, v) == digest(sources[p]), 'installed-source-bytes')
    challenge = secrets.token_hex(32)
    local_digest = hashlib.sha256(encode(local)).hexdigest()
    hello_value=dict(protocol=wire, type='hello', nonce=nonce, operation_id=operation,
                        sequence=1, challenge=challenge, source_map_sha256=hashlib.sha256(encode(sources)).hexdigest(),
                        local_originals_sha256=local_digest)
    if birth_sha is not None:hello_value['receiver_birth_sha256']=birth_sha
    hello=encode(hello_value)
    raw_close(source_frame); close_originals(channel, original, local); channel.send(hello,local=local)
    request_raw = channel.read(); request = decode(request_raw)
    need(set(request) == ({'protocol', 'type', 'nonce', 'operation_id', 'sequence', 'challenge', 'owner',
                         'outcome', 'producer_ref', 'producer_history_ref', 'producer_originals',
                         'host_projection', 'consumer_projection', 'rights'}|({'receiver_birth_sha256'} if channel.launch is not None else set())), 'observe-schema')
    need(request['protocol'] == wire and request['type'] == 'observe' and request['nonce'] == nonce
         and request['operation_id'] == operation and type(request['sequence']) is int and request['sequence'] == 1
         and request['challenge'] == challenge and request['owner'] == selected and request['rights'] == RIGHTS
         and all(v is False for v in request['rights'].values())
         and request['outcome'] in ('observed-forward', 'observed-rollback'), 'observe-binding')
    if birth_sha is not None:need(request['receiver_birth_sha256']==birth_sha, 'observe-original-birth')
    need(frame(request['consumer_projection'], local=True) == local, 'original-consumer-projection')
    foreign = {k: frame(request[k], local=False) for k in ('producer_originals', 'host_projection')}
    for key in ('producer_ref', 'producer_history_ref'):
        ref = request[key]; need(type(ref) is dict and set(ref) == {'path', 'signature9', 'sha256'}, 'foreign-reference')
        path(ref['path'], source=True); vector(ref['signature9'], 9); digest(ref['sha256'])
        foreign[key] = ref
    hashes = {}
    for p, expected in local['hashes']:
        hashes[p] = read_file(p, known[p]); need(hashes[p] == expected, 'original-selected-bytes')
    catalog = sql_snapshot(roles['catalog'], known[roles['catalog']])
    selected_fact = catalog_owner(catalog, selected, roles['catalog_native_target'])
    proof = dict(originals_sha256=local_digest, archive_sha256=hashes[roles['archive']],
                 catalog_sha256=hashes[roles['catalog']], catalog_logical_sha256=hashlib.sha256(encode(catalog)).hexdigest(),
                 authority_sha256=hashes[roles['authority']], marker_sha256=hashes[roles['marker']], catalog_owner=selected_fact)
    request_sha = hashlib.sha256(request_raw).hexdigest()
    result_value=dict(protocol=wire, type='observed', nonce=nonce, operation_id=operation, sequence=1,
                         challenge=challenge, request_sha256=request_sha, owner=selected,
                         outcome=request['outcome'], local_proof=proof, foreign_unrestated=foreign, rights={'publication': False, 'ordinary_import': False, 'index': False, 'cleanup': False, 'replay': False, 'resume': False})
    if birth_sha is not None:result_value['receiver_birth_sha256']=birth_sha
    result=encode(result_value)
    result_sha = hashlib.sha256(result).hexdigest()
    raw_close(source_frame); close_originals(channel, original, local); channel.send(result,local=local)
    release = decode(channel.read())
    need(set(release) == ({'protocol', 'type', 'nonce', 'operation_id', 'sequence', 'challenge',
                         'request_sha256', 'result_sha256', 'rights'}|({'receiver_birth_sha256'} if channel.launch is not None else set())) and release['protocol'] == wire
         and release['type'] == 'release' and release['nonce'] == nonce and release['operation_id'] == operation
         and type(release['sequence']) is int and release['sequence'] == 2 and release['challenge'] == challenge
         and release['request_sha256'] == request_sha and release['result_sha256'] == result_sha
         and release['rights'] == RIGHTS and all(v is False for v in release['rights'].values()), 'release-binding')
    if birth_sha is not None:need(release['receiver_birth_sha256']==birth_sha, 'release-original-birth')
    final = encode(dict(release, type='released'))
    raw_close(source_frame); close_originals(channel, original, local); channel.send(final,local=local)
    return None  # No authority-bearing handle escapes this original call.


def main():
    if len(sys.argv)==1:exchange(ParentChannel());return
    launch=reviewed_launch(tuple(sys.argv));exchange(ParentChannel(launch=launch))


_PINNED_IMPLEMENTATIONS = _implementation()


if __name__ == '__main__':
    main()
