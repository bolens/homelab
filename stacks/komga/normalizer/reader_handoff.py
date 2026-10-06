"""Bound, durable reader notifications dispatched only outside media exclusion."""
from contextlib import closing
from pathlib import Path
import sqlite3
import re
import time

from import_recovery import handoff_read, handoff_save
from publication_guard import current, evidence, remote_unlocked, scope, Unavailable

ACTIONS = frozenset(('library_scan', 'analyze', 'metadata_refresh'))


def idle(worker, authority, targets):
    """Observe every retained native/worker job; new pending work revokes readiness."""
    physical = {(Path(path).stat().st_dev, Path(path).stat().st_ino) for path in targets}
    def conflicts(path):
        if str(path) in targets:
            return True
        if path.is_symlink():
            raise Unavailable('Linked pending reader notification path')
        if path.is_file():
            info = path.lstat()
            return (info.st_dev, info.st_ino) in physical
        return False
    history = list(worker.jobs.glob('*/receipt.json'))
    if len(history) > 4096:
        raise Unavailable('Reader notification worker history exceeds bound')
    for path in history:
        with evidence.regular(path) as stream:
            before = evidence.signature(path.lstat())
            if before[2] > 2*1024*1024:
                raise Unavailable('Reader notification worker receipt exceeds bound')
            job = evidence.decode_json(stream.read(2*1024*1024+1))
            if evidence.signature(path.lstat()) != before:
                raise Unavailable('Reader notification worker receipt changed')
        if (not isinstance(job, dict) or not isinstance(job.get('phase'), str)
                or any(type(job.get(key, False)) is not bool
                       for key in ('mylar_refresh_pending', 'mylar_tag_pending'))):
            raise Unavailable('Malformed reader notification worker history')
        if job['phase'] != 'done' or job.get('mylar_refresh_pending') or job.get('mylar_tag_pending'):
            if not any(job.get(key) is not None for key in ('source', 'destination')):
                raise Unavailable('Pending worker notification has no archive path')
            for key in ('source', 'destination'):
                value = job.get(key)
                if value is None:
                    continue
                if not isinstance(value, str) or not Path(value).is_absolute() or '..' in Path(value).parts:
                    raise Unavailable('Unbound pending worker notification path')
                if conflicts(Path(value)):
                    raise Unavailable('Reader notification archive has pending worker work')
    database = authority.database
    before = evidence.signature(database.lstat())
    with closing(sqlite3.connect(database.as_uri()+'?mode=ro', uri=True)) as db:
        if db.execute("SELECT count(*) FROM records WHERE kind IN ('converted_tag','library_repair')").fetchone()[0] > 4096:
            raise Unavailable('Reader notification native history exceeds bound')
        rows = db.execute("SELECT value FROM records WHERE kind IN ('converted_tag','library_repair')").fetchall()
    for (raw,) in rows:
        job = evidence.decode_json(raw.encode())
        if not isinstance(job, dict) or not isinstance(job.get('phase'), str):
            raise Unavailable('Malformed native reader notification history')
        if job['phase'] != 'completed':
            value = job.get('path')
            if not isinstance(value, str) or not Path(value).is_absolute() or '..' in Path(value).parts:
                raise Unavailable('Unbound pending native notification path')
            if conflicts(authority.mapped(value)):
                raise Unavailable('Reader notification archive has pending native work')
    if evidence.signature(database.lstat()) != before:
        raise Unavailable('Reader notification native work changed during observation')


def proofs(worker, bindings):
    authority = current(worker)
    if not isinstance(bindings, list) or not 1 <= len(bindings) <= 4000:
        raise Unavailable('Reader notification requires bounded current owner evidence')
    targets = {row.get('target') for row in bindings if isinstance(row, dict) and isinstance(row.get('target'), str)}
    for row in bindings:
        if not isinstance(row, dict) or set(row) != {'source', 'target', 'match'}:
            raise Unavailable('Invalid reader notification binding')
        for key in ('source', 'target'):
            path = Path(row[key])
            if (not path.is_absolute() or '..' in path.parts
                    or not any(path.is_relative_to(root) for root in worker.roots)
                    or any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file()):
                raise Unavailable('Unsafe reader notification archive')
        target = Path(row['target'])
        if not any(target.is_relative_to(root) for root in worker.roots):
            raise Unavailable('Reader notification target is outside library')
    idle(worker, authority, targets)
    values = [authority.confirmation_check(Path(row['source']), Path(row['target']), row['match'])
              for row in bindings]
    idle(worker, authority, targets)
    return dict(census=authority.admission()[0], bindings=values)


def queue(worker, action, bindings, *, folder=None, book_id=None):
    """Prepare under owned Writer; never infer publication from reader acknowledgement."""
    if not isinstance(bindings, list) or not 1 <= len(bindings) <= 4000:
        raise Unavailable('Reader notification requires bounded owner bindings')
    if action not in ACTIONS:
        raise Unavailable('Unsupported reader notification')
    if action == 'library_scan':
        folder = Path(folder)
        if (not folder.is_absolute() or '..' in folder.parts or not folder.is_dir()
                or any(p.is_symlink() for p in (folder, *folder.parents))
                or any(not Path(row['target']).is_relative_to(folder) for row in bindings)):
            raise Unavailable('Reader scan does not cover bound targets')
        book_id = None
    elif not isinstance(book_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', book_id):
        raise Unavailable('Invalid reader book identity')
    else:
        folder = None
    proof = proofs(worker, bindings)
    plan = dict(version=1, action=action, folder=str(folder) if folder is not None else None,
                book_id=book_id, bindings=bindings, proof=proof)
    token = evidence.canonical_digest(plan)
    root = worker.state/'reader-handoffs'
    root.mkdir(exist_ok=True, mode=0o700)
    path = root/(token+'.json')
    history = list(root.glob('*.json'))
    if len(history) > 4096 or (not path.exists() and len(history) >= 4096):
        raise Unavailable('Reader notification retention requires review')
    if not path.exists():
        for previous in history:
            old, _ = handoff_read(previous)
            validate(old, previous.stem)
            if (not isinstance(old, dict) or old.get('phase') not in ('prepared', 'dispatching', 'complete')):
                raise Unavailable('Malformed reader notification history')
            if (old['phase'] == 'dispatching' and old.get('action') == action
                    and old.get('folder') == plan['folder'] and old.get('book_id') == book_id):
                raise Unavailable('Uncertain reader notification requires review')
        handoff_save(path, dict(plan, phase='prepared', prepared_at=time.time()))
        return None
    old, _ = handoff_read(path)
    validate(old, token)
    if not evidence.same_json({key:old.get(key) for key in plan}, plan):
        raise Unavailable('Reader notification predecessor changed')
    return old.get('result') if old.get('phase') == 'complete' else None


def route(worker, record):
    """Resolve reader identities through fresh read-only API observations."""
    from normalize import api_path
    if record['action'] == 'library_scan':
        libraries = worker.reader.call('/api/v1/libraries')
        if not isinstance(libraries, list) or len(libraries) > 1024:
            raise Unavailable('Reader library observation exceeds bound')
        matches = []
        for row in libraries:
            if not isinstance(row, dict) or not isinstance(row.get('root'), str):
                raise Unavailable('Malformed reader library observation')
            root = api_path(row['root'])
            if not root.is_absolute() or '..' in root.parts or root == Path('/'):
                raise Unavailable('Unsafe reader library root')
            if Path(record['folder']).is_relative_to(root):
                matches.append(str(row.get('id')))
        if len(matches) != 1 or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', matches[0]):
            raise Unavailable('Reader scan has no unique library')
        return '/api/v1/libraries/'+matches[0]+'/scan'
    book = worker.reader.call('/api/v1/books/'+record['book_id'])
    targets = {str(Path(row['target'])) for row in record['bindings']}
    if (not isinstance(book, dict) or str(book.get('id')) != record['book_id']
            or str(api_path(book.get('url', ''))) not in targets or len(targets) != 1):
        raise Unavailable('Reader book no longer names the bound archive')
    return '/api/v1/books/'+record['book_id']+'/analyze'


def validate(record, token):
    keys = {'version', 'action', 'folder', 'book_id', 'bindings', 'proof', 'phase', 'prepared_at'}
    phase = record.get('phase') if isinstance(record, dict) else None
    if phase in ('dispatching', 'complete'):
        keys |= {'endpoint', 'dispatched_at'}
    if phase == 'complete':
        keys |= {'completed_at', 'result'}
    if (not isinstance(record, dict) or set(record) != keys
            or type(record.get('version')) is not int or record['version'] != 1
            or record.get('action') not in ACTIONS or phase not in ('prepared', 'dispatching', 'complete')
            or not isinstance(record.get('proof'), dict) or set(record['proof']) != {'census', 'bindings'}
            or not isinstance(record.get('bindings'), list) or not 1 <= len(record['bindings']) <= 4000
            or any(type(record.get(name)) not in (float, int) or record[name] < 0
                   for name in ('prepared_at', 'dispatched_at', 'completed_at') if name in record)
            or (phase == 'complete' and not evidence.same_json(record['result'], {'acknowledged':True}))):
        raise Unavailable('Malformed reader notification plan')
    if record['action'] == 'library_scan':
        if (not isinstance(record['folder'], str) or not Path(record['folder']).is_absolute()
                or '..' in Path(record['folder']).parts or record['book_id'] is not None):
            raise Unavailable('Malformed reader library notification')
    elif (record['folder'] is not None or not isinstance(record['book_id'], str)
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', record['book_id'])):
        raise Unavailable('Malformed reader book notification')
    for row in record['bindings']:
        if (not isinstance(row, dict) or set(row) != {'source', 'target', 'match'}
                or any(not isinstance(row.get(key), str) for key in ('source', 'target'))
                or not isinstance(row.get('match'), dict) or set(row['match']) != {'issueid', 'comicid'}
                or any(not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]{0,15}', value)
                       for value in row['match'].values())):
            raise Unavailable('Malformed reader owner binding')
    plan_keys = ('version', 'action', 'folder', 'book_id', 'bindings', 'proof')
    if evidence.canonical_digest({key:record[key] for key in plan_keys}) != token:
        raise Unavailable('Reader notification immutable plan changed')


def dispatch(worker):
    """Record attempts before HTTP; retain uncertain outcomes without automatic replay."""
    from media_writer import Writer, Busy
    from writer_cycle import bind_state
    remote_unlocked(worker)
    root = worker.state/'reader-handoffs'
    if not root.exists():
        return 0
    history = sorted(root.glob('*.json'))
    if len(history) > 4096:
        raise Unavailable('Reader notification retention requires review')
    completed = 0
    for path in history:
        old, _ = handoff_read(path)
        if not isinstance(old, dict):
            raise Unavailable('Malformed reader notification')
        validate(old, path.stem)
        if old.get('phase') != 'prepared':
            continue
        writer = Writer(worker.config['writer_state'], create=False)
        try:
            with writer.hold(allow_pending=True, timeout=0), scope(worker, writer):
                bind_state(writer, worker)
                if writer.fenced():
                    raise Unavailable('Reader notification waits for publication completion')
                if not evidence.same_json(proofs(worker, old['bindings']), old['proof']):
                    raise Unavailable('Reader notification source or authority changed')
            endpoint = route(worker, old)
            with writer.hold(allow_pending=True, timeout=0), scope(worker, writer):
                bind_state(writer, worker)
                if writer.fenced():
                    raise Unavailable('Reader notification waits for publication completion')
                record, signature = handoff_read(path)
                if (not evidence.same_json(record, old)
                        or not evidence.same_json(proofs(worker, old['bindings']), old['proof'])):
                    raise Unavailable('Reader notification changed before request')
                attempt = dict(old, phase='dispatching', endpoint=endpoint, dispatched_at=time.time())
                handoff_save(path, attempt, expected=(record, signature))
            remote_unlocked(worker)
            worker.reader.call(endpoint, {})
            if route(worker, old) != endpoint:
                raise Unavailable('Reader notification target changed after request')
            with writer.hold(allow_pending=True, timeout=0), scope(worker, writer):
                bind_state(writer, worker)
                if writer.fenced():
                    raise Unavailable('Reader notification waits for publication completion')
                record, signature = handoff_read(path)
                if (not evidence.same_json(record, attempt)
                        or not evidence.same_json(proofs(worker, old['bindings']), old['proof'])):
                    raise Unavailable('Reader notification changed after request')
                handoff_save(path, dict(attempt, phase='complete', completed_at=time.time(),
                    result={'acknowledged':True}), expected=(record, signature))
            completed += 1
        except (Busy, Unavailable, OSError, ValueError, KeyError, TypeError, RuntimeError):
            # Prepared requests may be retried only before side effects; once
            # dispatching, even a lost successful reply remains operator review.
            continue
    return completed
