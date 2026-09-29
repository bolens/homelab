"""Durable missing-metadata follow-up for verified normalizer conversions."""
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import uuid
import zipfile
import zlib

ACTIVE = ('queued', 'waiting-library', 'waiting-settings', 'tagging', 'retry')
RUN = threading.Lock()
_TAGGING = False


def store():
    from mylar import workflow
    return workflow.store()


def admit(payload, journal=None):
    if not isinstance(payload, str) or len(payload.encode('utf-8')) > 8192:
        raise ValueError('Invalid conversion request')
    try:
        value = json.loads(payload)
    except (ValueError, RecursionError) as error:
        raise ValueError('Invalid conversion request') from error
    if (not isinstance(value, dict) or set(value) != {'version', 'path', 'sha256'}
            or type(value['version']) is not int or value['version'] != 1):
        raise ValueError('Invalid conversion request')
    name, digest = value['path'], value['sha256']
    if (not isinstance(name, str) or len(name) > 4096 or re.search(r'[\x00-\x1f\x7f]', name)
            or not name.startswith('/') or str(Path(name)) != name or '..' in Path(name).parts
            or Path(name).suffix.lower() != '.cbz'
            or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)):
        raise ValueError('Invalid conversion request')
    key = hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    journal = journal if journal is not None else store()
    now = journal.clock()
    record = dict(value, key=key, phase='queued', reason='Waiting for catalog rescan',
                  attempts=0, retry_at=0, created_at=now, updated_at=now)
    journal.create('converted_tag', key, record)
    return dict(version=1, key=key, phase=journal.get('converted_tag', key)['phase'])


class Queue:
    def __init__(self, journal, catalog, coordinate, inspect, tag, recover, settings, clock=time.time):
        self.journal, self.catalog, self.coordinate = journal, catalog, coordinate
        self.inspect, self.tag, self.recover, self.settings = inspect, tag, recover, settings
        self.clock = clock

    def save(self, job, phase, reason, delay=0):
        job.update(phase=phase, reason=reason, retry_at=self.clock()+delay, updated_at=self.clock())
        self.journal.set('converted_tag', job['key'], job)

    def retry(self, job):
        if job['attempts'] >= 6:
            self.save(job, 'review', 'Tagging retry limit reached; review required')
        else:
            self.save(job, 'retry', 'Tagging did not finish; retry scheduled', min(3600, 60*2**job['attempts']))

    def tick(self):
        jobs = self.journal.active('converted_tag', ACTIVE)
        job = next((r for r in jobs if r.get('retry_at', 0) <= self.clock()), None)
        if job is None:
            return
        try:
            with self.coordinate():
                self.process(job)
        except Exception:
            # Keep unknown ownership/recovery failures retryable, without spending
            # a publication attempt or clearing any native recovery marker.
            self.save(job, 'retry', 'Writer or recovery state unavailable; retry scheduled', 60)

    def process(self, job):
        try:
            match = self.catalog(job['path'])
        except ValueError:
            self.save(job, 'review', 'Catalog ownership is ambiguous; review required')
            return
        if not match:
            if self.clock()-job['created_at'] >= 86400:
                self.save(job, 'review', 'No exact downloaded issue after rescan; review required')
            else:
                self.save(job, 'waiting-library', 'Waiting for exact downloaded issue after rescan', 60)
            return
        if job.get('issueid') and (job['issueid'], job['comicid']) != (match['issueid'], match['comicid']):
            self.save(job, 'review', 'Catalog ownership changed; review required')
            return
        job.update(match)
        if job.get('token'):
            result = self.recover(job)
            if result in ('added', 'updated', 'unchanged'):
                self.save(job, 'completed', 'Metadata '+result+'; publication verified')
                return
            if result not in (None, 'failed', 'timed_out', 'unsupported'):
                self.save(job, 'review', 'Publication recovery requires review')
                return
        if not self.settings():
            self.save(job, 'waiting-settings', 'Waiting for enabled Modern ComicRack metadata tagging', 60)
            return
        try:
            digest, has_metadata = self.inspect(job['path'])
        except (OSError, ValueError, zipfile.BadZipFile, zlib.error, EOFError):
            self.save(job, 'review', 'Converted archive is missing or invalid; review required')
            return
        if has_metadata:
            self.save(job, 'completed', 'Existing ComicInfo preserved; no automatic retag')
            return
        if digest != job['sha256']:
            self.save(job, 'review', 'Converted archive changed; review required')
            return
        if job['attempts'] >= 6:
            self.retry(job)
            return
        job.update(token=uuid.uuid4().hex, attempts=job['attempts']+1)
        self.save(job, 'tagging', 'Adding missing ComicInfo metadata')
        result = self.tag(job)
        if result in ('added', 'updated', 'unchanged'):
            self.save(job, 'completed', 'Metadata '+result+'; publication verified')
        elif result in ('failed', 'timed_out'):
            self.retry(job)
        elif result == 'unsupported':
            self.save(job, 'waiting-settings', 'Waiting for supported Modern tagging settings', 60)
        else:
            self.save(job, 'review', 'Publication could not be verified; review required')


def catalog(path):
    from mylar import db, tagger_native
    from mylar.workflow_store import identifier
    source = Path(path)
    if any(p.is_symlink() for p in (source, *source.parents)):
        raise ValueError('Linked path')
    database = db.DBConnection()
    matches = []
    # Conversion notifications use the same series-directory contract as rescans.
    for series in database.select('SELECT ComicID,ComicLocation,AgeRating FROM comics', []):
        if (not series['ComicLocation'] or Path(series['ComicLocation']) != source.parent
                or '..' in Path(series['ComicLocation']).parts):
            continue
        for table in ('issues', 'annuals'):
            rows = database.select('SELECT IssueID,Location,Status FROM '+table+' WHERE ComicID=?'+
                                   (' AND NOT Deleted' if table == 'annuals' else ''), [series['ComicID']])
            for row in rows:
                if not row['Location']:
                    continue
                location = Path(series['ComicLocation'])/row['Location']
                if location != source or '..' in location.parts:
                    continue
                if row['Status'] != 'Downloaded':
                    continue
                issueid, comicid = identifier(row['IssueID']), identifier(series['ComicID'])
                if not issueid or not comicid:
                    raise ValueError('Invalid catalog identity')
                tagger_native.catalog(issueid)  # Reject duplicate/deleted release ownership.
                arcs = database.select('SELECT StoryArc,ReadingOrder FROM storyarcs WHERE ComicID=? AND IssueID=?', [comicid, issueid])
                matches.append(dict(issueid=issueid, comicid=comicid, agerating=series['AgeRating'],
                                    readingorder=[(r['StoryArc'], r['ReadingOrder']) for r in arcs]))
    if len(matches) > 1:
        raise ValueError('Ambiguous catalog ownership')
    return matches[0] if matches else None


def inspect_archive(path):
    from mylar.tagger_archive import snapshot
    from mylar.tagger_adapter import fingerprint
    archive = snapshot(Path(path))
    return fingerprint(Path(path)), archive.xml is not None


def recover(job):
    from mylar import native_writers, tagger_native, tagger_handoff
    publisher, _ = tagger_native.state(native_writers.owner())
    receipt = publisher.receipt(job['token'])
    if not receipt.exists() and not receipt.is_symlink():
        return None
    if publisher.read(job['token'])['source'] != job['path']:
        return 'conflict'
    result = tagger_handoff.capture(publisher, job['token'])
    return result.metadata if result.valid_for(job['path']) else result.state


def settings():
    import mylar
    config = mylar.CONFIG
    return (config.POST_PROCESSING and config.ENABLE_META and config.CT_TAG_CR
            and not config.CT_TAG_CBL and not config.CBR2CBZ_ONLY
            and getattr(config, 'TAGGER_BACKEND', 'legacy') == 'modern')


def busy():
    return _TAGGING


def tag(job):
    global _TAGGING
    from mylar import tagger_native
    _TAGGING = True
    try:
        result = tagger_native.run(str(Path(job['path']).parent), filename=job['path'], issueid=job['issueid'],
            manualmeta=True, automatic_in_place=True, publication_token=job['token'],
            readingorder=job.get('readingorder'), agerating=job.get('agerating'))
        return result.metadata if result.valid_for(job['path']) else result.state
    finally:
        _TAGGING = False


def poll():
    """One durable job on the existing PP thread; native imports retain priority."""
    import mylar
    from mylar import native_writers
    if not mylar.CONFIG.POST_PROCESSING or mylar.APILOCK or not mylar.PP_QUEUE.empty():
        return
    if not RUN.acquire(blocking=False):
        return
    try:
        Queue(store(), catalog, native_writers.operation, inspect_archive, tag, recover, settings).tick()
    except Exception:
        mylar.logger.warn('Converted comic tagging state unavailable; retained for retry')
    finally:
        RUN.release()


def snapshot(journal=None):
    if __package__:
        from .workflow_store import label, identifier
    else:
        from workflow_store import label, identifier
    journal = journal if journal is not None else store()
    return [dict(name=label(r['path']), phase=r['phase'], reason=label(r['reason']),
                 attempts=r['attempts'], updated_at=r['updated_at'],
                 issueid=identifier(r.get('issueid')), comicid=identifier(r.get('comicid')))
            for r in journal.all('converted_tag', 100)]
