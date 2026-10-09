"""Existing installed-SDK read coordinator; no reader or retirement admission.

The caller supplies the actual configured Controller. No daemon initialization,
private native lifecycle flags, queues, Store creation, or network calls occur.
"""
from contextlib import contextmanager
import copy
import importlib
import hashlib
import json
import os
from pathlib import Path
import stat
import threading

class Held(ValueError):
    pass


def check(value, reason):
    if not value:
        raise Held(reason)


def sdk():
    api = importlib.import_module('mylar.publication_api')
    writers = importlib.import_module('mylar.media_writer')
    guard = importlib.import_module('mylar.publication_guard')
    for module in (api, writers, guard):
        path = Path(module.__file__).absolute()
        check(path.parent == Path('/app/mylar3/mylar') and path.resolve() == path,
              'installed-sdk-required')
    return api, writers, guard


def signature(path):
    s = os.lstat(path)
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns,
            s.st_mode, s.st_uid, s.st_gid, s.st_nlink)


def canonical(path):
    path = Path(path)
    check(path.is_absolute() and '..' not in path.parts and path.resolve() == path
          and not any(p.is_symlink() for p in (path, *path.parents)), 'canonical')
    return path


def projection(controller):
    return (str(controller.root), str(controller.database),
            str(controller.native_database), str(controller.writer_root),
            tuple(map(str, controller.roots)), str(controller.tool_root))


_KEY = object()

class NativeReadCoordinator:
    """Same-thread existing raw Writer lifetime, not a serialized capability."""
    __slots__ = ('_key', '_api', '_writers', '_guard', '_controller', '_writer',
                 '_projection', '_thread', '_local', '_identity', '_files',
                 '_ancestors', '_census', '_records', '_open', '_seal')

    def __init__(self, key, controller, writer, modules):
        check(key is _KEY, 'coordinator-factory-required')
        self._key = key
        self._api, self._writers, self._guard = modules
        check(type(controller) is self._api.Controller and type(writer) is self._writers.Writer,
              'exact-native-types')
        self._controller, self._writer = controller, writer
        self._projection = projection(controller)
        self._thread = threading.get_ident()
        self._local = writer.local
        self._open = True
        check(getattr(self._local[1], 'depth', 0) > 0, 'raw-writer-not-held')
        root = canonical(controller.root)
        check(controller.database == root/'workflow.sqlite'
              and controller.native_database == root/'mylar.db'
              and controller.writer_root == root/'media-writer'
              and writer.root == controller.writer_root
              and controller.tool_root == self._guard.TOOL_ROOT, 'configured-native-paths')
        check(type(controller.roots) in (list, tuple) and 1 <= len(controller.roots) <= 8,
              'configured-roots')
        roots = [canonical(p) for p in controller.roots]
        check(len(set(roots)) == len(roots), 'duplicate-roots')
        paths = [writer.root, writer.lock, controller.database,
                 controller.native_database, writer.root/'publication-v1.json', *roots]
        # Capture namespace before any SDK callback or database observation.
        self._ancestors = {}
        for path in paths:
            for p in canonical(path).parents:
                s = signature(p)
                value = s[0:2]+s[5:8]
                check(p not in self._ancestors or self._ancestors[p] == value,
                      'admission-ancestor-drift')
                self._ancestors[p] = value
        self._files = {p: signature(p) for p in paths}
        for p in (writer.lock, controller.database, controller.native_database,
                  writer.root/'publication-v1.json'):
            s = self._files[p]
            check(stat.S_ISREG(s[5]) and s[6] == os.geteuid()
                  and stat.S_IMODE(s[5]) in ((0o600, 0o644) if p == controller.native_database else (0o600,))
                  and s[8] == 1, 'private-native-control')
        self._identity = tuple(self._guard.writer_identity(writer))
        self._census, self._records = self._guard.media_snapshot(
            controller.database, writer.root/'publication-v1.json')
        self._seal = self._seal_value()
        self.close_passive()

    def _seal_value(self):
        value = dict(projection=self._projection, thread=self._thread,
                     identity=self._identity, census=self._census, records=self._records,
                     objects=[id(x) for x in (self._api,self._writers,self._guard,
                         self._controller,self._writer,self._local)],
                     files={str(p):v for p,v in self._files.items()},
                     ancestors={str(p):v for p,v in self._ancestors.items()})
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),
            ensure_ascii=False,allow_nan=False).encode()).hexdigest()

    @property
    def binding(self):
        self.close_passive()
        return dict(version=1, kind='existing-native-read-coordinator',
                    writer_identity=list(self._identity), census=copy.deepcopy(self._census),
                    mutation_authority=False, reader_admission=False,
                    retirement_authority=False, publication_acceptance=False)

    def close_passive(self):
        check(self._key is _KEY and self._open and threading.get_ident() == self._thread
              and self._seal_value() == self._seal,
              'coordinator-lifetime')
        w = self._writer
        check(type(w) is self._writers.Writer and type(self._controller) is self._api.Controller
              and w.root == self._controller.writer_root
              and w.lock == w.root/'writer-v1.lock'
              and w.pending == w.root/'normalizer-v1.pending'
              and w.tagger_pending == w.root/'tagger-v2.pending'
              and w.release_pending == w.root/'release-v1.pending'
              and w.local is self._local and getattr(self._local[1], 'depth', 0) > 0
              and projection(self._controller) == self._projection
              and tuple(w.root_identity)+tuple(w.lock_identity) == self._identity,
              'coordinator-identity')
        # Pure direct leaf/ancestor checks: no SDK, database or network callbacks.
        for db in (self._controller.database, self._controller.native_database):
            for suffix in ('-wal', '-shm', '-journal'):
                try: os.lstat(str(db)+suffix)
                except FileNotFoundError: pass
                else: raise Held('native-companion')
        for name in ('normalizer-v1.pending', 'tagger-v2.pending', 'release-v1.pending'):
            try: os.lstat(w.root/name)
            except FileNotFoundError: pass
            else: raise Held('native-fence')
        for p, expected in self._files.items():
            check(signature(p) == expected, 'native-control-drift')
        for p, expected in self._ancestors.items():
            s = signature(p)
            check(s[0:2]+s[5:8] == expected, 'native-ancestor-drift')

    def revalidate(self):
        self.close_passive()
        check(tuple(self._guard.writer_identity(self._writer)) == self._identity,
              'fresh-writer-identity')
        census, records = self._guard.media_snapshot(
            self._controller.database, self._writer.root/'publication-v1.json')
        check(self._guard.same_json(census, self._census)
              and self._guard.same_json(records, self._records), 'native-authority-drift')
        self.close_passive()
        return self.binding

    def native_pair(self):
        self.revalidate()
        return self._controller, self._writer


@contextmanager
def hold_existing(controller, writer):
    modules = sdk()
    check(type(controller) is modules[0].Controller and type(writer) is modules[1].Writer,
          'exact-native-types')
    # No pending privileges; no creation, replay, bootstrap or daemon mode changes.
    with writer.hold(timeout=0):
        coordinator = NativeReadCoordinator(_KEY, controller, writer, modules)
        try:
            yield coordinator
            coordinator.revalidate()
        finally:
            coordinator._open = False
