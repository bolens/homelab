"""Default-off same-process retained member orchestration; factual local UI only."""
import os
import threading
import weakref

from maintenance import Maintenance
from media_writer import Writer
from publication_guard import scope, remote_unlocked
import retained_pack_handoff as handoff

_SESSIONS=weakref.WeakKeyDictionary()
_OWNERS=weakref.WeakKeyDictionary()


class RetainedPackSession:
    __slots__=('__weakref__',)
    def __init__(self,*args,**kwargs):raise ValueError('Owning retained session required')


def _core(session):
    if type(session) is not RetainedPackSession:raise ValueError('Owning retained session required')
    c=_SESSIONS.get(session)
    if c is None or (c['pid'],c['thread'])!=(os.getpid(),threading.get_ident()):raise ValueError('Original retained session lifetime required')
    return c


def initialize(maintenance):
    """Call before backup/proof lifetime; never from an active publication scope."""
    if handoff.ENABLED is not True or type(maintenance) is not Maintenance:raise ValueError('Retained operations disabled')
    if maintenance in _OWNERS:raise ValueError('Retained session already initialized')
    remote_unlocked(maintenance.worker);original=handoff.initialize(maintenance)
    session=object.__new__(RetainedPackSession)
    _SESSIONS[session]=dict(maintenance=maintenance,pid=os.getpid(),thread=threading.get_ident(),phase='review',action=None,selection=None,initial=original)
    _OWNERS[maintenance]=session
    _initial_originals(_SESSIONS[session])
    return session


def _initial_originals(c):
    path,stamp,nodes,binding=c['initial'];z=os.lstat(path)
    if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise ValueError('Original initialized journal required')
    for path,stamp in nodes:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise ValueError('Original initialized ancestor required')
    m=c['maintenance']
    if (m.state,m.worker,tuple(m.worker.roots),m.worker.config['writer_state'],m.settings.get('ddl_cache'),m.settings.get('mylar_ddl_cache'),m.worker.config['mylar'].get('url'),m.worker.config['mylar'].get('config_dir','/mylar'),tuple((row['native'],row['worker']) for row in m.worker.config['publication_roots']))!=binding:raise ValueError('Original initialized configuration required')


def existing(maintenance):
    if type(maintenance) is not Maintenance:raise ValueError('Original Maintenance required')
    session=_OWNERS.get(maintenance)
    if session is None or _core(session)['maintenance'] is not maintenance:raise ValueError('Original initialized session required')
    return session


def select(session,pack_id,member_id):
    c=_core(session)
    if c['selection'] is not None or c['action'] is not None:raise ValueError('One original retained selection only')
    selected=handoff.validate_selection(c['maintenance'],pack_id,member_id)
    c['selection']=selected;c['phase']='selected-review'


def execute(session):
    c=_core(session);m=c['maintenance']
    if c['phase']!='selected-review':raise ValueError('Original selected retained action required')
    c['phase']='preparing'
    try:
        _initial_originals(c)
        writer=Writer(m.worker.config['writer_state'],create=False)
        _initial_originals(c)
        with writer.hold(timeout=0),scope(m.worker,writer):
            _initial_originals(c)
            action=handoff.prepare(m,*c['selection'],initialized=c['initial'])
        c['action']=action;c['writer']=writer;c['phase']='dispatching'
        handoff.dispatch(action)
        with writer.hold(timeout=0),scope(m.worker,writer):handoff.consume(action)
        c['phase']='retained-observed'
    except Exception:
        c['phase']='uncertain-review'
        raise
    return view(session)


def reconcile(session):
    """One status query for the same live lost-return action; no finalize replay."""
    c=_core(session);m=c['maintenance'];action=c['action']
    if c['phase']!='uncertain-review' or action is None or handoff.live_state(action)!='dispatching':raise ValueError('Original lost-return action required')
    c['phase']='statusing'
    try:
        handoff.status_after_lost_reply(action)
        with c['writer'].hold(timeout=0),scope(m.worker,c['writer']):handoff.consume(action)
        c['phase']='retained-observed'
    except Exception:
        c['phase']='uncertain-review'
        raise
    return view(session)


def view(session):
    """Review progress, never imported/cleanup/index acceptance."""
    c=_core(session);phase=c['phase'];selected=c['selection']
    observed=phase=='retained-observed'
    return dict(version=1,phase=phase,pack_id=None if selected is None else selected[0],
                member_id=None if selected is None else selected[1],selected_members=int(selected is not None),
                retained_observed_members=int(observed),review_members=int(selected is not None and not observed),
                uncertain=phase in ('dispatching','statusing','uncertain-review','preparing'),
                imported_members=0,cleanup_grant=False,ordinary_import_grant=False,
                historical_import_ack=False,reader_index_acceptance=False,automatic_replay=False)
