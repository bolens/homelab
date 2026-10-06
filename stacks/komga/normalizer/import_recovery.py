"""One durable, source-preserving submission per matched download."""
from contextlib import closing
import sqlite3
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import stat
import time
import uuid

from normalize import digest, identity, save, sync_directory

MAX_HANDOFF = 16 * 1024**2


def handoff_read(path):
    from publication_guard import evidence, Unavailable
    path = Path(path)
    with evidence.regular(path) as stream:
        before = evidence.signature(os.fstat(stream.fileno()))
        if (before[6] != os.geteuid() or before[8] != 1
                or stat.S_IMODE(before[5]) != 0o600 or not 0 < before[2] <= MAX_HANDOFF):
            raise Unavailable('Unsafe private import handoff')
        raw = stream.read(MAX_HANDOFF+1)
        if evidence.signature(path.lstat()) != before or len(raw) != before[2]:
            raise Unavailable('Import handoff changed during read')
    return evidence.decode_json(raw), before


def handoff_save(path, record, *, expected=None):
    from publication_guard import evidence, Unavailable
    raw = evidence.compact(record)
    if not 0 < len(raw) <= MAX_HANDOFF:
        raise Unavailable('Import handoff exceeds bounds')
    if any(p.is_symlink() for p in (path.parent,*path.parents)):
        raise Unavailable('Linked import handoff state')
    temporary = path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    fd = os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        if expected is None:
            os.link(temporary,path)  # Never replace a prior attempt or proof.
        else:
            current, signature = handoff_read(path)
            if not evidence.same_json(current,expected[0]) or signature != expected[1]:
                raise Unavailable('Import handoff changed before commit')
            os.replace(temporary,path)
        sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)
        sync_directory(path.parent)


def staging_name(source, issueid, *, pdf=False):
    """Carry the verified catalog choice into native post-processing's filename parser."""
    issueid = str(issueid)
    if not re.fullmatch(r'[1-9][0-9]*', issueid):
        raise ValueError('Invalid recovery issue identity')
    markers = re.findall(r'\[__(\d+)__\]', source.stem)
    if '[__' in re.sub(r'\[__\d+__\]', '', source.stem) or (markers and markers != [issueid]):
        raise ValueError('Conflicting recovery filename identity')
    stem = source.stem if markers else source.stem + ' [__' + issueid + '__]'
    return stem + ('.cbz' if pdf else source.suffix)


def issue_state(database, match):
    args = (match['issueid'], match['comicid'])
    if database.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='annuals'").fetchone():
        rows = database.execute('SELECT Status,Location,ComicID,Deleted FROM annuals WHERE IssueID=?', (match['issueid'],)).fetchall()
        if rows:
            row = rows[0]
            return tuple(row[:2]) if len(rows) == 1 and not row[3] and str(row[2]) == str(match['comicid']) else None
    rows = database.execute('SELECT Status,Location FROM issues WHERE IssueID=? AND ComicID=?', args).fetchall()
    return rows[0] if len(rows) == 1 else None


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
            row = issue_state(db, record['match'])
        if row and row[0] == 'Downloaded' and row[1]:
            return 'import_cleanup', record['match']
        if record['phase'] == 'prepared':
            from publication_guard import import_check, evidence
            current = import_check(maintenance.worker,source,record['match'])
            return ('ready' if evidence.same_json(current,record.get('publication',{}).get('source'))
                    else 'import_review'),record['match']
        kind = ('import_queued' if record['phase'] == 'submitted'
                and time.time() - record['submitted_at'] < 1800 else 'import_review')
        return kind, record['match']
    return None


def submit(maintenance, source, match, explicit=False, expected_identity=None, expected_sha256=None, workflow_command=None, reviewed_source=False):
    from maintenance import scoped_file
    settings = maintenance.settings
    if not explicit and not settings.get('auto_import', False):
        return 'ready'
    cache = Path(settings.get('ddl_cache', ''))
    remote = Path(settings.get('mylar_ddl_cache', ''))
    if not remote.is_absolute() or '..' in remote.parts or cache not in maintenance.roots:
        raise ValueError('Explicit shared cache mapping required')
    pdf = source.suffix.casefold() == '.pdf' and maintenance.worker.pdf_policy['enabled']
    if source.suffix.casefold() not in ('.cbz', '.cbr') and not pdf:
        return 'import_unsupported'
    if not scoped_file(source, maintenance.roots):
        raise ValueError('Unsafe import source')
    before = identity(source)
    checksum = digest(source)
    if ((expected_identity is not None and before != expected_identity)
            or (expected_sha256 is not None and checksum != expected_sha256)):
        raise RuntimeError('Confirmed source changed; original retained')
    from publication_guard import import_check
    import_check(maintenance.worker, source, match)
    key = hashlib.sha256(os.fsencode(source) + checksum.encode() + (workflow_command or '').encode()).hexdigest()
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
        if (record.get('source') == str(source) or record.get('match', {}).get('issueid') == match.get('issueid')) and not (explicit and workflow_command and reviewed_source):
            return 'import_review'
    if getattr(maintenance, 'import_submitted', False) or not maintenance.idle():
        return 'ready'
    # Keep the original in place. Mylar can move/tag only this verified copy.
    prepared_source = source
    if pdf:
        from pdf_conversion import derivative
        prepared_source = derivative(maintenance.worker, source)
    if shutil.disk_usage(cache).free < prepared_source.stat().st_size * 2 + 128 * 1024**2:
        raise RuntimeError('Insufficient recovery storage')
    stage = cache / ('.mylar-recovery-' + key)
    stage.mkdir(mode=0o700)  # Existing/orphaned staging requires review, never reuse.
    try:
        target = stage / staging_name(source, match['issueid'], pdf=pdf)
    except ValueError:
        stage.rmdir()
        return 'import_review'
    try:
        if pdf:
            maintenance.worker.convert_tool('comic-to-cbz', '--apply', '--output', target, source)
        else:
            shutil.copyfile(source, target)
        with target.open('rb') as stream:
            os.fsync(stream.fileno())
        sync_directory(stage)
        if identity(source) != before or (not pdf and digest(target) != checksum) or digest(source) != checksum:
            raise RuntimeError('Recovery copy changed; originals retained')
        if pdf and maintenance.info(source) != maintenance.info(target):
            raise RuntimeError('PDF import pages changed; original retained')
        import_check(maintenance.worker, source, match)
        import_check(maintenance.worker, target, match)
    except Exception:
        # This newly owned stage has no receipt or external submission yet.
        target.unlink(missing_ok=True)
        stage.rmdir()
        raise
    if not maintenance.idle():
        target.unlink()
        stage.rmdir()
        return 'ready'
    database = Path(maintenance.worker.config['mylar'].get('config_dir', '/mylar')) / 'mylar.db'
    with closing(sqlite3.connect('file:' + str(database) + '?mode=ro', uri=True)) as db:
        current = issue_state(db, match)
    if not current or current[0] in ('Downloaded', 'Archived'):
        target.unlink()
        stage.rmdir()
        return 'import_review'
    # Recompute rather than use the earlier result as publication permission.
    source_proof = import_check(maintenance.worker, source, match)
    stage_proof = import_check(maintenance.worker, target, match)
    record = {'source': str(source), 'identity': before, 'sha256': checksum, 'stage': str(target),
              'match': match, 'workflow_command':workflow_command, 'phase': 'unconfirmed', 'submitted_at': time.time()}
    maintenance.import_attempts = None
    if maintenance.worker.config.get('writer_state') is not None:
        if workflow_command is not None:
            raise ValueError('Guided handoff requires durable claim dependency')
        record.pop('submitted_at')
        record.update(phase='prepared',prepared_at=time.time(),remote_folder=str(remote/stage.name),
                      publication=dict(version=1,source=source_proof,stage=stage_proof))
        handoff_save(receipt,record)
        maintenance.import_submitted = True
        return 'ready'  # Prepared is never acknowledged as queued.
    save(receipt, record)  # Persist before the potentially accepted network request.
    maintenance.import_submitted = True
    try:
        command = {'workflow_command': workflow_command} if workflow_command is not None else {}
        maintenance.mylar('forceProcess', nzb_name=target.name,
                          nzb_folder=str(remote / stage.name), ddl='True', **match, **command)
    except Exception:
        return 'import_review'
    record['phase'] = 'submitted'
    save(receipt, record)
    return 'import_queued'


def dispatch_prepared(maintenance):
    """One durable attempt after complete cycle/fence clearance, outside HTTP lock."""
    from maintenance import scoped_file
    from media_writer import Writer, Busy
    from publication_guard import scope, evidence, Unavailable, remote_unlocked
    from writer_cycle import bind_state
    worker = maintenance.worker
    remote_unlocked(worker)
    root = worker.config.get('writer_state')
    if root is None:return 0
    receipts = maintenance.state/'imports'
    if not receipts.exists():return 0
    if maintenance.state != worker.state/'maintenance':
        raise Unavailable('Import handoff belongs to foreign worker state')
    paths = sorted(receipts.glob('*.json'))
    if len(paths) > 4096:raise Unavailable('Import handoff count exceeds bounds')
    writer = Writer(root,create=False)
    for path in paths:
        # Legacy attempts and uncertain requests remain retained, never replayed.
        try:record,_ = handoff_read(path)
        except (Unavailable,OSError,ValueError,TypeError):continue
        if not isinstance(record,dict):continue
        if record.get('phase') != 'prepared':continue
        try:
            health = maintenance.mylar('getHealth')
            protocol = health.get('workflow',{})
            if (protocol.get('valid') is not True or type(protocol.get('publication_handoff')) is not int
                    or protocol['publication_handoff'] != 1):return 0
            queue = health['queues'].get('POST-PROCESS-QUEUE',{})
            if not queue.get('alive') or queue.get('size') != 0 or health['processing']:return 0
            with writer.hold(timeout=0),scope(worker,writer) as authority:
                bind_state(writer,worker)
                record, signature = handoff_read(path)
                fields = {'source','identity','sha256','stage','match','workflow_command','phase',
                          'prepared_at','remote_folder','publication'}
                if (not isinstance(record,dict) or set(record) != fields or record['phase'] != 'prepared'
                        or record['workflow_command'] is not None or not isinstance(record['prepared_at'],(int,float))
                        or type(record['prepared_at']) is bool):
                    raise Unavailable('Unsupported import handoff receipt')
                source,target = Path(record['source']),Path(record['stage'])
                cache = Path(maintenance.settings['ddl_cache'])
                remote = Path(maintenance.settings['mylar_ddl_cache'])
                key = hashlib.sha256(os.fsencode(source)+record['sha256'].encode()).hexdigest()
                expected_stage = cache/('.mylar-recovery-'+key)
                if (path.name != key+'.json' or not scoped_file(source,maintenance.roots)
                        or cache not in maintenance.roots or not remote.is_absolute() or '..' in remote.parts
                        or target != expected_stage/staging_name(source,record['match']['issueid'])
                        or not scoped_file(target,[cache]) or record['remote_folder'] != str(remote/expected_stage.name)
                        or identity(source) != record['identity'] or digest(source) != record['sha256']):
                    raise Unavailable('Import handoff scope or source changed')
                fresh = dict(version=1,source=authority.import_check(source,record['match']),
                             stage=authority.import_check(target,record['match']))
                if not evidence.same_json(fresh,record['publication']):
                    raise Unavailable('Prepared import publication evidence changed')
                with closing(sqlite3.connect(authority.catalog.as_uri()+'?mode=ro&immutable=1',uri=True)) as database:
                    current = issue_state(database,record['match'])
                if not current or current[0] in ('Downloaded','Archived'):
                    raise Unavailable('Prepared import is no longer eligible')
                proof = fresh['stage']
                command = dict(version=1,token=key,source_sha256=proof['inventory']['source_sha256'],
                    payload=proof['inventory']['payload'],owner=proof['authority']['owner'],
                    census=proof['authority']['census'])
                attempted = dict(record,phase='dispatching',submitted_at=time.time())
                handoff_save(path,attempted,expected=(record,signature))
            # Native independently checks its actual stage, owner and census.
            try:
                maintenance.mylar('forceProcess',nzb_name=target.name,nzb_folder=record['remote_folder'],
                    ddl='True',publication_handoff=json.dumps(command),**record['match'])
            except Exception:
                return 0  # Dispatching is durable uncertain review, never auto-retry.
            with writer.hold(timeout=0),scope(worker,writer) as authority:
                bind_state(writer,worker)
                old, signature = handoff_read(path)
                if (not evidence.same_json(old,attempted)
                        or not evidence.same_json(authority.import_check(source,record['match']),fresh['source'])):
                    raise Unavailable('Import handoff changed before queued acknowledgement')
                handoff_save(path,dict(attempted,phase='submitted'),expected=(old,signature))
            maintenance.import_attempts = None
            return 1
        except (Busy,Unavailable,OSError,ValueError,TypeError,KeyError,sqlite3.Error):
            return 0  # Keep original receipt/proof and every original source.
    return 0
