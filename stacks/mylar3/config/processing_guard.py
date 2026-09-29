"""Own the native processing lock for the complete lifetime of one run."""
from functools import wraps
import threading

_RUN = threading.RLock()


def run(function):
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        import mylar
        from mylar import pack_intake, native_writers
        try:
            # Always acquire the shared writer first: a guarded rescan can call
            # processing synchronously. Reversing these locks deadlocks callers.
            with native_writers.operation():
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
