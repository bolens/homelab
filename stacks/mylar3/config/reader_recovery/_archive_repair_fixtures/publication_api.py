"""Bounded publication protocol; the native API adapter owns authentication.

No request controls filesystem locations. State paths and library roots come
from the native process configuration. This module never runs media replay.
"""
from contextlib import closing
import json
import os
import sqlite3
import time
from pathlib import Path

if __package__:
    from . import publication_guard as guard
    from .media_writer import Writer
else:
    import publication_guard as guard
    from media_writer import Writer

MAX_REQUEST = 4 * 1024 * 1024
FIELDS = {
    'status': set(),
    'prepare-archive-repair': {'owner','operation_id'},
    'archive-repair-status': {'owner','operation_id'},
    'request-archive-repair-adoption': {'owner','operation_id'},
    'archive-repair-adoption-status': {'owner','operation_id'},
    'prepare-bootstrap': {'epoch', 'backup'},
    'prepare-fresh': {'epoch', 'backup'},
    'initialize-bootstrap': {'token'},
    'recover-bootstrap': {'token', 'mode'},
    'prepare-registration': {'census', 'inventory', 'allowed', 'rejected', 'evidence', 'created'},
    'register': {'token'},
    'recover-registration': {'token', 'mode'},
    'prepare-derivative': {'lineage', 'created'},
    'prepare-lineage': {'request'},
    'adopt-derivative': {'token'},
    'recover-derivative': {'token', 'mode'},
    'prepare-journal': {'kind', 'token'},
    'recover-journal': {'kind', 'token'},
    'prepare-tagging-completion': {'backup'},
    'complete-tagging': {'token'},
    'check': {'owner', 'payload'},
}


def _integer(raw):
    if len(raw) > 20:
        raise guard.Unavailable('Protocol integer exceeds bounds')
    return int(raw)


def _reject_number(_):
    raise guard.Unavailable('Protocol requires finite integers')


def request(raw):
    """Reject ambiguity and unbounded structures before accessing state."""
    if (not isinstance(raw, str) or len(raw) > MAX_REQUEST
            or len(raw.encode('utf-8')) > MAX_REQUEST):
        raise guard.Unavailable('Protocol request exceeds bounds')
    # Reject excessive nesting before the JSON parser allocates recursive data.
    depth, quoted, escaped = 0, False, False
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '[{':
            depth += 1
            if depth > 16:
                raise guard.Unavailable('Protocol nesting exceeds bounds')
        elif char in ']}':
            depth -= 1
    try:
        value = json.loads(raw, object_pairs_hook=guard.object_pairs,
                           parse_int=_integer, parse_float=_reject_number,
                           parse_constant=_reject_number)
    except (ValueError, RecursionError) as error:
        raise guard.Unavailable('Malformed publication request') from error
    stack, count = [value], 0
    while stack:
        item = stack.pop();count += 1
        if count > 65536:
            raise guard.Unavailable('Protocol nodes exceed bounds')
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    if (not isinstance(value, dict) or type(value.get('version')) is not int
            or value['version'] != 1 or not isinstance(value.get('action'), str)
            or value['action'] not in FIELDS):
        raise guard.Unavailable('Unsupported publication protocol')
    action = value['action']
    optional = ({'parent_token'} if action == 'prepare-journal' else
                {'token'} if action == 'status' else set())
    required = FIELDS[action] | {'version', 'action'}
    if not required <= set(value) or set(value) - required - optional:
        raise guard.Unavailable('Unexpected publication request fields')
    for key in ('token', 'parent_token', 'epoch', 'payload'):
        if key in value and not guard.digest_value(value[key]):
            raise guard.Unavailable('Invalid exact protocol token')
    if 'mode' in value and value['mode'] not in ('finish', 'abort'):
        raise guard.Unavailable('Invalid recovery mode')
    if 'kind' in value and value['kind'] not in ('bootstrap', 'registration'):
        raise guard.Unavailable('Invalid journal recovery type')
    if action in ('prepare-bootstrap','prepare-fresh','prepare-tagging-completion'):
        backup = value['backup']
        if (not isinstance(backup, dict)
                or set(backup) != {'manifest_sha256', 'restore_sha256', 'description'}
                or any(not guard.digest_value(backup[key]) for key in ('manifest_sha256', 'restore_sha256'))
                or not isinstance(backup['description'], str)
                or not 1 <= len(backup['description'].encode('utf-8')) <= 1024):
            raise guard.Unavailable('Invalid reviewed backup')
    if action == 'prepare-registration':
        guard.census_value(value['census']);guard.validate(value['inventory'])
        owners = []
        for key in ('allowed', 'rejected'):
            if not isinstance(value[key], list) or not 1 <= len(value[key]) <= 8:
                raise guard.Unavailable('Missing explicit owners')
            owners.extend(guard.canonical_digest(guard.exact_owner(owner)) for owner in value[key])
        evidence = value['evidence']
        if (len(owners) > 8 or len(set(owners)) != len(owners)
                or type(value['created']) is not int or value['created'] < 0
                or not isinstance(evidence, dict) or set(evidence) != {'sha256', 'description'}
                or not guard.digest_value(evidence['sha256'])
                or not isinstance(evidence['description'], str)
                or not 1 <= len(evidence['description'].encode('utf-8')) <= 2048):
            raise guard.Unavailable('Invalid reviewed registration')
    if action in ('prepare-archive-repair','archive-repair-status','request-archive-repair-adoption','archive-repair-adoption-status'):
        guard.exact_owner(value['owner'])
        if not guard.digest_value(value['operation_id']):
            raise guard.Unavailable('Invalid exact archive operation')
    if action == 'check':
        guard.exact_owner(value['owner'])
    if action == 'prepare-derivative':
        if __package__:
            from .publication_derivative import plan_value
        else:
            from publication_derivative import plan_value
        plan_value(value['lineage'])
        if type(value['created']) is not int or value['created']<0:
            raise guard.Unavailable('Exact derivative review time required')
    if action == 'prepare-lineage':
        if __package__:
            from .publication_lineage import validate
        else:
            from publication_lineage import validate
        validate(value['request'])
    return value


class Controller:
    """Trusted native configuration only; construct after request validation."""
    def __init__(self, data_dir, library_roots, *, tool_root=guard.TOOL_ROOT):
        self.root = Path(data_dir).absolute()
        self.database = self.root / 'workflow.sqlite'
        self.native_database = self.root / 'mylar.db'
        self.writer_root = self.root / 'media-writer'
        self.roots = library_roots
        self.tool_root = tool_root

    def observe(self, writer, body):
        return guard.observe_owners(self.native_database, writer, body['allowed'],
                                   self.roots, tool_root=self.tool_root)

    @guard.state_errors
    def dispatch(self, value):
        action = value['action']
        if action == 'status':
            result = guard.authority_status(self.database, self.writer_root)
            if 'token' not in value and os.path.lexists(self.root/'publication-fresh-v1.json'):
                try:
                    if __package__:
                        from . import publication_fresh
                    else:
                        import publication_fresh
                    value=dict(value,token=publication_fresh.prepared_token(self.root))
                except (ValueError,OSError,RuntimeError):
                    result['fresh'] = dict(outcome='unavailable')
            if 'token' in value:
                try:
                    writer = Writer(self.writer_root, create=False)
                    with writer.hold(allow_pending=True, allow_tagger_pending=True,
                                     allow_release_pending=True, timeout=0):
                        result['intent'] = self.receipt(value['token'], writer)
                except (ValueError, OSError, RuntimeError):
                    result['intent'] = dict(token=value['token'], outcome='unavailable')
            return result
        if action in ('request-archive-repair-adoption','archive-repair-adoption-status'):
            if __package__:
                from . import publication_archive_dispatch
            else:
                import publication_archive_dispatch
            writer=Writer(self.writer_root,create=False)
            with writer.hold(timeout=0):
                return publication_archive_dispatch.dispatch(self,writer,value)
        if action in ('prepare-archive-repair','archive-repair-status'):
            if __package__:
                from . import publication_archive_prepare_routes
            else:
                import publication_archive_prepare_routes
            writer=Writer(self.writer_root,create=False)
            with writer.hold(timeout=0):
                return publication_archive_prepare_routes.dispatch(self,writer,value)
        if action == 'prepare-fresh':
            if __package__:
                from . import publication_fresh
            else:
                import publication_fresh
            token=publication_fresh.prepare(self.root,value['backup'],epoch=value['epoch'])
            writer=Writer(self.writer_root,create=False)
            with writer.hold(allow_pending=True,allow_tagger_pending=True,allow_release_pending=True):
                return dict(version=1,action=action,token=token,outcome='prepared',review=self.receipt(token,writer))
        writer = Writer(self.writer_root, create=False)
        with writer.hold(allow_pending=True, allow_tagger_pending=True, allow_release_pending=True):
            return self._dispatch(value, writer)

    def _dispatch(self, value, writer):
        action = value['action']
        result = dict(version=1, action=action)
        if action in ('prepare-tagging-completion','complete-tagging'):
            if __package__:
                from .publication_tagging_recovery import Completion
            else:
                from publication_tagging_recovery import Completion
            recovery=Completion(self,writer)
            token=(recovery.prepare(value['backup']) if action=='prepare-tagging-completion' else value['token'])
            result.update(token=token,outcome='prepared' if action=='prepare-tagging-completion'
                          else recovery.complete(token))
            row=recovery._read(token)
            result['review']=dict(job=row['plan']['job']['token'],phase=row['phase'],
                                  backup={key:row['plan']['backup'][key]
                                          for key in ('manifest_sha256','restore_sha256')})
            return result
        if action in ('prepare-journal', 'recover-journal'):
            cls = (guard.JournalRecovery if value['kind'] == 'bootstrap'
                   else guard.RegistrationJournalRecovery)
            state = cls(self.database, writer)
            if action == 'prepare-journal':
                result['token'] = state.prepare(value['token'], parent_token=value.get('parent_token'))
                result['outcome'] = 'prepared'
            else:
                result['token'] = value['token']
            with state._locked():
                record = state._receipt(result['token']);plan = record['plan']
                result['review'] = dict(action=plan['action'], outcome=record['outcome'],
                    intent=plan[state.TOKEN_FIELD], parent_token=plan['parent'],
                    capture=plan['capture'], restored=plan['restored'])
            if action == 'recover-journal':
                state.commit(value['token'], accepted_token=value['token'])
                result['outcome'] = 'restored-old'
                result['review']['outcome'] = 'recovered'
            return result
        if action == 'check':
            return self._check(value, writer)
        if action == 'prepare-lineage':
            from mylar import native_writers, publication_native
            if __package__:
                from . import publication_lineage, publication_derivative
            else:
                import publication_lineage, publication_derivative
            try:
                with native_writers.operation() as active:
                    publication_derivative.prepared_scope(value['request'])
                    plan=publication_lineage.prepare(active,value['request'])
            except publication_native.Review:
                raise guard.Unavailable('Reviewed lineage preparation requires current-source review') from None
            result.update(lineage=plan,outcome='reviewed',executable=False)
            return result
        if action.endswith('bootstrap'):
            state = guard.RegistryState(self.database, writer)
            if action == 'prepare-bootstrap':
                result.update(token=state.prepare_bootstrap(value['backup'], epoch=value['epoch']),
                              outcome='prepared', epoch=value['epoch'], backup={key:value['backup'][key]
                                  for key in ('manifest_sha256', 'restore_sha256')})
            elif action == 'initialize-bootstrap':
                result.update(token=value['token'], outcome='committed',
                              census=state.initialize(value['token'], accepted_token=value['token']))
            else:
                census = state.recover_bootstrap(value['token'], abort=value['mode'] == 'abort')
                result.update(token=value['token'], outcome='aborted' if census is None else 'committed', census=census)
            result['review'] = self.receipt(result['token'], writer)
            result['outcome'] = result['review']['outcome']
            return result
        state = guard.RegistrationState(self.database, writer)
        if __package__:
            from . import publication_derivative
        else:
            import publication_derivative
        observe = lambda body: (publication_derivative.registration_observe(writer,body)
                                if body.get('version')==2 else self.observe(writer, body))
        if action in ('prepare-derivative','adopt-derivative','recover-derivative'):
            if action=='prepare-derivative':
                from mylar import native_writers, publication_native
                try:
                    with native_writers.operation() as active:
                        token=publication_derivative.prepare(active,value['lineage'],value['created'],self.database)
                except publication_native.Review:
                    raise guard.Unavailable('Reviewed derivative preparation requires current-source review') from None
                result.update(token=token,outcome='prepared')
            else:
                token=value['token']
                with state._session() as db:
                    record=state._record(db,token)
                if record['plan']['body'].get('version')!=2:
                    raise guard.Unavailable('Derivative route requires an exact derivative intent')
                census=(state.register(token,accepted_token=token,observe=observe) if action=='adopt-derivative'
                        else state.recover_registration(token,abort=value['mode']=='abort',observe=observe))
                result.update(token=token,outcome='aborted' if census is None else 'committed',census=census)
            result['review']=self.receipt(token,writer)
            result['outcome']=result['review']['outcome']
            return result
        if action in ('register','recover-registration'):
            with state._session() as db:
                record=state._record(db,value['token'])
            if record['plan']['body'].get('version')!=1:
                raise guard.Unavailable('Ordinary registration route cannot consume a derivative intent')
        if action == 'prepare-registration':
            census, _ = state.snapshot()
            if not guard.same_json(census, value['census']):
                raise guard.Unavailable('Reviewed census changed')
            current = observe(value)
            if current['inventory']['payload'] != value['inventory']['payload']:
                raise guard.Unavailable('Reviewed payload differs from native owner')
            body = dict(version=1, epoch=census['epoch'], prior_revision=census['revision'],
                        inventory=current['inventory'], observed=current['observed'],
                        allowed=value['allowed'], rejected=value['rejected'], evidence=value['evidence'],
                        created=value['created'])
            token = state.prepare_registration(body, observe=observe)
            result.update(token=token, outcome='prepared', census=census,
                          allowed=body['allowed'], rejected=body['rejected'], payload=body['inventory']['payload'],
                          pages=len(body['inventory']['pages']), members=len(body['inventory']['members']),
                          evidence_sha256=body['evidence']['sha256'],
                          source_sha256=[item['source_sha256'] for item in body['observed']])
        else:
            if action == 'register':
                census = state.register(value['token'], accepted_token=value['token'], observe=observe)
            else:
                census = state.recover_registration(value['token'], abort=value['mode'] == 'abort', observe=observe)
            result.update(token=value['token'], outcome='aborted' if census is None else 'committed', census=census)
        result['review'] = self.receipt(value['token'] if 'token' in value else token, writer)
        result['outcome'] = result['review']['outcome']
        return result

    @guard.state_errors
    def receipt(self, token, writer):
        # Caller owns raw Writer before workflow LOCK. Status never opens a
        # write transaction or calls ordinary Store/native operation recovery.
        if __package__:
            from .workflow_store import LOCK
        else:
            from workflow_store import LOCK
        if not getattr(writer.local[1], 'depth', 0):
            raise guard.Unavailable('Raw Writer required before intent read')
        with LOCK:
            stamp = guard.database_stamp(self.database)
            deadline = time.monotonic() + guard.TIMEOUT
            with closing(sqlite3.connect(self.database.as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
                db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
                db.execute('BEGIN')
                if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                    raise guard.Unavailable('Unreadable intent database')
                guard.workflow_schema(db)
                row = db.execute("SELECT value FROM records WHERE kind='publication_intent' AND key=? "
                    "AND typeof(value)='text' AND length(CAST(value AS BLOB))<=?",
                    (token, guard.REGISTRATION_BYTES)).fetchone()
                if row is None:
                    raise guard.Unavailable('Missing exact intent')
                record = guard.decode_json(row[0]);plan = guard.intent_record(token, record)
                if (plan['binding']['database_identity'] != stamp[:2]
                        or plan['binding']['writer_identity'] != guard.writer_identity(writer)):
                    raise guard.Unavailable('Foreign intent state binding')
                db.rollback()
            if guard.database_stamp(self.database) != stamp:
                raise guard.Unavailable('Intent database changed')
        result = dict(token=token, action=plan['action'], outcome=record['outcome'], accepted=record['accepted'],
                      binding=plan['binding'])
        if plan['action'] == 'bootstrap':
            result.update(census=plan['new'], backup={key:plan['backup'][key]
                          for key in ('manifest_sha256', 'restore_sha256')})
        else:
            body=plan['body']
            result.update(census=plan['old'], payload=body['inventory']['payload'],
                          allowed=body['allowed'], rejected=body['rejected'],
                          evidence_sha256=body['evidence']['sha256'], pages=len(body['inventory']['pages']),
                          members=len(body['inventory']['members']),
                          source_sha256=[item['source_sha256'] for item in body['observed']])
        return result

    def _check(self, value, writer, *, transaction=None):
        snapshot=guard.registry_snapshot if transaction is not None else guard.media_snapshot
        census, records = snapshot(self.database, writer.root / 'publication-v1.json')
        result = dict(version=1, action='check', advisory=True, census=census,
                      owner=value['owner'], payload=value['payload'], decision='unknown')
        if transaction is not None:
            if __package__:
                from .publication_transaction import admission
            else:
                from publication_transaction import admission
            admission(transaction,writer)
        elif (os.path.lexists(writer.root/'tagger-publication-v1.json')
                or os.path.lexists(writer.root/'nested-derivative-v1.json')
                or os.path.lexists(writer.root/'tagger-recovery-v1.pending')
                or any(writer.fenced(**args) for args in ({}, {'tagger': True}, {'release': True}))):
            result.update(decision='held', reason='media-pending');return result
        if any(record['version']==2 for record in records.values()):
            if __package__:
                from .publication_derivative import matches as family_matches, families
            else:
                from publication_derivative import matches as family_matches, families
            matches=list(family_matches(records,value['payload']).values())
            family_index,_=families(records)
        else:
            matches = [record for record in records.values() if record['inventory']['payload'] == value['payload']]
            family_index={}
        if not matches:
            return result
        allowed = {guard.canonical_digest(owner):owner for record in matches for owner in record['allowed']}
        rejected = {guard.canonical_digest(owner) for record in matches for owner in record['rejected']}
        if len(allowed) > 8:
            raise guard.Unavailable('Matched owners exceed bounds')
        owners = [allowed[key] for key in sorted(allowed)]
        if family_index:
            current={'observed':[]}
            for owner in owners:
                observed=guard.observe_owners(self.native_database,writer,[owner],self.roots,
                    tool_root=self.tool_root,transaction=transaction)
                if (family_index.get(observed['inventory']['payload'])!=family_index.get(value['payload'])
                        or family_index.get(value['payload']) is None):
                    raise guard.Unavailable('Matched exact derivative owner lineage changed')
                current['observed'].extend(observed['observed'])
        else:
            current = (self.observe(writer, {'allowed': owners}) if transaction is None else
                       guard.observe_owners(self.native_database,writer,owners,self.roots,
                                            tool_root=self.tool_root,transaction=transaction))
            if current['inventory']['payload'] != value['payload']:
                raise guard.Unavailable('Matched correct-owner payload changed')
        proposed = guard.canonical_digest(value['owner'])
        result.update(decision='allowed' if proposed in allowed and proposed not in rejected else 'held',
                      reason='verified-correction', matched=sorted(guard.attestation(record) for record in matches),
                      observed=current['observed'], historical=[dict(attestation=guard.attestation(record),
                          allowed=record['allowed'], rejected=record['rejected'],
                          observed=record['observed']) for record in matches])
        return result


def execute(raw, *, data_dir, library_roots):
    value = request(raw)
    return Controller(data_dir, library_roots).dispatch(value)
