"""Process-local read exclusion, always nested inside the shared raw Writer."""
import threading

LOCK = threading.RLock()
