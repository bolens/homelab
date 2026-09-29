"""Isolated migration helper; not yet connected to the native tagger."""

from dataclasses import dataclass, field
import math
import os
import selectors
import signal
import subprocess
import time

VERSION_TIMEOUT = 10
TAG_TIMEOUT = 180
MAX_OUTPUT = 65536


@dataclass(frozen=True)
class ProcessResult:
    state: str
    returncode: int | None
    stdout: bytes = field(default=b'', repr=False)
    stderr: bytes = field(default=b'', repr=False)


def run(argv, *, cwd, timeout=TAG_TIMEOUT, max_output=MAX_OUTPUT, env=None):
    """Run without a shell. Never log argv or captured output, which may be private.

    The caller owns archive staging, validation and publication. Exit zero alone
    only means the child exited successfully, not that tagging succeeded.
    """
    if not isinstance(argv, (list, tuple)) or not argv or not all(isinstance(v, str) and '\0' not in v for v in argv):
        raise ValueError('Expected a nonempty argument sequence')
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('Expected a finite positive deadline')
    if not isinstance(max_output, int) or isinstance(max_output, bool) or not 0 < max_output <= MAX_OUTPUT:
        raise ValueError('Invalid output bound')
    started = time.monotonic()
    try:
        child = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 start_new_session=True, close_fds=True, env=env)
    except OSError:
        return ProcessResult('unavailable', None)
    output = [bytearray(), bytearray()]
    state = None
    try:
        with selectors.DefaultSelector() as selector:
            for index, stream in enumerate((child.stdout, child.stderr)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, index)
            while selector.get_map():
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    state = 'timed_out'
                    break
                for key, _ in selector.select(min(remaining, 0.1)):
                    block = os.read(key.fileobj.fileno(), 8192)
                    if not block:
                        selector.unregister(key.fileobj)
                        continue
                    room = max_output - sum(map(len, output))
                    output[key.data].extend(block[:room])
                    if len(block) > room:
                        state = 'output_limit'
                        break
                if state:
                    break
            if state is None:
                try:
                    child.wait(timeout=max(0, timeout - (time.monotonic() - started)))
                    state = 'ok' if child.returncode == 0 else 'failed'
                except subprocess.TimeoutExpired:
                    state = 'timed_out'
    finally:
        # Kill descendants too, including children holding inherited output pipes.
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()
        child.stdout.close()
        child.stderr.close()
    return ProcessResult(state, child.returncode, bytes(output[0]), bytes(output[1]))
