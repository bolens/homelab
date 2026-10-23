"""One explicitly authorized trusted Root invocation of the UID1000 Creator.

This is NOT a privilege sandbox. Saved Root exists for this invocation only.
Creator, its filesystem work and all pipe waits run as real/effective UID/GID1000.
Only the source-owned PurposeEngine can spawn the fixed Root Docker client.
There is no command relay, socket, caller prefix, cleanup, resume or replay API.
Authenticate before invoking this entry: Creator's deadline starts afterwards.
"""
import argparse
from contextlib import contextmanager
import hashlib
import importlib
import json
import os
from pathlib import Path
import signal
import select
import time
import stat
import subprocess
import sys
import threading

HERE = Path(__file__).resolve().parent
DOCKER = ('/usr/bin/docker', '--host', 'unix:///run/docker.sock')


def require(value, code):
    if not value:
        raise ValueError(code)


def _child_signal_mask():
    # Popen inherits the temporarily blocked spawning-thread mask. The exact
    # Docker child must regain normal signal delivery before exec, not remain
    # immune to termination. No caller callback is accepted.
    signal.pthread_sigmask(signal.SIG_SETMASK, set())


def _identity_abort():
    # Dedicated invocation only: do not run diagnostics, handlers or caller code
    # with unverified credentials. Exit126 means held/unknown, never replay.
    os._exit(126)


class Identity:
    """Trusted single-threaded saved-ID lifetime, never a general user facility."""
    def __init__(self):
        require(os.getresuid() == (0, 0, 0) and os.getresgid() == (0, 0, 0), 'batch-original-root-required')
        require(threading.active_count() == 1, 'batch-single-thread-required')
        self.closed = False
        self._client = None

    def enter(self):
        os.setgroups([])
        os.setresgid(1000, 1000, 0)
        os.setresuid(1000, 1000, 0)
        self.check()

    def check(self):
        require(not self.closed and os.getresuid() == (1000, 1000, 0)
                and os.getresgid() == (1000, 1000, 0) and os.getgroups() == []
                and threading.active_count() == 1, 'batch-uid1000-lifetime')

    @contextmanager
    def _root_window(self):
        self.check()
        # No application signal handler may execute with elevated credentials.
        blocked = signal.valid_signals() - {signal.SIGKILL, signal.SIGSTOP}
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, blocked)
        try:
            os.seteuid(0)
            os.setegid(0)
            yield
        finally:
            try:
                try:
                    os.setegid(1000)
                finally:
                    os.seteuid(1000)
                self.check()
            except BaseException:
                _identity_abort()
            # A pending handler may run only after verified effective UID1000.
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)

    def spawn_docker(self, args, data):
        require(type(args) is list and all(type(x) is str for x in args)
                and (data is None or type(data) is bytes), 'batch-fixed-command-fields')
        require(self._client is None or self._client.poll() is not None, 'batch-previous-client-live')
        with self._root_window():
            # Set all child IDs explicitly: the client is genuinely Root, while
            # this Python process is UID1000 again before reading or waiting.
            self._client = subprocess.Popen([*DOCKER, *args],
                stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'},
                user=0, group=0, extra_groups=[], close_fds=True,
                preexec_fn=_child_signal_mask)
        return self._client

    def terminate_client(self, process):
        require(process is self._client and process is not None, 'batch-owned-client-required')
        with self._root_window():
            process.kill()

    def close(self):
        if self.closed:
            return
        primary = None
        try:
            if self._client is not None and self._client.poll() is None:
                self.terminate_client(self._client)
                self._client.wait(timeout=1)
        except BaseException as error:
            primary = error
        finally:
            # Keep every catchable signal blocked until authority is proven
            # irreversibly gone; no pending app handler may run at EUID0.
            try:
                previous = signal.pthread_sigmask(signal.SIG_BLOCK,
                    signal.valid_signals() - {signal.SIGKILL, signal.SIGSTOP})
                os.seteuid(0)
                os.setgroups([])
                os.setresgid(1000, 1000, 1000)
                os.setresuid(1000, 1000, 1000)
                require(os.getresuid() == (1000, 1000, 1000)
                        and os.getresgid() == (1000, 1000, 1000) and not os.getgroups(), 'batch-authority-not-dropped')
                self.closed = True
            except BaseException:
                _identity_abort()
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)
        if primary is not None:
            raise primary


def driver_type(c):
    """Bind authority to actual owning call/code objects, not request argv."""
    admitted = {getattr(c.PurposeEngine, name).__code__ for name in
                ('image', 'network_preflight', 'create_network', 'create', 'inspect', 'copy', 'start', 'enroll', 'run')}
    admitted.update((c.Creator.prepare.__code__, c.Creator.virgin_process.__code__))
    original_docker = c.Driver.docker.__code__
    original_call = c.PurposeEngine.call.__code__

    class BatchDriver(c.Driver):
        def __init__(self, identity):
            self.identity = identity
            self.owner = None

        def _kill_process(self, process):
            frame = sys._getframe(1)
            require(frame.f_code is original_docker and frame.f_globals is vars(c)
                    and frame.f_locals.get('self') is self and frame.f_locals.get('process') is process,
                    'batch-owning-termination-required')
            # Timeout may have exhausted owner.seconds(): terminating the exact
            # client must not depend on a fresh application-admission deadline.
            self.identity.terminate_client(process)

        def _spawn(self, args, data):
            frame = sys._getframe(1)
            call = frame.f_back
            origin = None if call is None else call.f_back
            owner = self.owner
            require(owner is not None and frame.f_code is original_docker
                    and frame.f_globals is vars(c) and frame.f_locals.get('self') is self
                    and frame.f_locals.get('args') is args and frame.f_locals.get('data') is data
                    and call is not None and call.f_code is original_call and call.f_globals is vars(c)
                    and call.f_locals.get('self') is owner.engine and owner.engine.owner is owner and owner.engine.driver is self
                    and call.f_locals.get('args') is args and call.f_locals.get('data') is data
                    and origin is not None and origin.f_code in admitted and origin.f_globals is vars(c)
                    and (origin.f_locals.get('self') is owner or origin.f_locals.get('self') is owner.engine), 'batch-owning-dispatch-required')
            # Same original source/config/geometry closure, before elevation.
            owner.check()
            self.identity.check()
            return self.identity.spawn_docker(args, data)

    return BatchDriver


def _nine(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns,
            value.st_ctime_ns, value.st_mode, value.st_uid, value.st_gid, value.st_nlink)


def _source_ancestors(path):
    require(path.is_absolute() and path.resolve(strict=True) == path, 'batch-source-canonical')
    nodes = []
    for parent in path.parents:
        value = parent.lstat()
        require(stat.S_ISDIR(value.st_mode), 'batch-source-ancestor-directory')
        nodes.append((str(parent), (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid)))
    return tuple(nodes)


def _close_source(path, fd, original, ancestors):
    require(_nine(os.fstat(fd)) == original == _nine(path.lstat())
            and _source_ancestors(path) == ancestors, 'batch-source-final-closure')


def run(ref, source_sha256, *, activate=False):
    require(activate is True and sys.flags.isolated and sys.dont_write_bytecode, 'batch-explicit-isolated-activation-required')
    path = Path(__file__)
    ancestors = _source_ancestors(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= 131072
            and before.st_uid == before.st_gid == 1000 and stat.S_IMODE(before.st_mode) in (0o600, 0o644),
            'batch-original-source')
    identity = Identity()
    fd = None
    original = _nine(before)
    primary = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        raw = os.read(fd, 131073)
        require(len(raw) == before.st_size and hashlib.sha256(raw).hexdigest() == source_sha256, 'batch-source-pin')
        identity.enter()
        sys.path.insert(0, str(HERE))
        c = importlib.import_module('genuine_bootstrap_creator')
        _close_source(path, fd, original, ancestors)
        driver = driver_type(c)(identity)
        owner = c.Creator(c.p.decode(c.p.read(ref)), driver=driver)
        driver.owner = owner
        return owner.execute()
    except BaseException as error:
        primary = error
        raise
    finally:
        failures = []
        if fd is not None:
            try:
                _close_source(path, fd, original, ancestors)
            except BaseException as error:
                failures.append(error)
        if fd is not None:
            try:
                os.close(fd)
            except BaseException as error:
                failures.append(error)
        try:
            identity.close()
        except BaseException as error:
            failures.append(error)
        if failures:
            if primary is None:
                raise failures[0]
            primary.batch_secondary_failure_classes = tuple(type(error).__name__ for error in failures)


def identity_self_check():
    """Fixed Root-only fork probe: no Docker, application facts or callable input."""
    require(os.getresuid() == (0, 0, 0) and os.getresgid() == (0, 0, 0), 'batch-original-root-required')
    original = (os.getresuid(), os.getresgid(), os.getgroups())
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        code = 1
        identity = None
        try:
            identity = Identity()
            identity.enter()
            during = (os.getresuid(), os.getresgid(), os.getgroups())
            with identity._root_window():
                elevated = (os.getresuid(), os.getresgid())
            identity.check()
            # Fixed self-test only, not a caller program or Docker operation.
            with identity._root_window():
                identity._client = subprocess.Popen(['/usr/bin/python3', '-I', '-B', '-c',
                    'import json,os,time;print(json.dumps([list(os.getresuid()),list(os.getresgid())]),flush=True);time.sleep(30)'],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}, user=0, group=0,
                    extra_groups=[], close_fds=True, preexec_fn=_child_signal_mask)
            probe = identity._client
            require(select.select([probe.stdout], [], [], 1)[0], 'batch-probe-client-no-reply')
            reply = json.loads(os.read(probe.stdout.fileno(), 256))
            require(reply == [[0, 0, 0], [0, 0, 0]], 'batch-probe-client-not-root')
            identity.terminate_client(probe)
            terminal = probe.wait(timeout=1) == -signal.SIGKILL
            probe.stdout.close()
            probe.stderr.close()
            identity.check()
            identity.close()
            try:
                os.seteuid(0)
            except PermissionError:
                irreversible = True
            else:
                irreversible = False
            result = dict(uid1000=during == ((1000, 1000, 0), (1000, 1000, 0), []),
                          window_root=elevated == ((1000, 0, 0), (1000, 0, 0)),
                          final_uid1000=os.getresuid() == os.getresgid() == (1000, 1000, 1000),
                          root_cannot_be_regained=irreversible, owned_root_client_terminal=terminal, docker_calls=0)
            require(all(result[k] for k in result if k != 'docker_calls'), 'batch-identity-probe-failed')
            os.write(write_fd, json.dumps(result, sort_keys=True).encode())
            code = 0
        except BaseException:
            pass
        finally:
            if identity is not None:
                try:
                    identity.close()
                except BaseException:
                    code = 1
                client = identity._client
                if client is not None:
                    for stream in (client.stdout, client.stderr):
                        if stream is not None:
                            stream.close()
            os.close(write_fd)
            os._exit(code)
    os.close(write_fd)
    try:
        deadline = time.monotonic() + 5
        raw = bytearray()
        status = None
        while status is None:
            require(time.monotonic() < deadline, 'batch-identity-probe-timeout')
            ready, _, _ = select.select([read_fd], [], [], min(0.1, max(0, deadline-time.monotonic())))
            if ready:
                block = os.read(read_fd, 4097-len(raw))
                raw.extend(block)
                require(len(raw) <= 4096, 'batch-identity-probe-bound')
            found, observed = os.waitpid(pid, os.WNOHANG)
            if found:
                status = observed
        # The child writes once before exiting; collect a final ready fragment.
        while select.select([read_fd], [], [], 0)[0]:
            block = os.read(read_fd, 4097-len(raw))
            if not block:
                break
            raw.extend(block)
            require(len(raw) <= 4096, 'batch-identity-probe-bound')
        require(os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0 and len(raw) <= 4096,
                'batch-identity-probe-held')
        require((os.getresuid(), os.getresgid(), os.getgroups()) == original, 'batch-parent-identity-changed')
        return json.loads(raw)
    finally:
        os.close(read_fd)
        if status is None:
            # Only this exact newly forked identity-test process, never Docker.
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(pid, 0)


def safe_failure(error, source_sha256):
    """Fixed class plus authenticated own code location; never messages/values."""
    kinds = (AssertionError, ValueError, TypeError, KeyError, RuntimeError,
             OSError, TimeoutError, PermissionError, FileNotFoundError,
             UnicodeError, SystemExit, KeyboardInterrupt, subprocess.TimeoutExpired)
    token = next((kind.__name__ for kind in kinds if type(error) is kind), 'unclassified-exception')
    creator = sys.modules.get('genuine_bootstrap_creator')
    if creator is not None and type(error) is creator.p.Held:
        token = 'Held'
    result = dict(exception_class=token, source_frame=None)
    try:
        path = Path(__file__)
        ancestors = _source_ancestors(path)
        before = path.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and before.st_uid == before.st_gid == 1000 and before.st_size <= 131072
                and stat.S_IMODE(before.st_mode) in (0o600, 0o644), 'batch-diagnostic-source')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            raw = os.read(fd, 131073)
            require(len(raw) == before.st_size and hashlib.sha256(raw).hexdigest() == source_sha256
                    and _nine(before) == _nine(os.fstat(fd)) == _nine(path.lstat()), 'batch-diagnostic-pin')
            pending = [(compile(raw, str(path), 'exec'), 0)]
            codes = []
            while pending:
                code, depth = pending.pop()
                require(depth <= 16 and len(codes) < 512, 'batch-diagnostic-code-bound')
                codes.append(code)
                pending.extend((item, depth+1) for item in code.co_consts if isinstance(item, type(code)))
            trace = error.__traceback__
            count = 0
            selected = None
            while trace is not None and count < 128:
                frame = trace.tb_frame
                if frame.f_globals is globals() and frame.f_code.co_filename == str(path) and frame.f_code in codes:
                    selected = dict(function=frame.f_code.co_name, line=trace.tb_lineno, source_sha256=source_sha256)
                trace = trace.tb_next
                count += 1
            require(trace is None, 'batch-diagnostic-trace-bound')
            _close_source(path, fd, _nine(before), ancestors)
            result['source_frame'] = selected
        finally:
            os.close(fd)
    except BaseException:
        pass
    return result


class Arguments(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default error would repeat unknown argument values.
        raise ValueError('batch-arguments-refused')


def main(argv=None):
    parser = Arguments(description=__doc__)
    parser.add_argument('--activate', action='store_true')
    parser.add_argument('--identity-self-check', action='store_true')
    for name in ('input', 'sha256', 'source-sha256'):
        parser.add_argument('--' + name)
    args = None
    try:
        args = parser.parse_args(argv)
        require(sys.flags.isolated and sys.dont_write_bytecode, 'batch-isolation-required')
        if args.identity_self_check:
            require(not args.activate and not any((args.input, args.sha256, args.source_sha256)), 'batch-identity-only')
            print(json.dumps(identity_self_check(), sort_keys=True))
            return 0
        require(args.activate and args.input and args.sha256 and args.source_sha256, 'batch-explicit-activation-required')
        signature = os.lstat(args.input)
        fields = (signature.st_dev, signature.st_ino, signature.st_size, signature.st_mtime_ns,
                  signature.st_ctime_ns, signature.st_mode, signature.st_uid, signature.st_gid, signature.st_nlink)
        run(dict(path=args.input, sha256=args.sha256, signature9=list(fields)), args.source_sha256, activate=True)
        print('disposable-batch-produced; factory-runtime-unproved')
        return 0
    except BaseException as error:
        report = safe_failure(error, None if args is None else args.source_sha256)
        print('disposable-batch-held; resources-retained; no-replay')
        print(json.dumps(report, sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
