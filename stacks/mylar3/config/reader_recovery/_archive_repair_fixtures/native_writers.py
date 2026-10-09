"""Serialize native readers/writers and recover publication before admission."""
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
import threading
from .media_writer import Writer

_LOCAL = threading.local()
# Activated only by the focused startup adapter, never by a cached probe.
_PUBLICATION = False
_MODE_LOCK = threading.Lock()
_OPERATIONS = 0
_STARTUP_COMPLETE = False
PASSIVE_API = ('publicationControl','getHealth','getVersion','restart','shutdown')


def active():
    return bool(getattr(_LOCAL, 'depth', 0))


def owner():
    import mylar
    return Writer(Path(mylar.DATA_DIR)/'media-writer', create=False)


@contextmanager
def _mode():
    global _OPERATIONS
    with _MODE_LOCK:
        _OPERATIONS += 1
        publication = _PUBLICATION
    try:
        yield publication
    finally:
        with _MODE_LOCK:
            _OPERATIONS -= 1


@contextmanager
def operation(*, reconcile=False, startup=False):
    with _mode() as publication:
        writer = owner()
        with writer.hold(allow_pending=publication, allow_tagger_pending=True, allow_release_pending=True, timeout=180):
            outer = not getattr(_LOCAL, 'depth', 0)
            if publication:
                admission(writer,startup=startup)
            else:
                from . import tagger_native
            if not publication and outer and (reconcile or writer.fenced(tagger=True)):
                tagger_native.recover(writer)
            if not publication and outer and writer.fenced(release=True):
                from . import release_naming
                release_naming.recover(writer)
            _LOCAL.depth = getattr(_LOCAL, 'depth', 0) + 1
            previous_startup=getattr(_LOCAL,'startup',False)
            _LOCAL.startup=startup
            retained_review=False
            try:
                if publication:
                    from .publication_native import Review
                    try:yield writer
                    except Review:
                        retained_review=True
                        raise
                else:yield writer
            finally:
                _LOCAL.depth -= 1
                _LOCAL.startup=previous_startup
                if publication:
                    from .publication_guard import Unavailable
                    try:admission(writer,startup=startup)
                    except Unavailable:
                        # Preserve the terminal refusal while held state still
                        # denies the next operation. This grants no admission.
                        if not retained_review:raise
                elif outer and writer.fenced(tagger=True):
                    tagger_native.recover(writer)


def initialize():
    if _PUBLICATION:
        from .publication_guard import Unavailable
        raise Unavailable('Legacy initialization is unavailable after publication activation')
    import mylar
    Writer(Path(mylar.DATA_DIR)/'media-writer', create=True)
    with operation(reconcile=True):
        pass


def guard(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with operation():
            return function(*args, **kwargs)
    return wrapped


def publication_mode():
    return _PUBLICATION


def authority_probe():
    """Passive existing-only authority; never cached authorization or recovery."""
    import mylar
    from .publication_guard import authority_status
    root=Path(mylar.DATA_DIR)
    return authority_status(root/'workflow.sqlite',root/'media-writer')


def initialize_publication():
    """Activate fail-closed admission without creating or replaying state."""
    global _PUBLICATION
    with _MODE_LOCK:
        if _OPERATIONS:
            from .publication_guard import Unavailable
            raise Unavailable('Publication activation must precede native operations')
        _PUBLICATION=True
    return authority_probe()


def startup_status():
    status=authority_probe()
    if status['state']=='ready' and not _STARTUP_COMPLETE:
        status=dict(status,state='held',reason='startup-restart-required')
    return status


def complete_startup():
    global _STARTUP_COMPLETE
    from .publication_guard import Unavailable
    if not _PUBLICATION or not active() or not getattr(_LOCAL,'startup',False):
        raise Unavailable('Native startup admission required before completion')
    _STARTUP_COMPLETE=True


def startup_catalog(writer):
    """Never infer a fresh native catalog from lost existing application data."""
    import mylar
    import os
    import sqlite3
    import stat
    import time
    from . import publication_guard as guard
    root=Path(mylar.DATA_DIR).absolute();path=root/'mylar.db'
    if not active() or not getattr(_LOCAL,'startup',False):
        raise guard.Unavailable('Native catalog check requires startup admission')
    if os.path.lexists(path):
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_nlink!=1:
            raise guard.Unavailable('Unsafe native catalog')
        if not 4096<=info.st_size<=256*1024*1024:
            raise guard.Unavailable('Invalid native catalog size')
        before=guard.signature(info)
        with guard.regular(path) as stream:
            if guard.signature(os.fstat(stream.fileno()))!=before:
                raise guard.Unavailable('Native catalog changed before startup check')
            header=stream.read(100)
        if len(header)!=100 or header[:16]!=b'SQLite format 3\0' or header[18:20]!=b'\x01\x01':
            raise guard.Unavailable('Invalid native rollback catalog header')
        if any(os.path.lexists(root/('mylar.db'+suffix)) for suffix in ('-journal','-wal','-shm')):
            raise guard.Unavailable('Native catalog journal requires explicit review')
        db=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)
        try:
            deadline=time.monotonic()+guard.TIMEOUT
            db.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
            if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:
                raise guard.Unavailable('Unreadable native catalog')
            for table in ('comics','issues','annuals'):
                if db.execute("SELECT type FROM sqlite_master WHERE name=?",(table,)).fetchall()!=[('table',)]:
                    raise guard.Unavailable('Missing native catalog base tables')
        finally:db.close()
        if (guard.signature(path.lstat())!=before
                or any(os.path.lexists(root/('mylar.db'+suffix)) for suffix in ('-journal','-wal','-shm'))):
            raise guard.Unavailable('Native catalog changed during startup check')
        return
    from . import publication_fresh as fresh
    from .publication_api import Controller
    fresh.native_absent(root)
    token=fresh.prepared_token(root)
    receipt=Controller(root,[]).receipt(token,writer)
    if receipt['action']!='bootstrap' or receipt['outcome']!='committed' or not receipt['accepted']:
        raise guard.Unavailable('Exact accepted fresh installation required')
    claim=guard.private_json(root/fresh.CLAIM)
    # Consume the one-time creation permission before native dbcheck can create
    # anything. An interruption retains a hold for review, never recreates data.
    fresh._replace(root,claim,dict(claim,phase='native-creation-started'))


def cleanup_admission(database):
    from .publication_guard import cleanup_admission as check
    return check(database)


def admission(writer, *, startup=False):
    """Validate full current authority under raw Writer before workflow LOCK."""
    import mylar
    from .publication_guard import media_snapshot, Unavailable, ordinary_purpose
    if not getattr(writer.local[1],'depth',0):
        raise Unavailable('Raw Writer required before publication admission')
    ordinary_purpose(writer)
    census,_=media_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json')
    import os
    if (os.path.lexists(writer.root/'tagger-publication-v1.json')
            or os.path.lexists(writer.root/'nested-derivative-v1.json')
            or os.path.lexists(writer.root/'tagger-recovery-v1.pending')
            or any(writer.fenced(**args) for args in ({},{'tagger':True},{'release':True}))):
        raise Unavailable('Explicit publication recovery is required')
    if not startup and not _STARTUP_COMPLETE:
        raise Unavailable('Native initialization requires restart after authority review')
    ordinary_purpose(writer)
    return census


def existing_store(root, *, cached=None):
    """Store factory never acquires Writer while its caller holds workflow LOCK."""
    from .workflow_store import Store
    if _PUBLICATION:
        import mylar
        from .publication_guard import Unavailable
        if not active() or Path(root).absolute() != Path(mylar.DATA_DIR).absolute():
            raise Unavailable('Outer native admission and native state root required before workflow Store')
    if cached is not None and not _PUBLICATION:
        return cached
    if cached is not None and cached.existing_only:
        if Path(cached.path).parent != Path(root).absolute():
            from .publication_guard import Unavailable
            raise Unavailable('Cached Store belongs to foreign state')
        return cached
    return Store(root,existing_only=_PUBLICATION)


@contextmanager
def queue_operation(mode):
    if mode == 'start':
        with operation() as writer:yield writer
    else:
        # Shutdown remains available while authority/media journals are held.
        yield None


def publication_http(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        if _PUBLICATION and startup_status()['state']!='ready':
            return '<p>Media processing is held. Complete authenticated publication review, then restart Mylar.</p>'
        if _PUBLICATION:
            from .publication_native import Review
            try:
                with operation():return function(*args,**kwargs)
            except Review:
                return '<p>Publication identity requires review. Source and catalog are retained.</p>'
        return function(*args,**kwargs)
    return wrapped


def publication_api_call(function):
    @wraps(function)
    def wrapped(self,*args,**kwargs):
        if _PUBLICATION and self.data == 'OK' and self.cmd not in PASSIVE_API:
            from .publication_native import Review
            try:
                with operation():return function(self,*args,**kwargs)
            except Review:
                self.data=self._failureResponse('Publication identity requires review; source and catalog retained')
                return self.data
        return function(self,*args,**kwargs)
    return wrapped
