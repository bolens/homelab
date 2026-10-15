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
SELF_ADMITTED_API = ('retainedDeliveryFinalize','retainedDeliveryStatus')


def self_admitted_api(handler):
    if getattr(handler,'cmd',None) not in SELF_ADMITTED_API:return False
    from . import publication_retained_api
    return publication_retained_api.owns(handler)


PASSIVE_API = ('publicationControl','getHealth','getVersion','restart','shutdown','ordinaryImportObservation')


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
def operation(*, reconcile=False, startup=False, ordinary=False):
    if type(ordinary) is not bool or ordinary and (reconcile or startup):
        raise ValueError('Invalid ordinary native operation purpose')
    with _mode() as publication:
        if ordinary and not publication:
            from .publication_guard import Unavailable
            raise Unavailable('Ordinary native operation requires publication mode')
        writer = owner()
        # A nested default hold cannot narrow an already inherited recovery purpose.
        if ordinary and getattr(writer.local[1], 'depth', 0) and any(
                getattr(writer.local[1], name, False) for name in
                ('allow_pending', 'allow_tagger_pending', 'allow_release_pending')):
            from .publication_guard import Unavailable
            raise Unavailable('Inherited recovery purpose cannot enter ordinary native operation')
        with writer.hold(allow_pending=False if ordinary else publication,
                         allow_tagger_pending=not ordinary, allow_release_pending=not ordinary, timeout=180):
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
    # Only admitted normal startup initializes the shared reservation inode.
    # Invalid/missing cache state stays capacity-held without blocking ordinary startup.
    try:
        from . import cache_admission
        cache_admission.initialize_shared_lock()
    except (OSError, ValueError, AttributeError):
        pass
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


def publication_hold_page(*, review=False):
    """Render without templates or catalog access while native startup is held."""
    import mylar
    theme = 'default' if getattr(getattr(mylar, 'CONFIG', None), 'INTERFACE', 'carbon') == 'default' else 'carbon'
    title = 'Publication identity requires review' if review else 'Media processing is held'
    explanation = ('Source and catalog are retained. Mylar stopped this request because publication identity needs review.'
                   if review else 'This page is unavailable while Mylar waits for authenticated publication review.')
    restart = ('Restart Mylar if the review requires it.' if review
               else 'After the review is complete, restart Mylar to finish startup.')
    page = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>''' + title + ''' | Mylar</title>
<style>
:root { color-scheme: dark; font-family: Arial, Helvetica, sans-serif; background: #252b33; color: #e8ecf1; }
* { box-sizing: border-box; }
body { margin: 0; min-width: 0; line-height: 1.6; }
header { padding: 18px max(24px, calc((100% - 880px)/2)); border-bottom: 1px solid #46515e; background: #303943; }
header strong { font-size: 20px; letter-spacing: .02em; }
header span { margin-left: 14px; color: #c0c9d3; font-size: 14px; }
main { width: min(880px, calc(100% - 48px)); margin: clamp(28px, 7vh, 80px) auto; }
.state { display: inline-block; color: #ffcd83; border: 1px solid #a98049; border-radius: 4px; padding: 3px 10px; font-size: 14px; }
h1 { font-size: clamp(26px, 4vw, 38px); line-height: 1.2; margin: 20px 0 14px; }
.lead { color: #cdd5df; max-width: 68ch; font-size: 17px; }
section { margin: 30px 0; padding: 24px; background: #2d3540; border: 1px solid #4b5868; border-left: 4px solid #e9b46c; border-radius: 6px; }
h2 { margin: 0 0 12px; font-size: 20px; }
ol { padding-left: 24px; margin: 0; }
li { padding-left: 6px; margin: 10px 0; }
.actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 24px; }
a { color: #9dd5fc; }
.actions a { display: inline-flex; align-items: center; justify-content: center; min-height: 44px; padding: 9px 16px; border: 1px solid #7599b5; border-radius: 4px; text-decoration: none; font-weight: bold; }
.actions a:first-child { background: #8ac9f5; border-color: #8ac9f5; color: #182634; }
a:hover { text-decoration: underline; }
a:focus-visible { outline: 3px solid #ffcd83; outline-offset: 4px; }
.note { color: #b9c4d0; font-size: 14px; }
@media (max-width: 480px) { header span { display: block; margin-left: 0; } main { width: calc(100% - 32px); } section { padding: 18px; } .actions a { width: 100%; } }
html:has(body[data-mylar-theme=default]) { color-scheme: light; background: #fafafa; color: #333; }
body[data-mylar-theme=default] header { background: #eee; border-color: #aaa; }
body[data-mylar-theme=default] header span, body[data-mylar-theme=default] .lead, body[data-mylar-theme=default] .note { color: #555; }
body[data-mylar-theme=default] section { background: #f2f2f2; border-color: #aaa; border-left-color: #b88736; }
body[data-mylar-theme=default] .state { color: #805c24; border-color: #b88736; }
body[data-mylar-theme=default] a { color: #3383bb; }
body[data-mylar-theme=default] .actions a { border-color: #3383bb; }
body[data-mylar-theme=default] .actions a:first-child { background: #3383bb; color: #fff; }
body[data-mylar-theme=default] a:focus-visible { outline-color: #3383bb; }
</style></head><body>
<header><strong>Mylar</strong><span>Publication review</span></header>
<main aria-labelledby="hold-title"><span class="state">Processing held</span>
<h1 id="hold-title">''' + title + '''</h1><p class="lead">''' + explanation + '''</p>
<section aria-labelledby="next-steps"><h2 id="next-steps">What to do next</h2>
<ol><li>Ask your administrator to complete authenticated publication review.</li>
<li>''' + restart + '''</li><li>Return to this page and try again.</li></ol>
<div class="actions"><a href="https://github.com/bolens/homelab/blob/main/stacks/mylar3/README.md#image-updates-and-rollback">Read the recovery guide</a><a href="">Try this page again</a></div>
</section><p class="note">Refreshing this page does not clear the hold. Keep recovery files and pending markers in place until review is complete.</p>
</main></body></html>'''
    return page.replace('<body>', '<body data-mylar-theme="' + theme + '">')


def publication_http(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        if _PUBLICATION:
            startup=startup_status()
            if startup['state']!='ready' and (startup['state'],startup.get('reason'))!=('held','writer-busy'):
                return publication_hold_page()
        if _PUBLICATION:
            from .publication_native import Review
            try:
                with operation():return function(*args,**kwargs)
            except Review:
                return publication_hold_page(review=True)
        return function(*args,**kwargs)
    return wrapped


def publication_api_call(function):
    @wraps(function)
    def wrapped(self,*args,**kwargs):
        if _PUBLICATION and self.data == 'OK' and self.cmd in SELF_ADMITTED_API:
            if not self_admitted_api(self):
                self.data=self._failureResponse('Exact retained owning API hook required')
                return self.data
            return function(self,*args,**kwargs)
        if _PUBLICATION and self.data == 'OK' and self.cmd not in PASSIVE_API:
            from .publication_native import Review
            try:
                with operation():return function(self,*args,**kwargs)
            except Review:
                self.data=self._failureResponse('Publication identity requires review; source and catalog retained')
                return self.data
        return function(self,*args,**kwargs)
    return wrapped
