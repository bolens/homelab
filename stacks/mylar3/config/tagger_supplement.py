"""Explicit, offline, repeatable reader metadata maintenance under writer exclusion."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import uuid
import zipfile

if __package__:
    from .media_writer import Writer, sync
    from .tagger_adapter import fingerprint, TERMINAL
    from .tagger_archive import directory_limits, regular, snapshot
    from .tagger_enrichment import supplements, validate
    from .tagger_metadata import MAX_XML
    from .tagger_nfs import Publisher
else:
    from media_writer import Writer, sync
    from tagger_adapter import fingerprint, TERMINAL
    from tagger_archive import directory_limits, regular, snapshot
    from tagger_enrichment import supplements, validate
    from tagger_metadata import MAX_XML
    from tagger_nfs import Publisher


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


def recover(writer, publisher):
    """Recover before enumeration: an interrupted publication can hide its source."""
    with writer.hold(allow_tagger_pending=True, timeout=30):
        for result in publisher.recover_pending():
            if result.state not in TERMINAL:
                raise ValueError('Outstanding publication requires recovery')
        if writer.fenced(tagger=True):
            writer.clear_tagger_pending()


def apply(path, policy, writer, publisher, backup_root):
    """Back up, restore-verify, publish, and compare every non-metadata member."""
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
        writer.mark_tagger_pending()
        # Each admission is a new attempt. Recovery can roll an interrupted
        # publication back to the same source bytes with a failed terminal token.
        token = uuid.uuid4().hex
        result = publisher.tag(path, {}, token=token, supplement=policy, expected_digest=before)
        if result.state not in ('committed', 'unchanged'):
            raise ValueError('Supplement publication failed; backup retained')
        new = snapshot(path)
        if ((old.members, old.comment, old.mode, old.uid, old.gid) !=
                (new.members, new.comment, new.mode, new.uid, new.gid)
                or publisher.security(path) != security or supplements(new.xml, policy)):
            raise ValueError('Preservation or completeness verification failed; backup retained')
        # The verified publisher already compares XML reconciliation and archive
        # attributes. Keep the crash fence until independent completeness passes.
        writer.clear_tagger_pending()
        backup.unlink()
        folder.rmdir()
        return result.state


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
    return Publisher(paths[1])


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
