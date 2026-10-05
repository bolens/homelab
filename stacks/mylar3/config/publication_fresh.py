"""Explicit reviewed creation for a virgin installation, never a loss fallback."""
import os
from pathlib import Path
import secrets
import stat

if __package__:
    from . import publication_guard as guard
    from .media_writer import Writer, sync
    from .workflow_store import Store
else:
    import publication_guard as guard
    from media_writer import Writer, sync
    from workflow_store import Store

CLAIM = 'publication-fresh-v1.json'


def native_absent(root):
    if any(os.path.lexists(root/('mylar.db'+suffix)) for suffix in ('','-journal','-wal','-shm')):
        raise guard.Unavailable('Fresh native state appeared')


def root_identity(root):
    root=Path(root)
    if (not root.is_absolute() or '..' in root.parts
            or any(path.is_symlink() for path in (root,*root.parents))):
        raise guard.Unavailable('Invalid fresh installation root')
    info=root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
        raise guard.Unavailable('Fresh installation root must already exist and be owned')
    return [info.st_dev,info.st_ino,info.st_uid]


def absent(root):
    # A pre-existing native catalog, even empty, requires the existing-state
    # reviewed bootstrap route. No interpretation of lost/malformed state.
    names=('mylar.db','workflow.sqlite','media-writer',CLAIM)
    paths=[root/name for name in names]
    paths.extend(root/(name+suffix) for name in ('mylar.db','workflow.sqlite')
                 for suffix in ('-journal','-wal','-shm'))
    if any(os.path.lexists(path) for path in paths):
        raise guard.Unavailable('Existing state cannot use fresh installation creation')


def _replace(root, before, after):
    claim=root/CLAIM
    if not guard.same_json(guard.private_json(claim),before):
        raise guard.Unavailable('Fresh installation claim changed')
    temporary=root/('.publication-fresh-'+secrets.token_hex(16)+'.tmp')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(guard.compact(after));stream.flush();os.fsync(stream.fileno())
        if not guard.same_json(guard.private_json(claim),before):
            raise guard.Unavailable('Fresh installation claim changed')
        os.replace(temporary,claim);sync(root)
    finally:
        if temporary.exists():temporary.unlink();sync(root)


@guard.state_errors
def prepare(root, backup, *, epoch):
    """Authenticated adapter has validated backup/epoch before calling here.

    Explicit preparation may create only a held namespace. Failure retains its
    claim and partial state for review; it never removes or recreates them.
    """
    import mylar
    from mylar import native_writers
    root=Path(root).absolute()
    if not native_writers.publication_mode() or root != Path(mylar.DATA_DIR).absolute():
        raise guard.Unavailable('Fresh preparation requires early native startup exclusion')
    identity=root_identity(root);absent(root)
    # Validate the pure fields again before claiming or creating anything.
    if (not guard.digest_value(epoch) or not isinstance(backup,dict)
            or set(backup)!={'manifest_sha256','restore_sha256','description'}
            or any(not guard.digest_value(backup[key]) for key in ('manifest_sha256','restore_sha256'))
            or not isinstance(backup['description'],str)
            or not 1<=len(backup['description'].encode('utf-8'))<=1024):
        raise guard.Unavailable('Reviewed fresh installation evidence required')
    claim=dict(version=1,phase='creating',root_identity=identity,
               epoch=epoch,backup=backup)
    fd=os.open(root/CLAIM,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(guard.compact(claim));stream.flush();os.fsync(stream.fileno())
    sync(root)
    if root_identity(root)!=identity:
        raise guard.Unavailable('Fresh installation root changed')
    # The exclusive claim serializes cooperating fresh API requests. Existing
    # native initialization must already be excluded by the startup adapter.
    native_absent(root)
    if any(os.path.lexists(root/name) for name in ('media-writer','workflow.sqlite','mylar.db')):
        raise guard.Unavailable('Fresh installation state appeared')
    writer=Writer(root/'media-writer',create=True)
    with writer.hold(allow_pending=True,allow_tagger_pending=True,allow_release_pending=True):
        if any(os.path.lexists(root/('workflow.sqlite'+suffix)) for suffix in ('','-journal','-wal','-shm')):
            raise guard.Unavailable('Fresh workflow state appeared')
        store=Store(root)
        state=guard.RegistryState(store.path,writer)
        token=state.prepare_bootstrap(backup,epoch=epoch)
        native_absent(root)
        if root_identity(root)!=identity:
            raise guard.Unavailable('Fresh installation baseline changed')
        _replace(root,claim,dict(claim,phase='prepared',token=token))
    return token


@guard.state_errors
def prepared_token(root):
    root=Path(root).absolute();value=guard.private_json(root/CLAIM)
    if (not isinstance(value,dict) or set(value)!={'version','phase','root_identity','epoch','backup','token'}
            or type(value['version']) is not int or value['version']!=1 or value['phase']!='prepared'
            or not guard.same_json(value['root_identity'],root_identity(root)) or not guard.digest_value(value['token'])):
        raise guard.Unavailable('Fresh installation preparation requires review')
    return value['token']
