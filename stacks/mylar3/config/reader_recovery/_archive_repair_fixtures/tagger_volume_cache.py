"""Process-local volume cache; absolute expiry survives private worker handoff."""
from collections import OrderedDict
import hashlib
import json
import math
import threading
import time

TTL = 300
MAX_ENTRIES = 64
MAX_BYTES = 16 * 1024


def context(base_url, api_key, verify, volumeid):
    # Never retain credentials in a cache key or diagnostic representation.
    return hashlib.sha256(json.dumps([base_url.rstrip('/'), api_key, verify,
                                     str(volumeid)], allow_nan=False).encode()).hexdigest()


def fresh(deadline, now):
    return (type(deadline) in (int, float) and math.isfinite(deadline)
            and now < deadline <= now + TTL)


class VolumeCache:
    def __init__(self, *, clock=time.monotonic):
        self.clock = clock
        self.entries = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            item = self.entries.get(key)
            if item is None:
                return None
            raw, deadline = item
            if not fresh(deadline, self.clock()):
                del self.entries[key]
                return None
            self.entries.move_to_end(key)
            return {'volume': json.loads(raw), 'expires': deadline}

    def put(self, key, volume, deadline):
        if not isinstance(volume, dict):
            return False
        try:
            raw = json.dumps(volume, ensure_ascii=True, allow_nan=False).encode()
        except (ValueError, TypeError, RecursionError, OverflowError):
            return False
        if len(raw) > MAX_BYTES:
            return False
        with self.lock:
            if not fresh(deadline, self.clock()):
                return False
            self.entries[key] = (raw, deadline)
            self.entries.move_to_end(key)
            while len(self.entries) > MAX_ENTRIES:
                self.entries.popitem(last=False)
        return True
