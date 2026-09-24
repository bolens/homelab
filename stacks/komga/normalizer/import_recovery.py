"""One durable, source-preserving submission per matched download."""
from contextlib import closing
import sqlite3
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

from normalize import digest, identity, save, sync_directory



def previous_attempt(maintenance, source):
    """Keep attempted imports visible even after matching stops returning Downloaded issues."""
    if getattr(maintenance, 'import_attempts', None) is None:
        maintenance.import_attempts = [json.loads(p.read_text())
                                       for p in (maintenance.state / 'imports').glob('*.json')]
    for record in maintenance.import_attempts:
        if record['source'] != str(source) or record.get('identity') != identity(source):
            continue
        directory = Path(maintenance.worker.config['mylar'].get('config_dir', '/mylar'))
        with closing(sqlite3.connect('file:' + str(directory / 'mylar.db') + '?mode=ro', uri=True)) as db:
            row = db.execute('SELECT Status,Location FROM issues WHERE IssueID=? AND ComicID=?',
                             (record['match']['issueid'], record['match']['comicid'])).fetchone()
        if row and row[0] == 'Downloaded' and row[1]:
            return 'import_cleanup', record['match']
        kind = ('import_queued' if record['phase'] == 'submitted'
                and time.time() - record['submitted_at'] < 1800 else 'import_review')
        return kind, record['match']
    return None


def submit(maintenance, source, match, explicit=False, expected_identity=None, expected_sha256=None, workflow_command=None):
    from maintenance import scoped_file
    settings = maintenance.settings
    if not explicit and not settings.get('auto_import', False):
        return 'ready'
    cache = Path(settings.get('ddl_cache', ''))
    remote = Path(settings.get('mylar_ddl_cache', ''))
    if not remote.is_absolute() or '..' in remote.parts or cache not in maintenance.roots:
        raise ValueError('Explicit shared cache mapping required')
    if source.suffix.casefold() not in ('.cbz', '.cbr'):
        return 'import_unsupported'
    if not scoped_file(source, maintenance.roots):
        raise ValueError('Unsafe import source')
    before = identity(source)
    checksum = digest(source)
    if ((expected_identity is not None and before != expected_identity)
            or (expected_sha256 is not None and checksum != expected_sha256)):
        raise RuntimeError('Confirmed source changed; original retained')
    key = hashlib.sha256(os.fsencode(source) + checksum.encode()).hexdigest()
    receipts = maintenance.state / 'imports'
    receipts.mkdir(exist_ok=True, mode=0o700)
    receipt = receipts / (key + '.json')
    if receipt.exists():
        record = json.loads(receipt.read_text())
        if record.get('match') != match:
            return 'import_review'
        if record['phase'] == 'submitted' and time.time() - record['submitted_at'] < 1800:
            return 'import_queued'
        return 'import_review'
    # A different filename for the same issue must not bypass an uncertain attempt.
    for previous in receipts.glob('*.json'):
        record = json.loads(previous.read_text())
        if record.get('match', {}).get('issueid') == match.get('issueid'):
            return 'import_review'
    if getattr(maintenance, 'import_submitted', False) or not maintenance.idle():
        return 'ready'
    # Keep the original in place. Mylar can move/tag only this verified copy.
    stage = cache / ('.mylar-recovery-' + key)
    stage.mkdir(mode=0o700)  # Existing/orphaned staging requires review, never reuse.
    target = stage / source.name
    if shutil.disk_usage(cache).free < source.stat().st_size * 2 + 128 * 1024**2:
        stage.rmdir()
        raise RuntimeError('Insufficient recovery storage')
    shutil.copyfile(source, target)
    with target.open('rb') as stream:
        os.fsync(stream.fileno())
    sync_directory(stage)
    if identity(source) != before or digest(target) != checksum or digest(source) != checksum:
        raise RuntimeError('Recovery copy changed; originals retained')
    if not maintenance.idle():
        target.unlink()
        stage.rmdir()
        return 'ready'
    if explicit:
        database = Path(maintenance.worker.config['mylar'].get('config_dir', '/mylar')) / 'mylar.db'
        with closing(sqlite3.connect('file:' + str(database) + '?mode=ro', uri=True)) as db:
            current = db.execute('SELECT Status FROM issues WHERE IssueID=? AND ComicID=?',
                                 (match['issueid'], match['comicid'])).fetchall()
        if len(current) != 1 or current[0][0] == 'Downloaded':
            target.unlink()
            stage.rmdir()
            return 'import_review'
    record = {'source': str(source), 'identity': before, 'sha256': checksum, 'stage': str(target),
              'match': match, 'phase': 'unconfirmed', 'submitted_at': time.time()}
    maintenance.import_attempts = None
    save(receipt, record)  # Persist before the potentially accepted network request.
    maintenance.import_submitted = True
    try:
        command = {'workflow_command': workflow_command} if workflow_command is not None else {}
        maintenance.mylar('forceProcess', nzb_name=source.name,
                          nzb_folder=str(remote / stage.name), ddl='True', **match, **command)
    except Exception:
        return 'import_review'
    record['phase'] = 'submitted'
    save(receipt, record)
    return 'import_queued'
