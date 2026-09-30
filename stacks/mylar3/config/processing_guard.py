"""Own the native processing lock for the complete lifetime of one run."""
from functools import wraps
from contextlib import ExitStack
import threading

_RUN = threading.RLock()


def run(function):
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        import mylar
        from mylar import pack_intake, native_writers
        from mylar.media_writer import Busy
        try:
            # Always acquire the shared writer first: a guarded rescan can call
            # processing synchronously. Reversing these locks deadlocks callers.
            with ExitStack() as admission:
                try:
                    admission.enter_context(native_writers.operation())
                except Busy:
                    # No processing has begun. Preserve the exact job for the
                    # serial worker rather than consuming it as a finished run.
                    mylar.PP_QUEUE.put({
                        'nzb_name': self.nzb_name, 'nzb_folder': self.nzb_folder,
                        'issueid': self.issueid, 'comicid': self.comicid,
                        'failed': False, 'apicall': self.apicall, 'ddl': self.ddl,
                        'download_info': getattr(self, 'download_info', None),
                    })
                    from mylar import logger
                    logger.warn('Media writer busy; post-processing retained in queue for retry')
                    return None
                with _RUN:
                    mylar.APILOCK = True
                    try:
                        if pack_intake.capture(self):
                            return None
                        return function(self, *args, **kwargs)
                    finally:
                        mylar.APILOCK = False
        finally:
            # Admission failures must complete a synchronous caller's queue too,
            # without clearing APILOCK belonging to another active processor.
            queue = getattr(self, 'queue', None)
            if queue is not None and queue.empty():
                queue.put([{'mode': 'stop'}])
    return wrapped
