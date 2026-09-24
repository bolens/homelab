"""Read-only, bounded observations of actual post-processing calls."""
from collections import deque
from functools import wraps
from itertools import islice
import re
import threading
import time

_LOCK = threading.RLock()
_ACTIVE = {}
_RECENT = deque(maxlen=50)
_STARTED = time.time()
_ERRORS = 0
_SEQUENCE = 0


def display_name(value):
    if not isinstance(value, str) or '://' in value or '?' in value:
        return 'Name unavailable'
    value = value.replace('\\', '/').rstrip('/').rsplit('/', 1)[-1]
    return re.sub(r'[\x00-\x1f\x7f]', '', value)[:160] or 'Name unavailable'


def identifier(value):
    value = str(value or '')
    return value if value.isdecimal() and len(value) <= 20 else ''


def item_info(item):
    name = item.get('nzb_name')
    manual = name in ('Manual Run', 'Manual+Run')
    return {'name': display_name(item.get('nzb_folder') if manual else name),
            'source': 'DDL' if item.get('ddl') else 'Manual scan' if manual else 'Download client',
            'issueid': identifier(item.get('issueid')), 'comicid': identifier(item.get('comicid'))}


def observer_error():
    global _ERRORS
    with _LOCK:
        _ERRORS += 1


def observe(function):
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        global _SEQUENCE
        token = None
        error = False
        try:
            value = item_info(vars(self))
            value.update(started_at=time.time(), started_clock=time.monotonic())
            with _LOCK:
                if len(_ACTIVE) < 16:
                    _SEQUENCE += 1
                    token = _SEQUENCE
                    _ACTIVE[token] = value
        except Exception:
            observer_error()
        try:
            return function(self, *args, **kwargs)
        except BaseException:
            error = True
            raise
        finally:
            try:
                if token is not None:
                    modes = {row.get('mode') for row in getattr(self, 'valreturn', []) if isinstance(row, dict)}
                    outcome = ('Processing raised an error; check logs' if error else
                               'Processing reported a failure' if 'fail' in modes else
                               'Handed off for another processing pass' if 'outside' in modes else
                               'Run finished; check confirmed imports below')
                    with _LOCK:
                        value = _ACTIVE.pop(token)
                        value.update(outcome=outcome, finished_at=time.time(),
                                     elapsed_seconds=max(0, int(time.monotonic() - value.pop('started_clock'))))
                        _RECENT.appendleft(value)
            except Exception:
                with _LOCK:
                    _ACTIVE.pop(token, None)
                observer_error()
    return wrapped


def snapshot():
    import mylar
    from mylar import db, archive_monitor
    now = time.time()
    queue = mylar.PP_QUEUE
    with queue.mutex:
        depth = len(queue.queue)
        waiting = [item_info(item) for item in islice(queue.queue, 100) if isinstance(item, dict)]
    with _LOCK:
        active = [dict(value, elapsed_seconds=max(0, int(time.monotonic() - value['started_clock'])))
                  for value in _ACTIVE.values()]
        for row in active:
            row.pop('started_clock', None)
        recent = list(_RECENT)
        errors = _ERRORS
    enabled = bool(mylar.CONFIG.POST_PROCESSING)
    alive = bool(mylar.PPPOOL and mylar.PPPOOL.is_alive())
    locked = bool(mylar.APILOCK)
    status = ('Disabled' if not enabled else 'Worker unavailable' if not alive else
              'Processing' if active else 'Processing lock held; activity details unavailable' if locked else
              'Queued' if depth else 'Idle')
    database = db.DBConnection()
    imports = database.select("""
        SELECT i.ComicName AS name, i.Issue_Number AS issue, i.ComicID AS comicid,
               MAX(s.DateAdded) AS imported_at
        FROM snatched s JOIN issues i ON s.IssueID=i.IssueID
        WHERE s.Status='Post-Processed' AND i.Status='Downloaded' AND COALESCE(i.Location,'')!=''
        GROUP BY i.IssueID
        ORDER BY imported_at DESC LIMIT 25
    """)
    confirmed = [{'name': display_name(row['name']) + ' #' + display_name(str(row['issue'])),
                  'comicid': identifier(row['comicid']), 'imported_at': str(row['imported_at'])[:32]}
                 for row in imports]
    return {'checked_at': now, 'observing_since': _STARTED, 'status': status,
            'enabled': enabled, 'worker_alive': alive, 'processing_lock': locked,
            'queue_depth': depth, 'waiting': waiting, 'waiting_truncated': depth > 100,
            'active': active, 'recent': recent, 'imports': confirmed,
            'observer_errors': errors, 'archives': archive_monitor.snapshot()}
