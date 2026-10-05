"""Opt-in, incremental catalog metadata maintenance on the idle PP worker."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import time
import uuid
import zipfile
import zlib

if __package__:
    from . import converted_tagging, metadata_repair, tagger_archive
    from .tagger_adapter import fingerprint
    from .workflow_store import label
    from .publication_native import Review
    from .publication_guard import Unavailable
else:
    import converted_tagging, metadata_repair, tagger_archive
    from tagger_adapter import fingerprint
    from workflow_store import label
    from publication_native import Review
    from publication_guard import Unavailable

ACTIVE = ('queued', 'repairing')
ERRORS = (OSError, ValueError, RuntimeError, zipfile.BadZipFile, zlib.error, EOFError)


def key(path):
    return hashlib.sha256(str(path).encode()).hexdigest()


def source_version(path):
    source = Path(path)
    if not source.is_absolute() or '..' in source.parts or any(p.is_symlink() for p in (source, *source.parents)):
        raise ValueError('Linked or noncanonical library path')
    info = source.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size <= 0:
        raise ValueError('Expected one regular nonempty library archive')
    return list(tagger_archive.identity(info))


def classify(path):
    """Read bounded metadata only; admission performs full integrity verification."""
    with tagger_archive.regular(path) as stream:
        tagger_archive.directory_limits(stream)
        with zipfile.ZipFile(stream) as z:
            infos = z.infolist()
            if not infos or len(infos) > tagger_archive.MAX_MEMBERS:
                raise ValueError('Unsupported archive member count')
            copies = [i for i in infos if PurePosixPath(i.filename).name.casefold() == 'comicinfo.xml']
            if any(i.file_size > tagger_archive.MAX_XML for i in copies):
                raise ValueError('Oversized ComicInfo')
            for info in copies:
                metadata_repair.metadata.parse(z.read(info))
            if not copies:
                if b'ComicBookInfo' in z.comment:
                    return 'alternate'
                return 'missing'
            if len(copies) == 1 and copies[0].filename == 'ComicInfo.xml':
                return 'tagged'
            metadata_repair.layout(z)
            return 'nested'


def next_catalog(cursor):
    from mylar import db
    database = db.DBConnection()
    query = """SELECT * FROM (
      SELECT 'i:'||i.IssueID||':'||c.ComicID AS cursor,c.ComicLocation,i.Location
      FROM issues i JOIN comics c ON i.ComicID=c.ComicID WHERE i.Status='Downloaded'
      UNION ALL
      SELECT 'a:'||i.IssueID||':'||c.ComicID AS cursor,c.ComicLocation,i.Location
      FROM annuals i JOIN comics c ON i.ComicID=c.ComicID
      WHERE i.Status='Downloaded' AND NOT i.Deleted
    ) WHERE cursor>? ORDER BY cursor LIMIT 1"""
    rows = database.select(query, [cursor])
    if not rows:
        return None
    row = rows[0]
    path = str(Path(row['ComicLocation'])/row['Location']) if row['ComicLocation'] and row['Location'] else ''
    return row['cursor'], path


class Maintenance:
    def __init__(self, journal, next_entry, catalog, repair, recover, clock=time.time):
        self.journal, self.next_entry, self.catalog = journal, next_entry, catalog
        self.repair, self.recover, self.clock = repair, recover, clock

    def observe(self, path, version, policy, phase, reason):
        row = dict(path=path, identity=version, policy=policy, phase=phase, reason=reason, updated_at=self.clock())
        self.journal.set('library_observation', key(path), row)

    def tick(self, missing, nested):
        policy = [bool(missing), bool(nested)]
        if not any(policy):
            return
        pending = self.journal.active('library_repair', ACTIVE, 1) if nested else []
        if pending:
            self.process(pending[0])
            return
        scan = self.journal.get('library_scan', 'current', {})
        if scan.get('next_at', 0) > self.clock() and scan.get('policy') == policy:
            return
        cursor = scan.get('cursor', '') if scan.get('policy') == policy else ''
        entry = self.next_entry(cursor)
        if entry is None:
            self.journal.set('library_scan', 'current', dict(cursor='', next_at=self.clock()+3600,
                completed_at=self.clock(), policy=policy, reason='Sweep complete; next pass in one hour'))
            return
        cursor, path = entry
        # Save the cursor last, so an interrupted admission can replay idempotently.
        self.inspect(path, policy)
        self.journal.set('library_scan', 'current', dict(cursor=cursor, next_at=0, policy=policy,
            checked_at=self.clock(), reason='Inspecting catalog files while imports are idle'))

    def inspect(self, path, policy):
        if not path or Path(path).suffix.lower() != '.cbz':
            return
        version = None
        try:
            version = source_version(path)
            prior = self.journal.get('library_observation', key(path), {})
            if prior.get('identity') == version and prior.get('policy') == policy and prior.get('phase') == 'unchanged':
                return
            # Never take over an admitted conversion or an unfinished repair.
            for kind, phases in (('converted_tag', converted_tagging.ACTIVE), ('library_repair', ACTIVE)):
                if any(r['path'] == path for r in self.journal.active(kind, phases)):
                    return
            match = self.catalog(path)
            if not match:
                raise ValueError('No unique downloaded catalog owner')
            state = classify(path)
            if state in ('missing', 'nested') and policy[0 if state == 'missing' else 1]:
                archive = tagger_archive.snapshot(path, allow_nested_metadata=state == 'nested')
                digest = fingerprint(Path(path))
                if source_version(path) != version or list(archive.identity) != version:
                    raise ValueError('Source changed during inspection')
                request = dict(version=1, path=path, sha256=digest)
                if state == 'missing':
                    admission = converted_tagging.admit(json.dumps(request), self.journal)
                    phase = admission['phase']
                    reason = 'Missing ComicInfo admitted to tagging queue' if phase == 'queued' else 'Existing tagging job: '+phase
                else:
                    jobkey = key(json.dumps(dict(request, issueid=match['issueid'], comicid=match['comicid']), sort_keys=True))
                    self.journal.create('library_repair', jobkey, dict(request, **match, key=jobkey,
                        phase='queued', reason='Agreeing nested metadata queued for repair',
                        attempts=0, updated_at=self.clock()))
                    saved = self.journal.get('library_repair', jobkey)
                    phase, reason = saved['phase'], saved['reason']
                self.observe(path, version, policy, phase, reason)
            elif state == 'alternate':
                self.observe(path, version, policy, 'review', 'Alternate metadata preserved; automatic tagging skipped')
            else:
                self.observe(path, version, policy, 'unchanged', 'Existing tags preserved' if state == 'tagged' else 'Matching maintenance option is disabled')
        except ERRORS:
            self.observe(path, version, policy, 'review', 'Archive, metadata identity or catalog ownership requires review')

    def process(self, job):
        def save(phase, reason):
            job.update(phase=phase, reason=reason, updated_at=self.clock())
            self.journal.set('library_repair', job['key'], job)
        try:
            publication_review(job)
            match = self.catalog(job['path'])
            if not match or any(match[k] != job[k] for k in ('issueid', 'comicid')):
                raise ValueError('Catalog ownership changed')
            if job.get('token'):
                result = self.recover(job)
                if result == 'updated':
                    save('completed', 'Nested metadata reconciled; source XML retained as provenance')
                    return
                if result not in (None, 'failed'):
                    raise ValueError('Recovery requires review')
            if fingerprint(Path(job['path'])) != job['sha256']:
                raise ValueError('Source changed')
            if job['attempts'] >= 2:
                raise ValueError('Repair retry limit reached')
            job.update(token=uuid.uuid4().hex, attempts=job['attempts']+1)
            save('repairing', 'Reconciling nested metadata with verified publication')
            result = self.repair(job)
            if result != 'updated':
                raise ValueError('Repair publication requires review')
            save('completed', 'Nested metadata reconciled; source XML retained as provenance')
        except (Review, Unavailable):
            save('review', 'Publication evidence requires review; source and recovery evidence retained')
        except ERRORS:
            save('review', 'Repair could not be verified; source and recovery evidence retained')


def publication_review(job):
    runtime=sys.modules.get('mylar');writers=getattr(runtime,'native_writers',None)
    if writers is None or not writers.publication_mode():return
    from mylar import publication_native
    publication_native.require(Path(job['path']),issueid=job['issueid'],comicid=job['comicid'])
    # Moving nested provenance changes canonical member names. A direct
    # repair journal cannot authorize an unreviewed derivative alias.
    raise publication_native.Review('nested-metadata-derivative-unbound')


def repair(job):
    from mylar import native_writers, tagger_native, tagger_handoff
    publication_review(job)
    writer = native_writers.owner()
    publisher, _ = tagger_native.state(writer)
    writer.mark_tagger_pending()
    publisher.tag(Path(job['path']), {}, token=job['token'], expected_digest=job['sha256'], repair_nested=True)
    result = tagger_handoff.capture(publisher, job['token'])
    return result.metadata if result.valid_for(job['path']) else result.state


def poll():
    import mylar
    from mylar import workflow, native_writers
    if not converted_tagging.settings() or mylar.APILOCK or not mylar.PP_QUEUE.empty():
        return
    policy = workflow.policy()
    if not policy['library_missing_tags'] and not policy['library_nested_metadata']:
        return
    if not converted_tagging.RUN.acquire(blocking=False):
        return
    try:
        with native_writers.operation():
            if mylar.APILOCK or not mylar.PP_QUEUE.empty():
                return
            Maintenance(workflow.store(), next_catalog, converted_tagging.catalog, repair,
                        converted_tagging.recover).tick(policy['library_missing_tags'], policy['library_nested_metadata'])
    except (Review, Unavailable):
        mylar.logger.warn('Library metadata publication requires review; existing files and recovery state retained')
    except Exception:
        mylar.logger.warn('Library metadata maintenance deferred; existing files and recovery state retained')
    finally:
        converted_tagging.RUN.release()


def snapshot():
    from mylar import workflow
    journal = workflow.store()
    rows = journal.all('library_repair', 100)
    rows += [r for r in journal.active('library_observation', ('review',)) if r['phase'] == 'review']
    rows.sort(key=lambda r: r['updated_at'], reverse=True)
    return dict(scan=journal.get('library_scan', 'current', {}), rows=[
        dict(name=label(r['path']), phase=r['phase'], reason=label(r['reason']), updated_at=r['updated_at']) for r in rows[:100]])
