"""Selected and recurring ordinary packs; no bulk, naming or metadata sweep."""
import os
import re
import time
from contextlib import ExitStack
from media_writer import Writer, Busy
from publication_guard import scope, Unavailable, RemoteWriterBusy
from writer_cycle import bind_state
from maintenance import Maintenance
from pack_recovery import Packs


_ADMISSION_ATTEMPTS = 241
_RECOVERY_MARKERS = ('normalizer-v1.pending', 'tagger-v2.pending', 'release-v1.pending',
                     'normalizer-state-adoption-v1.pending', 'negative-retirement-v1.pending',
                     'negative-retirement-v1.terminal-pending', 'archive-repair-v1.pending',
                     'archive-repair-v1.terminal-pending')


def _recovery_pending(writer):
    writer.validate_root()
    for name in _RECOVERY_MARKERS:
        try:
            os.lstat(writer.root / name)
        except FileNotFoundError:
            continue
        return True
    return False


def _wait_admission(writer, error, wait, deadline, attempt):
    # Only lock entry or read-only remote preparation probes reach here.
    # Never retry an acquired scope, processing body or dispatch.
    remaining = deadline - time.monotonic()
    if not wait or attempt >= _ADMISSION_ATTEMPTS or remaining <= 0 or _recovery_pending(writer):
        raise error
    time.sleep(min(0.5, remaining))
    if time.monotonic() >= deadline:
        raise error


def run(worker, pack_id, ddl_id, *, admission_wait=0):
    if type(admission_wait) is not int or not 0 <= admission_wait <= 120:
        raise ValueError('Selected pack admission wait requires 0 through 120 seconds')
    if (type(pack_id) is not str or not re.fullmatch('[a-f0-9]{64}', pack_id)
            or type(ddl_id) is not str or not re.fullmatch('[0-9]{1,32}', ddl_id)):
        raise ValueError('Exact pack capture and DDL identity required')
    if not worker.config.get('writer_state'):
        raise Unavailable('Pack-only pass requires existing shared writer')
    if not worker.config.get('maintenance', {}).get('pack_import', False):
        raise Unavailable('Configured pack imports disabled')
    m = Maintenance(worker)
    m.import_submitted = False
    m.import_catalog = None
    m.import_attempts = None
    m._pack_only_imports = set()
    m._pack_only_native = set()
    m._pack_only_existing_catalog = True
    writer = Writer(worker.config['writer_state'], create=False)
    deadline = time.monotonic() + admission_wait
    for attempt in range(1, _ADMISSION_ATTEMPTS + 1):
        if admission_wait and _recovery_pending(writer):
            raise Busy('Existing writer recovery requires its owning cycle')
        with ExitStack() as probe:
            try:
                probe.enter_context(writer.hold(timeout=0))
            except Busy as error:
                _wait_admission(writer, error, admission_wait, deadline, attempt)
                continue
            with scope(worker, writer):
                pass
        if admission_wait and _recovery_pending(writer):
            raise Busy('Existing writer recovery requires its owning cycle')
        try:
            batch = m.prepare(pack_id, ddl_id)
        except RemoteWriterBusy as error:
            _wait_admission(writer, error, admission_wait, deadline, attempt)
            continue
        work = batch.read(worker, 'packWork')
        if (type(work) is not dict or work.get('enabled') is not True
                or type(work.get('packs')) is not list or len(work['packs']) != 1
                or work['packs'][0].get('id') != pack_id
                or work['packs'][0].get('ddl_id') != ddl_id):
            raise Unavailable('Exact enabled selected pack work required')
        with ExitStack() as admitted:
            try:
                admitted.enter_context(writer.hold(allow_pending=True, timeout=0))
            except Busy as error:
                _wait_admission(writer, error, admission_wait, deadline, attempt)
                continue
            if writer.fenced() or (admission_wait and _recovery_pending(writer)):
                raise Busy('Existing writer recovery belongs to its owning cycle')
            with scope(worker, writer, native_batch=batch):
                bind_state(writer, worker)
                if not m.idle():
                    raise Unavailable('Native post-processing is active')
                writer.mark_pending()
                Packs(m).cycle(pack_id, ddl_id, scan=False)
                imports = tuple(sorted(m._pack_only_imports))
                reports = tuple(sorted(m._pack_only_native))
                bind_state(writer, worker)
            writer.clear_pending()
        break
    from import_recovery import dispatch_prepared
    from native_handoff import dispatch
    imported = dispatch_prepared(m, imports)
    reported = dispatch(m, reports)
    return {'pack_id': pack_id, 'ddl_id': ddl_id,
            'import_requests': imported, 'maintenance_requests': reported,
            'complete': False}



def discover(worker):
    """Bounded native work discovery, followed by fresh selected admission."""
    settings = worker.config.get('maintenance', {})
    if (not worker.config.get('writer_state') or settings.get('pack_import') is not True
            or settings.get('auto_import') is not True):
        raise Unavailable('Configured recurring pack imports disabled')
    maintenance = Maintenance(worker)
    writer = Writer(worker.config['writer_state'], create=False)
    # Refuse original recovery before remote work. No outer lock survives APIs.
    with writer.hold(timeout=0), scope(worker, writer):
        bind_state(writer, worker)
    batch = maintenance.prepare(packs_only=True)
    with writer.hold(timeout=0), scope(worker, writer, native_batch=batch):
        bind_state(writer, worker)
        if not maintenance.idle():
            return None
        work = batch.read(worker, 'packWork')
        if (type(work) is not dict or work.get('enabled') is not True
                or type(work.get('packs')) is not list or len(work['packs']) > 50):
            raise Unavailable('Enabled bounded native pack work required')
        selected = []
        identities = set()
        for record in work['packs']:
            if (type(record) is not dict or type(record.get('id')) is not str
                    or not re.fullmatch('[a-f0-9]{64}', record['id'])
                    or type(record.get('ddl_id')) is not str
                    or not re.fullmatch('[0-9]{1,32}', record['ddl_id'])
                    or record.get('phase') not in ('discovered', 'review', 'confirmed')
                    or record['id'] in identities):
                raise Unavailable('Exact current native pack identities required')
            identities.add(record['id'])
            selected.append((record['id'], record['ddl_id']))
        bind_state(writer, worker)
    return selected


def tick(worker, stopping=lambda: False):
    """Visit at most the native fifty-record page; never a general cycle."""
    selected = discover(worker)
    if selected is None:
        return None
    imports = reports = captures = 0
    for pack_id, ddl_id in selected:
        if stopping():
            break
        result = run(worker, pack_id, ddl_id)
        captures += 1
        imports += result['import_requests']
        reports += result['maintenance_requests']
        # Let ordinary native post-processing settle before another submission.
        if result['import_requests']:
            break
    return dict(captures=captures, import_requests=imports,
                maintenance_requests=reports, complete=False)


def _interval(config):
    value = config.get('poll_seconds', 60)
    if type(value) is not int or not 30 <= value <= 3600:
        raise ValueError('Recurring pack poll requires 30 through 3600 seconds')
    return value


def check_health(config, state):
    import json
    import time
    interval = _interval(config)
    status = json.loads((state / 'status.json').read_text())
    if (not 0 <= time.time() - (state / 'heartbeat').stat().st_mtime <= 90
            or status.get('mode') != 'packs-only' or status.get('errors')
            or status.get('state') not in ('starting', 'waiting', 'checked')
            or not 0 <= time.time() - status['checked_at'] <= max(180, interval * 3)):
        raise Unavailable('Recurring pack worker health unavailable')


def serve(worker, *, once=False):
    """Idle between guarded passes; finish the current pass on shutdown."""
    import json
    import os
    import signal
    import threading
    import time
    from normalize import save
    interval = _interval(worker.config)
    settings = worker.config.get('maintenance', {})
    if settings.get('pack_import') is not True or settings.get('auto_import') is not True:
        raise Unavailable('Configured recurring pack imports disabled')
    stop = threading.Event()
    previous = {}
    status_path = worker.state / 'status.json'
    def request_stop(signum, frame):
        stop.set()
    def heartbeat():
        while not stop.wait(20):
            (worker.state / 'heartbeat').touch()
    for name in (signal.SIGTERM, signal.SIGINT):
        previous[name] = signal.signal(name, request_stop)
    (worker.state / 'heartbeat').touch()
    pulse = threading.Thread(target=heartbeat, daemon=True)
    pulse.start()
    status = dict(mode='packs-only', state='starting', checked_at=0, errors=[])
    absent = object()
    previous_status_context = getattr(worker, '_pack_recurring_status', absent)
    try:
        worker._pack_recurring_status = True
        while not stop.is_set():
            old_errors = status.get('errors', [])
            try:
                result = tick(worker, stop.is_set)
                status = dict(mode='packs-only', state='waiting' if result is None else 'checked',
                              checked_at=status['checked_at'] if result is None else time.time(),
                              observed_at=time.time(), errors=old_errors if result is None else [],
                              **({} if result is None else result))
            except Busy:
                writer = Writer(worker.config['writer_state'], create=False)
                pending = (writer.fenced() or writer.fenced(tagger=True) or writer.fenced(release=True)
                           or os.path.lexists(writer.root / 'normalizer-state-adoption-v1.pending'))
                status = dict(mode='packs-only', state='held' if pending else 'waiting',
                              checked_at=status['checked_at'], observed_at=time.time(),
                              errors=['Pack recovery pending'] if pending else old_errors)
            except Exception:
                status = dict(mode='packs-only', state='held', checked_at=time.time(),
                              errors=['Guarded pack pass requires review'])
            save(status_path, status)
            print(json.dumps(status), flush=True)
            if once:
                if status['errors'] or status['state'] != 'checked':
                    raise Unavailable('Guarded pack pass requires review')
                return status
            stop.wait(interval)
    finally:
        if previous_status_context is absent:
            del worker._pack_recurring_status
        else:
            worker._pack_recurring_status = previous_status_context
        stop.set()
        pulse.join(timeout=1)
        for name, handler in previous.items():
            signal.signal(name, handler)
        save(status_path, dict(status, state='stopped', checked_at=time.time()))
