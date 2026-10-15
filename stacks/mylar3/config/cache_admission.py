"""Native effective policy plus shared cache admission; no retained deletion."""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import stat

try:
    from . import cache_reservation as shared
except ImportError:
    import cache_reservation as shared

GIB=shared.GIB
DEFAULT_MAX_GIB=shared.DEFAULT_MAX_GIB
DEFAULT_FREE_GIB=shared.DEFAULT_FREE_GIB
MAX_ENTRIES=shared.MAX_ENTRIES
BLOCK=shared.BLOCK
Held=shared.Held
setting=shared.setting
validate_update=shared.validate_update
identity=shared.identity
directory_identity=shared.directory_identity
open_directory=shared.open_directory
usage=shared.usage
rounded=shared.rounded
Temporary=shared.Temporary
temporary=shared.temporary
fcntl=shared.fcntl

def configured():
    import mylar
    cfg = mylar.CONFIG
    try:
        maximum = setting(getattr(cfg, 'DDL_CACHE_MAX_GIB', DEFAULT_MAX_GIB)) * GIB
        reserve = setting(getattr(cfg, 'DDL_CACHE_MIN_FREE_GIB', DEFAULT_FREE_GIB)) * GIB
    except ValueError:
        raise Held('Invalid finite cache configuration') from None
    data = Path(mylar.DATA_DIR).absolute()
    cache = Path(cfg.CACHE_DIR).absolute()
    ddl = Path(cfg.DDL_LOCATION or cfg.CACHE_DIR).absolute()
    roots = tuple(sorted({cache, ddl}, key=lambda p: (len(p.parts), str(p))))
    roots = tuple(p for p in roots if not any(q != p and q in p.parents for q in roots))
    for p in (data, *roots):
        if p.resolve(strict=True) != p or not p.is_dir():
            raise Held('Cache roots must be original canonical directories')
    return data, roots, maximum, reserve


class Allocation(shared.Allocation):
    def configuration(self):
        return configured()


@contextmanager
def allocation(destination,required=None,nodes=0):
    with Allocation(destination,required,nodes) as reservation:
        yield reservation


def initialize_shared_lock():
    """Normal admitted startup creates only the existing native reservation lock."""
    data,_,_,_=configured()
    fd,nodes=open_directory(data)
    lock=None
    try:
        lock=os.open('cache-admission-v1.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=fd)
        z=os.fstat(lock);row=identity(z)
        if not stat.S_ISREG(z.st_mode) or z.st_nlink!=1 or z.st_uid!=os.geteuid() or stat.S_IMODE(z.st_mode)!=0o600:
            raise Held('Cache allocation lock is not private and original')
        if identity(os.lstat(data/'cache-admission-v1.lock'))!=row:
            raise Held('Original cache allocation lock changed')
        for name,expected in nodes.items():
            if directory_identity(os.lstat(name))!=expected:raise Held('Original cache ancestor changed')
        os.fsync(lock);os.fsync(fd)
    finally:
        if lock is not None:os.close(lock)
        os.close(fd)
    if identity(os.lstat(data/'cache-admission-v1.lock'))!=row:
        raise Held('Original cache allocation lock changed after initialization')
    for name,expected in nodes.items():
        if directory_identity(os.lstat(name))!=expected:raise Held('Original cache ancestor changed')


def policy_snapshot():
    """Read-only effective policy from actual CONFIG under the owning native Writer."""
    from . import native_writers
    if not native_writers.publication_mode() or not native_writers.active():
        raise Held('Cache policy requires actual native Writer')
    original=configured();data,roots,maximum,reserve=original
    import mylar
    ddl=Path(mylar.CONFIG.DDL_LOCATION or mylar.CONFIG.CACHE_DIR).absolute()
    if ddl.resolve(strict=True)!=ddl or not any(ddl==p or p in ddl.parents for p in roots):raise Held('Original DDL root unavailable')
    nodes={};opened=[]
    try:
        for directory in (data,*roots,ddl):
            fd,ancestors=open_directory(directory);opened.append(fd)
            for name,row in ancestors.items():
                if name in nodes and nodes[name]!=row:raise Held('Original cache ancestors conflict')
                nodes.setdefault(name,row)
        datafd=opened[0];data5=directory_identity(os.fstat(datafd))
        root5=[directory_identity(os.fstat(fd)) for fd in opened[1:1+len(roots)]]
        ddl5=directory_identity(os.fstat(opened[-1]))
        path=data/'config.ini';fd=os.open('config.ini',os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=datafd)
        try:
            z=os.fstat(fd);config9=identity(z)
            if not stat.S_ISREG(z.st_mode) or z.st_uid not in (0,os.geteuid()) or z.st_nlink!=1 or z.st_mode&0o022 or not 0<z.st_size<=2*1024**2 or identity(os.lstat(path))!=config9:
                raise Held('Original cache configuration unavailable')
            raw=b''
            while len(raw)<z.st_size:
                part=os.read(fd,65536)
                if not part:raise Held('Short cache configuration')
                raw+=part
            if identity(os.fstat(fd))!=config9 or identity(os.lstat(path))!=config9:
                raise Held('Original cache configuration changed')
        finally:os.close(fd)
        lock=data/'cache-admission-v1.lock';lockfd=os.open(lock.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=datafd)
        try:
            z=os.fstat(lockfd);lock9=identity(z)
            if not stat.S_ISREG(z.st_mode) or z.st_nlink!=1 or z.st_uid!=os.geteuid() or stat.S_IMODE(z.st_mode)!=0o600 or identity(os.lstat(lock))!=lock9:
                raise Held('Original shared cache lock unavailable')
        finally:os.close(lockfd)
    finally:
        for fd in reversed(opened):os.close(fd)
    result=dict(version=1,kind='effective-ddl-cache-policy-v1',data=dict(path=str(data),identity5=list(data5)),roots=[dict(path=str(p),identity5=list(row)) for p,row in zip(roots,root5)],ddl=dict(path=str(ddl),identity5=list(ddl5)),lock=dict(path=str(lock),signature9=list(lock9)),config=dict(path=str(path),signature9=list(config9),sha256=hashlib.sha256(raw).hexdigest()),maximum=maximum,reserve=reserve)
    if configured()!=original or Path(mylar.CONFIG.DDL_LOCATION or mylar.CONFIG.CACHE_DIR).absolute()!=ddl:raise Held('Effective cache configuration changed')
    for name,row in nodes.items():
        if directory_identity(os.lstat(name))!=row:raise Held('Original cache ancestor changed')
    if directory_identity(os.lstat(ddl))!=ddl5 or directory_identity(os.lstat(data))!=data5 or any(directory_identity(os.lstat(p))!=row for p,row in zip(roots,root5)) or identity(os.lstat(path))!=config9 or identity(os.lstat(lock))!=lock9:
        raise Held('Original effective cache policy changed')
    return result
