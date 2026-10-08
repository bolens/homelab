"""Explicit, offline, repeatable reader metadata maintenance under writer exclusion."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import sqlite3
import time
import uuid
import zipfile

if __package__:
    from .media_writer import Writer, sync
    from .tagger_adapter import fingerprint, TERMINAL
    from .tagger_archive import directory_limits, regular, snapshot
    from .tagger_enrichment import supplements, validate
    from .tagger_metadata import MAX_XML
else:
    from media_writer import Writer, sync
    from tagger_adapter import fingerprint, TERMINAL
    from tagger_archive import directory_limits, regular, snapshot
    from tagger_enrichment import supplements, validate
    from tagger_metadata import MAX_XML


def metadata(path):
    with regular(path) as stream:
        directory_limits(stream)
        with zipfile.ZipFile(stream) as archive:
            nodes = [i for i in archive.infolist() if Path(i.filename).name.casefold() == 'comicinfo.xml']
            if len(nodes) != 1 or nodes[0].filename != 'ComicInfo.xml' or nodes[0].file_size > MAX_XML:
                raise ValueError('Expected bounded root metadata')
            return archive.read(nodes[0])


def archives(roots):
    for root in roots:
        root = Path(root).absolute()
        if not root.is_dir() or any(p.is_symlink() for p in (root, *root.parents)):
            raise ValueError('Expected existing unlinked library root')
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(n for n in dirs if not n.startswith('.') and not (Path(directory)/n).is_symlink())
            for name in sorted(files):
                path = Path(directory)/name
                if path.suffix.lower() == '.cbz' and not path.is_symlink():
                    yield path


def authority_signature(info):
    # Read access time can advance during SQLite verification without a mutation.
    return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,
            info.st_mode,info.st_uid,info.st_gid,info.st_nlink)


def publication_review(writer):
    """An unbound maintenance caller cannot replay native correction state."""
    runtime=sys.modules.get('mylar')
    writers=getattr(runtime,'native_writers',None)
    if writers is not None and writers.publication_mode():
        from mylar.publication_native import Review
        raise Review('reader-supplement-transition-unbound')
    names=('publication-v1.json','tagger-publication-v1.json','tagger-recovery-v1.pending')
    protected=any(os.path.lexists(writer.root/name) for name in names)
    if protected:
        raise ValueError('Reader supplementation requires bound native publication admission')
    database=writer.root.parent/'workflow.sqlite'
    if os.path.lexists(database):
        if (database.is_symlink() or any(p.is_symlink() for p in database.parents)
                or any(os.path.lexists(Path(str(database)+suffix)) for suffix in ('-journal','-wal','-shm'))):
            raise ValueError('Supplement authority requires review')
        parents={}
        for parent in database.parents:
            info=parent.lstat()
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError('Supplement authority requires existing unlinked parents')
            parents[parent]=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)
        before=database.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_uid!=os.geteuid() or before.st_nlink!=1:
            raise ValueError('Supplement authority requires owned existing state')
        if not 4096<=before.st_size<=256*1024**2:
            raise ValueError('Supplement authority exceeds bounds')
        fd=os.open(database,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        try:
            if authority_signature(os.fstat(fd))!=authority_signature(before):
                raise ValueError('Supplement authority changed before read')
            connection=sqlite3.connect(Path('/proc/self/fd/'+str(fd)).as_uri()+'?mode=ro&immutable=1',uri=True)
            try:
                deadline=time.monotonic()+30
                connection.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
                protected=protected or connection.execute(
                    "SELECT 1 FROM records WHERE substr(kind,1,12)='publication_' LIMIT 1").fetchone() is not None
            except sqlite3.Error:
                raise ValueError('Supplement authority is unreadable or exceeds verification time') from None
            finally:connection.close()
            if authority_signature(os.fstat(fd))!=authority_signature(before):
                raise ValueError('Supplement authority changed during admission')
        finally:os.close(fd)
        for parent,identity in parents.items():
            info=parent.lstat()
            if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=identity:
                raise ValueError('Supplement authority parents changed during admission')
        if (authority_signature(database.lstat())!=authority_signature(before)
                or any(os.path.lexists(Path(str(database)+suffix)) for suffix in ('-journal','-wal','-shm'))):
            raise ValueError('Supplement authority changed during admission')
    if protected:
        raise ValueError('Reader supplementation requires bound native publication admission')


def recover(writer, publisher):
    """Recover before enumeration: an interrupted publication can hide its source."""
    publication_review(writer)
    with writer.hold(allow_tagger_pending=True, timeout=30):
        for result in publisher.recover_pending():
            if result.state not in TERMINAL:
                raise ValueError('Outstanding publication requires recovery')
        if writer.fenced(tagger=True):
            writer.clear_tagger_pending()


def apply(path, policy, writer, publisher, backup_root):
    """Back up, restore-verify, publish, and compare every non-metadata member."""
    publication_review(writer)
    with writer.hold(allow_tagger_pending=True, timeout=30):
        recover(writer, publisher)
        if not supplements(metadata(path), policy):
            return 'unchanged'
        old = snapshot(path)
        security = publisher.security(path)
        before = fingerprint(path)
        folder = backup_root/uuid.uuid4().hex
        folder.mkdir(mode=0o700)
        backup, restored = folder/'original.cbz', folder/'restored.cbz'
        shutil.copy2(path, backup)
        shutil.copy2(backup, restored)
        for copy in (backup, restored):
            with regular(copy) as stream:
                os.fsync(stream.fileno())
        sync(folder)
        sync(backup_root)
        if fingerprint(backup) != before or fingerprint(restored) != before or snapshot(restored).members != old.members:
            raise ValueError('Backup restore verification failed')
        restored.unlink()
        result = _publish(path, policy, writer, publisher, old, before, security, uuid.uuid4().hex)
        backup.unlink()
        folder.rmdir()
        return result['state']


def _publish(path, policy, writer, publisher, old, before, security, token):
    """Publication half; callers own verified preservation and writer admission."""
    publication_review(writer)
    additions = supplements(old.xml, policy)
    if not additions:
        return dict(state='unchanged', token=None, before=before, after=before,
                    fields=[], payloads_verified=True)
    writer.mark_tagger_pending()
    result = publisher.tag(path, {}, token=token, supplement=policy, expected_digest=before)
    if result.state not in ('committed', 'unchanged'):
        raise ValueError('Supplement publication failed; backup retained')
    new = snapshot(path)
    if ((old.members, old.comment, old.mode, old.uid, old.gid) !=
            (new.members, new.comment, new.mode, new.uid, new.gid)
            or {a[0]:a[1:] for a in old.attributes} != {a[0]:a[1:] for a in new.attributes}
            or publisher.security(path) != security or supplements(new.xml, policy)):
        raise ValueError('Preservation or completeness verification failed; backup retained')
    writer.clear_tagger_pending()
    return dict(state=result.state, token=token, journal=str(publisher.receipt(token)),
                before=before, after=fingerprint(path), fields=sorted(additions), payloads_verified=True)


def apply_preserved(path, policy, writer, publisher, original, restored, expected_digest, token):
    """Reuse caller-owned copies after a verified reader move; never delete them.

    The caller journals the token before admission and reconciles it after a
    failure. Existing tokens are never replayed through this entry point.
    """
    if (not isinstance(expected_digest, str) or not isinstance(token, str)
            or not re.fullmatch(r'[0-9a-f]{64}', expected_digest) or not re.fullmatch(r'[0-9a-f]{32}', token)):
        raise ValueError('Expected verified digest and new publication token')
    path, original, restored = map(Path, (path, original, restored))
    if (any(not p.is_absolute() or '..' in p.parts for p in (path, original, restored))
            or len({path, original, restored}) != 3 or original.parent != restored.parent):
        raise ValueError('Expected distinct preservation copies in one private folder')
    folder = original.parent
    info = folder.lstat()
    if (any(p.is_symlink() for p in (folder, *folder.parents)) or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError('Expected private owned preservation folder')
    runtime=sys.modules.get('mylar');writers=getattr(runtime,'native_writers',None)
    if writers is not None and writers.publication_mode():
        return owned_preserved(path,validate(policy),writer,publisher,original,restored,expected_digest,token)
    publication_review(writer)
    with writer.hold(allow_tagger_pending=True, timeout=30):
        recover(writer, publisher)
        if publisher.receipt(token).exists():
            raise ValueError('Existing publication token requires reconciliation')
        old = snapshot(path)
        security = publisher.security(path)
        if fingerprint(path) != expected_digest:
            raise ValueError('Combined source changed before metadata admission')
        for copy in (original, restored):
            info = copy.lstat()
            if (copy.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_uid != os.geteuid() or fingerprint(copy) != expected_digest):
                raise ValueError('Caller preservation hash or ownership changed')
            saved = snapshot(copy)
            if ((saved.members, saved.comment, saved.xml, saved.attributes) !=
                    (old.members, old.comment, old.xml, old.attributes)):
                raise ValueError('Caller restore archive differs from source')
        return _publish(path, validate(policy), writer, publisher, old, expected_digest, security, token)


def owned_preserved(path,policy,writer,publisher,original,restored,expected_digest,token):
    """Exact native supplement role; root metadata only, retained pair stays intact."""
    policy=json.loads(json.dumps(policy))
    import mylar
    from mylar import native_writers,publication_native as native,publication_guard as guard
    from mylar import publication_transaction,release_naming,tagger_pack
    if (not callable(getattr(native_writers,'operation',None)) or type(publisher) is not tagger_pack.Publisher):
        raise native.Review('supplement-producer-unbound')
    try:
        with native_writers.operation() as actual_writer:
            if guard.writer_identity(actual_writer)!=guard.writer_identity(writer):
                raise native.Review('supplement-writer-changed')
            publication_transaction.state_evidence(writer)
            if (Path(publisher.config_root).absolute()!=writer.root.parent
                    or publisher.root!=writer.root.parent/'modern-tagger-v2/journal-v2'
                    or publisher.receipt(token).exists() or publisher.receipt(token).is_symlink()):
                raise native.Review('supplement-publication-token-unbound')
            database,_=release_naming.services();catalog=release_naming.catalog(database,path)
            issueid=str(catalog['row']['IssueID']);comicid=str(catalog['row']['ComicID'])
            proof=native.require(path,issueid=issueid,comicid=comicid)
            old=snapshot(path);security=publisher.security(path)
            census=guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json')[0]
            selected=guard.observe_owners(Path(mylar.DATA_DIR)/'mylar.db',writer,[proof['owner']],
                                         [mylar.CONFIG.DESTINATION_DIR])['observed']
            if proof['inventory']['source_sha256']!=expected_digest:
                raise native.Review('supplement-source-changed')
            pair={}
            for name,copy in (('original',original),('restore',restored)):
                signature,checksum=guard.file_hash(copy)
                saved=snapshot(copy)
                if (checksum!=expected_digest or signature[6]!=os.geteuid() or signature[8]!=1
                        or (saved.members,saved.comment,saved.xml,saved.attributes)!=
                           (old.members,old.comment,old.xml,old.attributes)):
                    raise native.Review('supplement-preservation-changed')
                pair[name]=dict(path=str(copy),signature=signature)
            publication_transaction.preserved_pair(pair,expected_digest)
            additions=supplements(old.xml,policy)
            if not additions:
                fresh=native.require(path,issueid=issueid,comicid=comicid)
                signature,digest=guard.file_hash(path)
                observed=guard.observe_owners(Path(mylar.DATA_DIR)/'mylar.db',writer,[proof['owner']],
                                             [mylar.CONFIG.DESTINATION_DIR])['observed']
                current=guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json')[0]
                if (digest!=expected_digest or not guard.same_json(signature,proof['inventory']['source_signature'])
                        or fresh['inventory']['source_sha256']!=expected_digest
                        or not guard.same_json(fresh['owner'],proof['owner'])
                        or not guard.same_json(observed,selected) or not guard.same_json(current,census)
                        or publisher.security(path)!=security or snapshot(path).identity!=old.identity):
                    raise native.Review('supplement-unchanged-source-changed')
                return dict(state='unchanged',token=None,before=expected_digest,after=expected_digest,
                            fields=[],payloads_verified=True)
            captured=dict(role='preserved-supplement',manualmeta=True,supplement=policy,preservation=pair,
                          expected_digest=expected_digest,owner_observed=selected)
            with publication_transaction.tagging(writer,path,issueid,token,captured,modern=True) as job:
                result=publisher.tag(path,{},token=token,supplement=policy,expected_digest=expected_digest)
                if result.state not in ('committed','unchanged'):
                    raise native.Review('supplement-terminal-publication-required')
                new=snapshot(path)
                if ((old.members,old.comment,old.mode,old.uid,old.gid,old.attributes)!=
                        (new.members,new.comment,new.mode,new.uid,new.gid,new.attributes)
                        or publisher.security(path)!=security or supplements(new.xml,policy)):
                    raise native.Review('supplement-preservation-verification-failed')
                job.complete(publisher,None,path)
                return dict(state=result.state,token=token,journal=str(publisher.receipt(token)),
                            before=expected_digest,after=fingerprint(path),fields=sorted(additions),
                            payloads_verified=True)
    except (guard.Unavailable,OSError,ValueError,TypeError,KeyError):
        raise native.Review('supplement-owned-evidence-unavailable') from None


def bound_publisher(writer):
    """Require the same existing recovery binding as native Modern tagging."""
    root = writer.root.parent/'modern-tagger-v2'
    paths = (root, root/'journal-v2', root/'staging', root/'staging-receipts')
    identities = []
    for path in paths:
        info = path.lstat()
        if (any(p.is_symlink() for p in (path, *path.parents)) or not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700):
            raise ValueError('Expected private bound recovery state')
        identities.append((info.st_dev, info.st_ino))
    expected = (hashlib.sha256(json.dumps(identities).encode()).hexdigest()+'\n').encode()
    fd = os.open(writer.root/'tagger-state-v2.identity', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or os.read(fd, 66) != expected):
            raise ValueError('Tagger recovery state identity changed')
    finally:
        os.close(fd)
    if __package__:
        from .tagger_pack import Publisher as NativePublisher
    else:
        from tagger_pack import Publisher as NativePublisher
    return NativePublisher(paths[1], writer.root.parent)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('roots', nargs='+')
    parser.add_argument('--policy', help='Private JSON object of verified ComicInfo field overrides')
    parser.add_argument('--apply', action='store_true', help='Default is a read-only plan')
    parser.add_argument('--config', default='/config/mylar')
    parser.add_argument('--backup-root', help='Existing private owned directory, required for apply')
    args = parser.parse_args(argv)
    policy = validate(json.loads(Path(args.policy).read_text()) if args.policy else {})
    writer = publisher = backup_root = None
    if args.apply:
        if not args.backup_root:
            parser.error('--apply requires --backup-root')
        backup_root = Path(args.backup_root).absolute()
        info = backup_root.lstat()
        if (any(p.is_symlink() for p in (backup_root, *backup_root.parents)) or not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700):
            parser.error('Backup directory must be private, owned, and unlinked')
        writer = Writer(Path(args.config)/'media-writer')
        # Startup owns state creation/binding. Never create it during maintenance.
        publication_review(writer)
        with writer.hold(allow_tagger_pending=True, timeout=30):
            publisher = bound_publisher(writer)
            recover(writer, publisher)
    counts, fields = Counter(), Counter()
    for path in archives(args.roots):
        counts['checked'] += 1
        try:
            additions = supplements(metadata(path), policy)
            fields.update(additions.keys())
            if additions:
                counts[apply(path, policy, writer, publisher, backup_root) if args.apply else 'planned'] += 1
            else:
                counts['unchanged'] += 1
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile):
            counts['errors'] += 1
            if args.apply:
                # Stop before touching another source; retain backups and fence.
                print(json.dumps({'counts': dict(counts), 'fields': dict(fields), 'stopped': True}), flush=True)
                raise SystemExit(1)
        if counts['checked'] % 100 == 0:
            print(json.dumps({'counts': dict(counts), 'fields': dict(fields)}), flush=True)
    print(json.dumps({'counts': dict(counts), 'fields': dict(fields), 'complete': True}), flush=True)
    return 1 if counts['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
