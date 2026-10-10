"""Fixed Ubuntu candidate primitive for private installed-auth prototype; deployment approval required."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import weakref

LIMIT = 65536
_TOOL = Path('/usr/bin/openssl')
_LOADER = Path('/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2')
# Fixed Ubuntu candidate set; not full loaded ELF/provider attestation.
_HOST_FILES = (_TOOL, _LOADER, *map(Path, (
    '/usr/lib/x86_64-linux-gnu/libssl.so.3',
    '/usr/lib/x86_64-linux-gnu/libcrypto.so.3',
    '/usr/lib/x86_64-linux-gnu/libc.so.6')))
_ENV = {'LC_ALL': 'C', 'OPENSSL_CONF': '/dev/null', 'OPENSSL_MODULES': '/nonexistent-comic-providers'}
_SEALS = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL

_SOURCE_FRAMES = weakref.WeakKeyDictionary()
_BUFFER_FRAMES = weakref.WeakKeyDictionary()

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

def canonical(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=False, allow_nan=False).encode('utf-8')
    need(0 < len(raw) <= LIMIT, 'canonical-bound')
    return raw

class _OriginalSources:
    """Integrity observation, not source-authenticated installation authority."""
    def __init__(self, paths, *, root_owned=False, absent=()):
        self.leaves = {}; self.nodes = {}; self.links = {}; self.absent = tuple(absent)
        for path in paths:
            path = Path(path)
            need(path.is_absolute(), 'source-absolute')
            # Preserve alias symlinks as original facts as well as canonical leaves.
            for part in reversed((path, *path.parents)):
                z = os.lstat(part)
                if stat.S_ISDIR(z.st_mode):
                    fact = five(z)
                    need(part not in self.nodes or self.nodes[part] == fact, "source-first-parent-conflict")
                    if root_owned:
                        need(z.st_uid == 0 and not z.st_mode & 0o022, "source-first-parent-root")
                    self.nodes.setdefault(part, fact)
                if stat.S_ISLNK(z.st_mode):
                    fact = (nine(z), os.readlink(part))
                    need(part not in self.links or self.links[part] == fact, 'source-alias-conflict')
                    self.links.setdefault(part, fact)
            resolved = path.resolve(strict=True)
            for parent in resolved.parents:
                z = os.lstat(parent); need(stat.S_ISDIR(z.st_mode), 'source-parent-type')
                fact = five(z)
                need(parent not in self.nodes or self.nodes[parent] == fact, 'source-parent-conflict')
                if root_owned:
                    need(z.st_uid == 0 and not z.st_mode & 0o022, 'source-parent-root')
                self.nodes.setdefault(parent, fact)
            z = os.lstat(resolved)
            need(stat.S_ISREG(z.st_mode) and z.st_nlink == 1, 'source-regular-single')
            if root_owned:
                need(z.st_uid == 0 and not z.st_mode & 0o022, 'source-root')
            v = nine(z)
            need(resolved not in self.leaves or self.leaves[resolved][0] == v, 'source-leaf-conflict')
            self.leaves.setdefault(resolved, (v, None))
        for path in self.absent:
            need(not os.path.lexists(path), 'preload-original-absent')
            for parent in Path(path).parents:
                z = os.lstat(parent); fact = five(z)
                need(stat.S_ISDIR(z.st_mode), 'absent-parent-type')
                if root_owned:
                    need(z.st_uid == 0 and not z.st_mode & 0o022, 'absent-parent-root')
                need(parent not in self.nodes or self.nodes[parent] == fact, 'absent-parent-conflict')
                self.nodes.setdefault(parent, fact)
        # Immutable pre-hash facts cannot be replaced by a read callback.
        leaves_before = tuple((p, v) for p, (v, _) in self.leaves.items())
        nodes_before = tuple(self.nodes.items()); links_before = tuple(self.links.items())
        absent_before = self.absent; hashed = {}
        for path, v in leaves_before:
            hashed[path] = (v, self._hash(path, v))
        need(leaves_before == tuple((p,v) for p,(v,_) in self.leaves.items()) and
             nodes_before == tuple(self.nodes.items()) and links_before == tuple(self.links.items()) and
             absent_before == self.absent, 'source-capture-frame-replaced')
        self.leaves = hashed
        _SOURCE_FRAMES[self] = (tuple(self.leaves.items()), nodes_before, links_before, absent_before)
        self.close()

    @staticmethod
    def _hash(path, v):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            need(nine(os.fstat(fd)) == v, 'source-original-FD')
            h = hashlib.sha256(); size = 0
            while block := os.read(fd, 1024**2):
                size += len(block); need(size <= 64 * 1024**2, 'source-hash-bound'); h.update(block)
            need(nine(os.fstat(fd)) == v and size == v[2], 'source-final-FD')
            return h.hexdigest()
        finally:
            os.close(fd)

    def close(self):
        frame = _SOURCE_FRAMES.get(self)
        need(frame is not None and frame == (tuple(self.leaves.items()), tuple(self.nodes.items()), tuple(self.links.items()), self.absent), "source-original-frame")
        for p, fact in self.links.items():
            need((nine(os.lstat(p)), os.readlink(p)) == fact, 'source-alias-changed')
        for p, fact in self.nodes.items():
            need(five(os.lstat(p)) == fact, 'source-parent-changed')
        for p, (v, h) in self.leaves.items():
            need(nine(os.lstat(p)) == v, 'source-leaf-changed')
            if h is not None:
                need(self._hash(p, v) == h, 'source-hash-changed')
        for p in self.absent:
            need(not os.path.lexists(p), 'preload-appeared')
        # A later hash callback cannot mutate an earlier alias, node or leaf.
        for p, fact in self.links.items():
            need((nine(os.lstat(p)), os.readlink(p)) == fact, "source-final-alias")
        for p, fact in self.nodes.items():
            need(five(os.lstat(p)) == fact, 'source-final-parent')
        for p, (v, _) in self.leaves.items():
            need(nine(os.lstat(p)) == v, 'source-final-leaf')

        need(_SOURCE_FRAMES.get(self) is frame and frame == (tuple(self.leaves.items()), tuple(self.nodes.items()), tuple(self.links.items()), self.absent), "source-final-frame")

    def report(self):
        self.close()
        return {'files': {str(p): {'signature9': list(v), 'sha256': h}
                          for p, (v, h) in self.leaves.items()},
                'aliases': {str(p): {'signature9': list(v), 'target': t}
                            for p, (v, t) in self.links.items()},
                'nodes': {str(p): list(v) for p, v in self.nodes.items()},
                'absent': list(map(str, self.absent))}

class _Memfd:
    def __init__(self, raw):
        need(type(raw) is bytes and 0 < len(raw) <= LIMIT, 'memfd-bound')
        self.fd = os.memfd_create('comic-test-buffer', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
        try:
            offset = 0
            while offset < len(raw):
                n = os.write(self.fd, raw[offset:]); need(n > 0, 'memfd-write'); offset += n
            os.lseek(self.fd, 0, os.SEEK_SET)
            fcntl.fcntl(self.fd, fcntl.F_ADD_SEALS, _SEALS)
            self.fact = nine(os.fstat(self.fd)); self.raw = raw
            _BUFFER_FRAMES[self] = (self.fd, self.fact, raw)
            self.close_original()
        except BaseException:
            os.close(self.fd); raise
    def close_original(self):
        need(_BUFFER_FRAMES.get(self) == (self.fd, self.fact, self.raw), "memfd-original-frame")
        need(nine(os.fstat(self.fd)) == self.fact and
             fcntl.fcntl(self.fd, fcntl.F_GET_SEALS) == _SEALS, 'memfd-original')
        need(os.pread(self.fd, len(self.raw)+1, 0) == self.raw, 'memfd-readback')
    @property
    def path(self):
        self.close_original(); return '/proc/self/fd/' + str(self.fd)
    def __enter__(self): return self
    def __exit__(self, *args):
        try: self.close_original()
        finally: os.close(self.fd)

class _TargetExperiment:
    """Fixed tool/environment. All signing use is disposable test fixture only."""
    def __init__(self):
        self.code = _OriginalSources([Path(__file__).resolve()])
        self.null_fact = nine(os.lstat('/dev/null'))
        need(stat.S_ISCHR(self.null_fact[5]) and self.null_fact[6] == 0 and
             os.lstat('/dev/null').st_rdev == os.makedev(1,3), 'fixed-null-config')
        self.null_nodes = tuple((p,five(os.lstat(p))) for p in Path('/dev/null').parents)
        self.sources = _OriginalSources(_HOST_FILES, root_owned=True,
                                        absent=(Path('/etc/ld.so.preload'),))
    def _execute(self, arguments, buffers=(), key_fd=None):
        source_original = self.sources; code_original = self.code
        original_frames = ((source_original, _SOURCE_FRAMES[source_original]), (code_original, _SOURCE_FRAMES[code_original]))
        source_table = _SOURCE_FRAMES
        null_original = self.null_fact; null_nodes_original = self.null_nodes
        source_original.close(); code_original.close()
        need(nine(os.lstat('/dev/null')) == null_original, 'null-original')
        for p, v in null_nodes_original: need(five(os.lstat(p)) == v, 'null-parent-original')
        originals = [(b, b.fact) for b in buffers]
        for b, _ in originals: b.close_original()
        key_fact = nine(os.fstat(key_fd)) if key_fd is not None else None
        loader = None; tool = None
        try:
            loader = os.open(_LOADER, os.O_RDONLY | os.O_NOFOLLOW)
            tool = os.open(_TOOL, os.O_RDONLY | os.O_NOFOLLOW)
            need(nine(os.fstat(loader)) == self.sources.leaves[_LOADER.resolve()][0], 'loader-original-FD')
            need(nine(os.fstat(tool)) == self.sources.leaves[_TOOL.resolve()][0], 'tool-original-FD')
            fds = (loader, tool, *(b.fd for b in buffers), *(() if key_fd is None else (key_fd,)))
            cmd = ['/proc/self/fd/' + str(loader), '--inhibit-cache', '--glibc-hwcaps-mask', '',
                   '--library-path', '/usr/lib/x86_64-linux-gnu', '/proc/self/fd/' + str(tool), *arguments]
            result = subprocess.run(cmd, env=dict(_ENV), pass_fds=fds, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            need(len(result.stdout) <= LIMIT and len(result.stderr) <= LIMIT, 'tool-output-bound')
            return result
        finally:
            if loader is not None: os.close(loader)
            if tool is not None: os.close(tool)
            for b, fact in originals:
                need(b.fact == fact, 'buffer-original-fact'); b.close_original()
            if key_fd is not None:
                need(nine(os.fstat(key_fd)) == key_fact, 'key-original-FD')
            source_original.close(); code_original.close()
            need(self.code is code_original and self.null_fact == null_original and self.null_nodes == null_nodes_original, 'runtime-original-controls')
            need(nine(os.lstat('/dev/null')) == null_original, 'null-final')
            for p, v in null_nodes_original: need(five(os.lstat(p)) == v, 'null-parent-final')
            need(self.sources is source_original, "runtime-original-sources")
            # Last declared helper has completed. Close captured originals inline;
            # no need/serialization/hash/close helper is called after these loops.
            if _SOURCE_FRAMES is not source_table: raise Held('final-original-source-table')
            for observed, frame in original_frames:
                if _SOURCE_FRAMES.get(observed) is not frame: raise Held('final-original-source-frame')
                leaves, nodes, aliases, absent = frame
                if (tuple(observed.leaves.items()), tuple(observed.nodes.items()), tuple(observed.links.items()), observed.absent) != frame:
                    raise Held('final-original-source-logical')
                for path, (v, target) in aliases:
                    z = os.lstat(path)
                    if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink) != v or os.readlink(path) != target:
                        raise Held('final-original-source-alias')
                for path, v in nodes:
                    z = os.lstat(path)
                    if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid) != v: raise Held('final-original-source-node')
                for path, (v, digest) in leaves:
                    z = os.lstat(path)
                    if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink) != v:
                        raise Held('final-original-source-leaf')
                for path in absent:
                    try: os.lstat(path)
                    except FileNotFoundError: continue
                    raise Held('final-original-source-absence')
            z = os.lstat('/dev/null')
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink) != null_original:
                raise Held('final-original-null')
            for path, v in null_nodes_original:
                z = os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid) != v: raise Held('final-original-null-node')
            if self.sources is not source_original or self.code is not code_original or self.null_fact != null_original or self.null_nodes != null_nodes_original:
                raise Held('final-runtime-original-controls')
    def _verify(self, message, signature, public_der):
        source_original = self.sources; code_original = self.code
        original_frames = ((source_original, _SOURCE_FRAMES[source_original]), (code_original, _SOURCE_FRAMES[code_original]))
        source_table = _SOURCE_FRAMES; null_original = self.null_fact; null_nodes_original = self.null_nodes
        need(type(signature) is bytes and len(signature) == 64, 'signature-size')
        need(type(public_der) is bytes and len(public_der) == 44 and
             public_der[:12] == bytes.fromhex('302a300506032b6570032100'), 'fixed-ed25519-public-DER')
        with _Memfd(message) as m, _Memfd(signature) as s, _Memfd(public_der) as k:
            result = self._execute(['pkeyutl', '-verify', '-rawin', '-provider', 'default',
                '-propquery', 'provider=default', '-pubin', '-keyform', 'DER', '-inkey', k.path,
                '-in', m.path, '-sigfile', s.path], (m,s,k))
            need(result.returncode == 0, 'signature-verification')
        # Context cleanup and result validation are declared callbacks too.
        # Their side effects must close against this invocation's originals.
        source_original.close(); code_original.close()
        need(self.sources is source_original and self.code is code_original, 'verify-original-runtime')
        # Last declared helper has completed. Close captured originals inline;
        # no need/serialization/hash/close helper is called after these loops.
        if _SOURCE_FRAMES is not source_table: raise Held('final-original-source-table')
        for observed, frame in original_frames:
            if _SOURCE_FRAMES.get(observed) is not frame: raise Held('final-original-source-frame')
            leaves, nodes, aliases, absent = frame
            if (tuple(observed.leaves.items()), tuple(observed.nodes.items()), tuple(observed.links.items()), observed.absent) != frame:
                raise Held('final-original-source-logical')
            for path, (v, target) in aliases:
                z = os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink) != v or os.readlink(path) != target:
                    raise Held('final-original-source-alias')
            for path, v in nodes:
                z = os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid) != v: raise Held('final-original-source-node')
            for path, (v, digest) in leaves:
                z = os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink) != v:
                    raise Held('final-original-source-leaf')
            for path in absent:
                try: os.lstat(path)
                except FileNotFoundError: continue
                raise Held('final-original-source-absence')
        z = os.lstat('/dev/null')
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink) != null_original:
            raise Held('final-original-null')
        for path, v in null_nodes_original:
            z = os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid) != v: raise Held('final-original-null-node')
        if self.sources is not source_original or self.code is not code_original or self.null_fact != null_original or self.null_nodes != null_nodes_original:
            raise Held('final-runtime-original-controls')
        return True

# Intentionally no __main__, exported authority constructor or activation API.
