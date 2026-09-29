"""Native policy and versioned recovery ownership for the opt-in modern backend."""
import hashlib
import json
import os
import re
import stat

from .media_writer import sync
from .tagger_adapter import TERMINAL
from .tagger_nfs import Publisher
from .tagger_staging import Staging


def state(writer):
    """Bind recovery directories before admitting any publication or scanner."""
    root = writer.root.parent/'modern-tagger-v2'
    paths = (root, root/'journal-v2', root/'staging', root/'staging-receipts')
    binding = writer.root/'tagger-state-v2.identity'
    bound = binding.exists() or binding.is_symlink()
    identities = []
    for path in paths:
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Linked tagger recovery state')
        if not bound and not writer.fenced(tagger=True):
            path.mkdir(mode=0o700, exist_ok=True)
            sync(path.parent)
        info = path.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise ValueError('Expected private tagger recovery state')
        identities.append((info.st_dev, info.st_ino))
    expected = (hashlib.sha256(json.dumps(identities).encode()).hexdigest()+'\n').encode()
    if not bound:
        if writer.fenced(tagger=True):
            raise ValueError('Pending tagger recovery has no bound state')
        fd = os.open(binding, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
        try:
            os.write(fd, expected); os.fsync(fd)
        finally:
            os.close(fd)
        sync(writer.root)
    fd = os.open(binding, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or os.read(fd, 66) != expected):
            raise ValueError('Tagger recovery state identity changed')
    finally:
        os.close(fd)
    return Publisher(paths[1]), Staging(paths[2], paths[3])


def recover(writer):
    publisher, staging = state(writer)
    # Invalid receipts and unresolved publication conflicts keep all admission shut.
    writer.mark_tagger_pending()
    for result in publisher.recover_pending():
        if result.state not in TERMINAL:
            raise ValueError('Tagger publication recovery requires review')
    retained = staging.recover()
    writer.clear_tagger_pending()
    if retained:
        import mylar
        mylar.logger.warn('Modern tagger retained %s uncertain staging copies for review', retained)


def catalog(issueid):
    """Annual metadata belongs to its release volume, never its parent series."""
    from mylar import db
    from .tagger_lookup import identifier
    issueid = identifier(issueid)
    database = db.DBConnection()
    issues = database.select('SELECT ComicID FROM issues WHERE IssueID=?', [issueid])
    annuals = database.select('SELECT ReleaseComicID, Deleted FROM annuals WHERE IssueID=?', [issueid])
    volumes = {identifier(row['ComicID']) for row in issues}
    volumes.update(identifier(row['ReleaseComicID']) for row in annuals if not row['Deleted'])
    if any(row['Deleted'] for row in annuals) or len(volumes) > 1:
        raise ValueError('Ambiguous or deleted issue')
    if not volumes:
        arcs = database.select('SELECT ComicID FROM storyarcs WHERE IssueID=?', [issueid])
        volumes = {identifier(row['ComicID']) for row in arcs}
    if len(volumes) != 1:
        raise ValueError('No unique catalog volume')
    volumeid = volumes.pop()
    rows = database.select('SELECT ComicVersion, ComicYear FROM comics WHERE ComicID=?', [volumeid])
    if len(rows) > 1:
        raise ValueError('Ambiguous tracked volume')
    return issueid, volumeid, dict(rows[0]) if rows else {}


def run(dirName, nzbName=None, issueid=None, comversion=None, manual=None,
        filename=None, module=None, manualmeta=False, readingorder=None, agerating=None):
    import mylar
    from mylar import native_writers, tagger_handoff
    from .tagger_lookup import lookup
    from .tagger_service import Service
    def failure():
        return tagger_handoff.Published('unsupported') if manualmeta else tagger_handoff.Failure('unsupported')
    try:
        if type(manualmeta) is not bool or not filename or (not manualmeta and not native_writers.active()):
            return failure()
        # Snapshot settings once. Caller-provided comversion can describe an annual's
        # parent series, so derive the optional volume override from its release ID.
        config = mylar.CONFIG
        if not manualmeta and any(getattr(config, name, 'move') not in ('copy', 'move')
                                  for name in ('FILE_OPTS', 'ARC_FILEOPS')):
            # A native softlink would reference disposable staging. Preserve the
            # original import path until link-based placement has its own receipt.
            return failure()
        policy = dict(enabled=bool(manualmeta or config.ENABLE_META), comicrack=bool(config.CT_TAG_CR),
                      comicbooklover=bool(config.CT_TAG_CBL), conversion_only=bool(config.CBR2CBZ_ONLY),
                      overwrite=bool(config.CT_CBZ_OVERWRITE))
        api_key, base_url, interval = config.COMICVINE_API, config.COMICVINE_URL, config.CVAPI_RATE
        volume_enabled, year_volume, default_volume = config.CMTAG_VOLUME, config.CMTAG_START_YEAR_AS_VOLUME, config.SETDEFAULTVOLUME
        with native_writers.operation() as writer:
            issueid, volumeid, tracked = catalog(issueid)
            volume = None
            if volume_enabled and tracked:
                value = tracked.get('ComicYear' if year_volume else 'ComicVersion')
                if value in (None, '', 'None'):
                    value = '1' if default_volume and not year_volume else None
                if value is not None:
                    value = re.sub(r'^v', '', str(value), flags=re.I)
                    if not re.fullmatch(r'[0-9]{1,4}', value):
                        return failure()
                    volume = value
            publisher, staging = state(writer)
            writer.mark_tagger_pending()
            service = Service(publisher, staging.root,
                lambda **kwargs: lookup(api_key=api_key, base_url=base_url, interval=interval, **kwargs),
                tagger_handoff, native_writers.operation, staging=staging)
            return service.tag(filename, issueid=issueid, volumeid=volumeid, manualmeta=manualmeta,
                               volume=volume, reading_order=readingorder, age_rating=agerating, **policy)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        mylar.logger.warn('Modern tagging could not complete; original and recovery state retained')
        return failure()
