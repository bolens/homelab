"""Versioned local-filesystem writer lock shared with the comic normalizer.

Keep this module identical in both image contexts. The persistent pending marker
covers asynchronous Komga upgrades and process death, which flock alone cannot.
"""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import threading
import time

PROTOCOL = b'mylar-media-writer-v1\n'
_REGISTRY = {}
_REGISTRY_LOCK = threading.Lock()


class Busy(RuntimeError):
    pass


def sync(directory):
    fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def checked_file(path, flags=os.O_RDONLY):
    fd=os.open(path,flags|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size != len(PROTOCOL) or os.read(fd,len(PROTOCOL)+1) != PROTOCOL):
            raise ValueError('Invalid media writer protocol file')
        current=path.lstat()
        if (info.st_dev,info.st_ino) != (current.st_dev,current.st_ino):
            raise ValueError('Media writer protocol file changed')
        return fd
    except BaseException:
        os.close(fd);raise


class Writer:
    def __init__(self, root, *, create=False):
        self.root=Path(root).absolute()
        if self.root.anchor != '/' or '..' in self.root.parts or any(p.is_symlink() for p in (self.root,*self.root.parents)):
            raise ValueError('Invalid media writer state root')
        created=False
        if create:
            # Parent must exist; never create paths over a missing mount.
            try:self.root.mkdir(mode=0o700)
            except FileExistsError:pass
            else:created=True;sync(self.root.parent)
        self.validate_root()
        self.lock=self.root/'writer-v1.lock'
        self.pending=self.root/'normalizer-v1.pending'
        if created:
            self.create_file(self.lock)
        fd=checked_file(self.lock)
        info=os.fstat(fd);self.lock_identity=(info.st_dev,info.st_ino);os.close(fd)
        with _REGISTRY_LOCK:
            self.local=_REGISTRY.setdefault(str(self.root),(threading.RLock(),threading.local()))

    def validate_root(self):
        info=self.root.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise ValueError('Media writer state must be private and owned')
        if hasattr(self,'root_identity') and self.root_identity != (info.st_dev,info.st_ino):
            raise ValueError('Media writer state root changed')
        self.root_identity=(info.st_dev,info.st_ino)

    def create_file(self,path):
        self.validate_root()
        try:fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        except FileExistsError:
            fd=checked_file(path);os.close(fd);return
        try:
            os.write(fd,PROTOCOL);os.fsync(fd)
        finally:os.close(fd)
        sync(self.root)

    def fenced(self):
        try:fd=checked_file(self.pending)
        except FileNotFoundError:return False
        else:os.close(fd);return True

    @contextmanager
    def hold(self, *, allow_pending=False, timeout=30):
        if type(allow_pending) is not bool or timeout < 0:
            raise ValueError('Invalid writer admission policy')
        mutex,local=self.local
        deadline=time.monotonic()+timeout
        if not mutex.acquire(timeout=timeout):raise Busy('Another media writer is active')
        fd=None
        try:
            if getattr(local,'depth',0):
                if allow_pending and not local.allow_pending:
                    raise ValueError('Nested writer cannot gain recovery authority')
                local.depth+=1
                try:yield self
                finally:local.depth-=1
                return
            self.validate_root()
            fd=checked_file(self.lock,os.O_RDWR)
            while True:
                try:
                    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    info=os.fstat(fd);current=self.lock.lstat()
                    if (info.st_dev,info.st_ino)!=(current.st_dev,current.st_ino) or (info.st_dev,info.st_ino)!=self.lock_identity:
                        raise ValueError('Media writer lock changed')
                    if allow_pending or not self.fenced():break
                    fcntl.flock(fd,fcntl.LOCK_UN)
                except BlockingIOError:pass
                if time.monotonic()>=deadline:raise Busy('Media writer active or normalizer recovery pending')
                time.sleep(min(0.05,max(0,deadline-time.monotonic())))
            local.depth=1;local.allow_pending=allow_pending
            try:yield self
            finally:local.depth=0;local.allow_pending=False
        finally:
            if fd is not None:os.close(fd)
            mutex.release()

    def mark_pending(self):
        if not getattr(self.local[1],'depth',0) or not self.local[1].allow_pending:
            raise ValueError('Normalizer writer ownership required')
        self.create_file(self.pending)

    def clear_pending(self):
        if not getattr(self.local[1],'depth',0) or not self.local[1].allow_pending:
            raise ValueError('Normalizer writer ownership required')
        self.validate_root()
        fd=checked_file(self.pending)
        try:
            info=os.fstat(fd);current=self.pending.lstat()
            if (info.st_dev,info.st_ino)!=(current.st_dev,current.st_ino):
                raise ValueError('Normalizer recovery marker changed')
            self.pending.unlink();sync(self.root)
        finally:os.close(fd)
