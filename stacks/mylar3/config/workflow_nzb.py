"""Retain native NZB ownership across queue removal and downloader polling."""
from functools import wraps
import threading
import time
import uuid

from mylar import workflow
from mylar.workflow_store import LOCK, identifier

_RUN = uuid.uuid4().hex


def busy(issueid):
    import mylar
    iid = identifier(issueid)
    if not iid:
        return False
    with LOCK:
        for name in ('NZB_QUEUE', 'RETURN_THE_NZBQUEUE'):
            queue = getattr(mylar, name, None)
            if queue is not None:
                with queue.mutex:
                    if any(isinstance(item, dict) and identifier(item.get('issueid')) == iid for item in queue.queue):
                        return True
        active = workflow.store().get('native_nzb', iid, {})
        # A previous process or dead monitor cannot stay an invisible active poll.
        # Its durable dispatch reservation still requires explicit reconciliation.
        return (active.get('run') == _RUN and active.get('phase') == 'polling'
                and any(t.ident == active.get('thread') and t.is_alive() for t in threading.enumerate()))


def take(queue):
    """Lock queue removal and durable ownership together; callers already check size."""
    with LOCK:
        item = queue.get_nowait()
        iid = identifier(item.get('issueid')) if isinstance(item, dict) else ''
        if not iid:
            return item
        try:
            if not workflow.reservation(iid) and not workflow.dispatch_owner(iid):
                workflow.store().set('dispatch', iid, {'issueid': iid, 'phase': 'accepted',
                    'reason': 'Existing downloader job is being monitored'})
            workflow.store().set('native_nzb', iid, {'issueid': iid, 'phase': 'polling',
                'run': _RUN, 'thread': threading.get_ident(), 'updated_at': time.time()})
        except Exception:
            queue.put(item)
            raise
        return item


def review(issueid):
    """Client removal/errors are uncertain, never proof that another send is safe."""
    iid = identifier(issueid)
    if not iid:
        return
    with LOCK:
        held = workflow.reservation(iid)
        if held and held['phase'] == 'accepted':
            workflow.set_handoff(held, 'review', 'Downloader job needs review before replacement')
        dispatch = workflow.dispatch_owner(iid)
        if dispatch and dispatch['phase'] == 'accepted':
            workflow.store().set('dispatch', iid, dict(dispatch, phase='review',
                reason='Downloader job needs review before replacement'))


def complete(function):
    @wraps(function)
    def wrapped(queue, item, nzstat, *args, **kwargs):
        iid = identifier(item.get('issueid')) if isinstance(item, dict) else ''
        try:
            result = function(queue, item, nzstat, *args, **kwargs)
        except Exception:
            review(iid)
            raise
        else:
            status = nzstat.get('status') if isinstance(nzstat, dict) else None
            # True is handed to native success/verified-failure processing; False
            # and paused remain monitored. None/unknown/removal require review.
            if status is not True and status is not False and status not in ('queue_paused', 'double-pp'):
                review(iid)
            return result
        finally:
            if iid:
                with LOCK:
                    workflow.store().delete('native_nzb', iid)
    return wrapped
