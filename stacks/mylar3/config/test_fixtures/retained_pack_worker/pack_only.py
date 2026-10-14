"""Explicit one-capture maintenance pass; no bulk, naming or metadata sweep."""
import re
from media_writer import Writer, Busy
from publication_guard import scope, Unavailable
from writer_cycle import bind_state
from maintenance import Maintenance
from pack_recovery import Packs


def run(worker, pack_id, ddl_id):
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
    with writer.hold(timeout=0), scope(worker, writer):
        pass
    batch = m.prepare(pack_id, ddl_id)
    work = batch.read(worker, 'packWork')
    if (type(work) is not dict or work.get('enabled') is not True
            or type(work.get('packs')) is not list or len(work['packs']) != 1
            or work['packs'][0].get('id') != pack_id
            or work['packs'][0].get('ddl_id') != ddl_id):
        raise Unavailable('Exact enabled selected pack work required')
    with writer.hold(allow_pending=True, timeout=0):
        if writer.fenced():
            raise Busy('Existing normalizer recovery belongs to its owning cycle')
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
    from import_recovery import dispatch_prepared
    from native_handoff import dispatch
    imported = dispatch_prepared(m, imports)
    reported = dispatch(m, reports)
    return {'pack_id': pack_id, 'ddl_id': ddl_id,
            'import_requests': imported, 'maintenance_requests': reported,
            'complete': False}
