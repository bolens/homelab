"""Install only exact disabled standalone source; no API or parent activation."""
import ast
import hashlib
import os
from pathlib import Path
import stat
import sys

SOURCES = {
    'publication_retained_standalone': ('publication_retained_standalone.py', 'b2c796b10ae6ad08e0c7e7e3cac0277b59af1833b20424b7750038533f5741d7'),
    'comic_retained_standalone_action': ('reader_recovery/comic_retained_standalone_action.py', '3da7fb0fc4c72ac20b321e405a5567db8d173bf6e27ab25994b89aaf1df6b680'),
}
ROOT = Path(__file__).resolve().parent


def full(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid,
            s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def node(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid)


def main(directory):
    target = Path(directory).absolute()
    files = {}; nodes = {}; destinations = {}; payloads = {}
    # Capture every original leaf and ancestor before the first source read/AST.
    for name, (relative, _) in SOURCES.items():
        source = ROOT / relative; destination = target / (name + '.py')
        files[source] = full(source.lstat())
        if not stat.S_ISREG(files[source][2]) or files[source][5] != 1:
            raise ValueError('Standalone source must be single-link regular')
        for ancestor in (source.parent, *source.parent.parents, target, *target.parents):
            fact = node(ancestor.lstat())
            if not stat.S_ISDIR(fact[2]) or (ancestor in nodes and nodes[ancestor] != fact):
                raise ValueError('Standalone source ancestor conflict')
            nodes[ancestor] = fact
        destinations[destination] = full(destination.lstat()) if os.path.lexists(destination) else None
    for name, (relative, digest) in SOURCES.items():
        source = ROOT / relative
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            if full(os.fstat(fd)) != files[source]: raise ValueError('Standalone source FD changed')
            chunks = []
            while True:
                chunk = os.read(fd, 65536)
                if not chunk: break
                chunks.append(chunk)
            data = b''.join(chunks)
            if full(os.fstat(fd)) != files[source]: raise ValueError('Standalone source read changed')
        finally:
            os.close(fd)
        if hashlib.sha256(data).hexdigest() != digest: raise ValueError('Standalone source pin changed')
        tree = ast.parse(data)
        enabled = [x for x in tree.body if isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ENABLED' for t in x.targets)]
        if len(enabled) != 1 or not isinstance(enabled[0].value, ast.Constant) or enabled[0].value.value is not False:
            raise ValueError('Standalone default must remain disabled')
        payloads[target / (name + '.py')] = data
    # All parse/read callbacks precede closure of the original source+destination facts.
    for path, original in files.items():
        if full(path.lstat()) != original: raise ValueError('Standalone original source changed')
    for path, original in destinations.items():
        current = full(path.lstat()) if os.path.lexists(path) else None
        if current != original: raise ValueError('Standalone original destination changed')
        if original is not None:
            if not stat.S_ISREG(original[2]) or original[5] != 1 or path.read_bytes() != payloads[path]:
                raise ValueError('Unknown standalone installed predecessor')
    for path, original in nodes.items():
        if node(path.lstat()) != original: raise ValueError('Standalone original ancestor changed')
    for path, data in payloads.items():
        if destinations[path] is not None: continue
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        try:
            birth = full(os.fstat(fd))
            if not stat.S_ISREG(birth[2]) or stat.S_IMODE(birth[2]) != 0o644 or birth[5] != 1:
                raise ValueError('Standalone created output metadata')
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                if written <= 0: raise ValueError('Standalone short write')
                view = view[written:]
            os.fsync(fd)
            result = full(os.fstat(fd))
            if result[:6] != birth[:6] or result[6] != len(data) or full(path.lstat()) != result:
                raise ValueError('Standalone created output changed')
            destinations[path] = result
        finally:
            os.close(fd)
    # Encoding/readback/FD callbacks all precede the final original physical closure.
    for path, data in payloads.items():
        if path.read_bytes() != data: raise ValueError('Standalone output bytes changed')
    for path, original in nodes.items():
        if node(path.lstat()) != original: raise ValueError('Standalone final ancestor changed')
    for path, original in files.items():
        s = os.lstat(path)
        if (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns) != original:
            raise ValueError('Standalone final source changed')
    for path, original in destinations.items():
        s = os.lstat(path)
        if (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns) != original:
            raise ValueError('Standalone final destination changed')


if __name__ == '__main__': main(sys.argv[1])
