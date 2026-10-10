"""Coordinate complete conversion/maintenance cycles with native Mylar writers."""
import json
import hashlib
import os
import stat
import time
from media_writer import Writer, Busy, sync
from publication_guard import scope, evidence, Unavailable


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
    naming = getattr(normalizer, 'naming', None)
    if naming:
        naming.reconcile()  # The native owner alone can clear a release recovery fence.
    root=normalizer.config.get('writer_state')
    if root is None:
        normalizer.cycle()
        if maintenance:maintenance.cycle()
        return True
    if not isinstance(root,str) or not root:
        raise ValueError('writer_state must name an existing shared state directory')
    writer=Writer(root)
    try:
        prepare = getattr(maintenance,'prepare',None) if maintenance else None
        prepare_cycle=getattr(normalizer,'prepare_cycle',None)
        native_batch = None
        if prepare or prepare_cycle:
            # Prove authority without writing state before any remote work.
            with writer.hold(allow_pending=True,timeout=0),scope(normalizer,writer):
                pass
            if prepare_cycle:prepare_cycle()
            if prepare:native_batch = prepare()
        with writer.hold(allow_pending=True,timeout=0):
            # Fence before any work: Komga may keep writing after an API timeout
            # or process crash. The worker alone reconciles and clears this marker.
            with scope(normalizer,writer,native_batch=native_batch) as authority:
                cycle_census=authority.admission()
                bind_state(writer,normalizer)
                writer.mark_pending()
                normalizer.cycle()
                if maintenance:maintenance.cycle()
                bind_state(writer,normalizer)
                pending=any(json.loads(path.read_text())['phase']!='done'
                            for path in normalizer.jobs.glob('*/receipt.json'))
                if not evidence.same_json(cycle_census,authority.admission()):
                    raise Unavailable('Publication authority changed before reader collection')
                scans = getattr(normalizer, 'scan_batch', None)
                # Collection needs the owned current publication authority.
                scan_ready = bool(scans and scans.collect())
            if not pending:writer.clear_pending()
        try:
            if not pending:
                from conversion_handoff import dispatch as conversion_dispatch
                conversion_dispatch(normalizer)
                dispatch = getattr(maintenance,'dispatch',None) if maintenance else None
                if dispatch:dispatch()
                refresh_completed(normalizer)
        finally:
            if scan_ready:scans.dispatch()
        if not pending:
            from reader_handoff import dispatch as reader_dispatch
            reader_dispatch(normalizer)
        naming = getattr(normalizer, 'naming', None)
        if not pending and naming:
            naming.tick()  # Native rename owns the writer; call only after releasing our lock.
            reader_dispatch(normalizer)
        if not pending and maintenance:
            from ordinary_import_observation import post_cycle
            post_cycle(maintenance)  # fresh originals only after ALL current producers
        return True
    except Busy:
        # A busy lock is normal contention. Preserve errors and pending counts,
        # but update freshness so health does not misreport a stalled scan.
        from normalize import save
        for name in ('status.json','maintenance-status.json','reader-scan-status.json'):
            path=normalizer.state/name
            if name=='maintenance-status.json' and not maintenance:continue
            if name=='reader-scan-status.json' and not getattr(normalizer, 'scan_batch', None):continue
            previous=json.loads(path.read_text()) if path.exists() else {'errors':[]}
            previous.update(checked_at=time.time(),state='waiting for media writer')
            save(path,previous)
        return False


def refresh_completed(normalizer):
    """Retry independent durable rescan/tag admissions outside the writer lock."""
    from normalize import save
    failures = 0
    for receipt in normalizer.jobs.glob('*/receipt.json'):
        job = json.loads(receipt.read_text())
        if job['phase'] == 'done' and (job.get('mylar_refresh_pending') or job.get('mylar_tag_pending')):
            try:
                if job.get('mylar_refresh_pending'):
                    normalizer.refresh_mylar(job)
                    job.pop('mylar_refresh_pending')
                    save(receipt, job)
                elif job.get('mylar_tag_pending'):
                    normalizer.refresh_tagged(job)
                    save(receipt, job)
            except Exception:
                failures += 1
    if failures:
        raise RuntimeError('Mylar notifications remain pending for retry: '+str(failures))
