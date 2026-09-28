"""Coordinate complete conversion/maintenance cycles with native Mylar writers."""
import json
import hashlib
import os
import stat
import time
from media_writer import Writer, Busy, sync


def bind_state(writer, normalizer):
    # A missing/remounted recovery directory must not look like "no pending jobs".
    identities=[]
    for path in (normalizer.state,normalizer.jobs):
        if any(p.is_symlink() for p in (path,*path.parents)):
            raise ValueError('Linked normalizer recovery state')
        info=path.lstat()
        if not stat.S_ISDIR(info.st_mode):raise ValueError('Missing normalizer recovery state')
        identities.append((info.st_dev,info.st_ino))
    expected=(hashlib.sha256(json.dumps(identities).encode()).hexdigest()+'\n').encode()
    path=writer.root/'normalizer-state-v1.identity'
    if not path.exists() and writer.fenced():
        raise ValueError('Pending recovery has no bound state identity; review required')
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    except FileExistsError:pass
    else:
        try:os.write(fd,expected);os.fsync(fd)
        finally:os.close(fd)
        sync(writer.root)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.geteuid()
                or stat.S_IMODE(info.st_mode)!=0o600 or os.read(fd,66)!=expected):
            raise ValueError('Normalizer recovery state identity changed; review required')
    finally:os.close(fd)


def cycle(normalizer, maintenance=None):
    root=normalizer.config.get('writer_state')
    if root is None:
        normalizer.cycle()
        if maintenance:maintenance.cycle()
        return True
    if not isinstance(root,str) or not root:
        raise ValueError('writer_state must name an existing shared state directory')
    writer=Writer(root)
    try:
        with writer.hold(allow_pending=True,timeout=0):
            # Fence before any work: Komga may keep writing after an API timeout
            # or process crash. The worker alone reconciles and clears this marker.
            bind_state(writer,normalizer)
            writer.mark_pending()
            normalizer.cycle()
            if maintenance:maintenance.cycle()
            bind_state(writer,normalizer)
            pending=any(json.loads(path.read_text())['phase']!='done'
                        for path in normalizer.jobs.glob('*/receipt.json'))
            if not pending:writer.clear_pending()
            return True
    except Busy:
        # A busy lock is normal contention. Preserve errors and pending counts,
        # but update freshness so health does not misreport a stalled scan.
        from normalize import save
        for name in ('status.json','maintenance-status.json'):
            path=normalizer.state/name
            if name=='maintenance-status.json' and not maintenance:continue
            previous=json.loads(path.read_text()) if path.exists() else {'errors':[]}
            previous.update(checked_at=time.time(),state='waiting for media writer')
            save(path,previous)
        return False
