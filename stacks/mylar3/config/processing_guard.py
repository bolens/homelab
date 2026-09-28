"""Own the native processing lock for the complete lifetime of one run."""
from functools import wraps
import threading

_RUN = threading.RLock()


def run(function):
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        import mylar
        # Native callers include the queue, manual scans and API requests. The
        # ownership guard spans all of them, including early returns/errors.
        with _RUN:
            try:
                from mylar import pack_intake, native_writers
                with native_writers.owner().hold(timeout=180):
                    mylar.APILOCK = True
                    if pack_intake.capture(self):
                        return None
                    return function(self, *args, **kwargs)
            finally:
                mylar.APILOCK = False
                # The synchronous native caller waits for a result after join().
                # Exceptions before the native result must not strand it either.
                queue = getattr(self, 'queue', None)
                if queue is not None and queue.empty():
                    queue.put([{'mode': 'stop'}])
    return wrapped
