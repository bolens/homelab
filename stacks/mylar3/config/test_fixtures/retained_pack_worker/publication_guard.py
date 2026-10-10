"""Fresh local worker evidence under the existing shared writer.

This adapter does not register corrections, recover native state or call APIs.
Every mutation boundary must call check again; a returned snapshot is evidence,
never a reusable permission. Native final import must independently enforce it.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import re
import threading
import time

import publication_evidence as evidence
from media_writer import Writer, Busy

Unavailable = evidence.Unavailable
_ACTIVE = threading.local()


class ArchiveDiagnosticUnavailable(Unavailable):
    """Terminal ordinary-inventory refusal with read-only diagnostic codes."""
    def __init__(self, diagnostic):
        message='Current worker publication evidence unavailable'
        safe=None
        try:
            from publication_archive_diagnostics import public_summary, display
            safe=public_summary(diagnostic)
            if safe is not None:message=display(safe)
        except Exception:
            pass
        super().__init__(message)
        self.archive_diagnostic=safe


@dataclass(frozen=True,slots=True)
class NativeBatch:
    """Bounded read-side replies collected before exclusion, never permission."""
    worker: object
    thread: int
    raw: bytes
    COMMANDS = frozenset(('getHealth','workflowCommands','packWork'))

    def __init__(self, worker, values):
        if not isinstance(values,dict) or not set(values) <= self.COMMANDS:
            raise Unavailable('Invalid native work batch')
        object.__setattr__(self,'worker',worker)
        object.__setattr__(self,'thread',threading.get_ident())
        object.__setattr__(self,'raw',evidence.compact(values))
        if len(self.raw) > evidence.MAX_OUTPUT:
            raise Unavailable('Native work batch exceeds bounds')

    def read(self, worker, command):
        if (worker is not self.worker or self.thread != threading.get_ident()
                or command not in self.COMMANDS):
            raise Unavailable('Owned native work batch required')
        values = evidence.decode_json(self.raw)
        if command not in values or values[command] is None:
            raise Unavailable('Native work snapshot unavailable')
        return values[command]


class Authority:
    def __init__(self, config_dir, writer, mappings, *, tool_root=evidence.TOOL_ROOT):
        if type(writer) is not Writer:
            raise Unavailable('Exact shared writer required')
        self.config = Path(config_dir)
        self.writer = writer
        self.tool_root = tool_root
        if (not self.config.is_absolute() or '..' in self.config.parts
                or not self.config.is_dir()
                or any(p.is_symlink() for p in (self.config, *self.config.parents))
                or not isinstance(mappings, list) or not 1 <= len(mappings) <= 8):
            raise Unavailable('Invalid trusted worker observation scope')
        self.mappings = []
        for value in mappings:
            if not isinstance(value, dict) or set(value) != {'native', 'worker'}:
                raise Unavailable('Explicit native/worker media roots required')
            if any(not isinstance(value[key], str) or '\0' in value[key] or '\\' in value[key]
                   for key in ('native', 'worker')):
                raise Unavailable('Invalid media mapping spelling')
            native, worker = Path(value['native']), Path(value['worker'])
            if (any(not path.is_absolute() or path == Path('/') or '..' in path.parts
                    for path in (native, worker)) or not worker.is_dir()
                    or any(path.is_symlink() for path in (worker, *worker.parents))):
                raise Unavailable('Unsafe mapped media root')
            for old_native, old_worker in self.mappings:
                if any(a.is_relative_to(b) or b.is_relative_to(a)
                       for a, b in ((native, old_native), (worker, old_worker))):
                    raise Unavailable('Overlapping media mappings')
            self.mappings.append((native, worker))
        self.database = self.config / 'workflow.sqlite'
        self.catalog = self.config / 'mylar.db'
        self.native_batch = None

    def mapped(self, path):
        path = Path(path)
        for native, worker in self.mappings:
            if path.is_relative_to(native):
                return worker / path.relative_to(native)
        # The native observer also audits ancestors of a catalog claim. Use
        # their corresponding worker ancestor, rather than native-only paths.
        matches = {worker.parents[min(len(native.relative_to(path).parts) - 1, len(worker.parents) - 1)]
                   for native, worker in self.mappings if native.is_relative_to(path)
                   and 0 < len(native.relative_to(path).parts)}
        if len(matches) != 1:
            raise Unavailable('Unmapped or ambiguous catalog ancestor')
        return matches.pop()

    def admission(self):
        evidence.ordinary_purpose(self.writer)
        local = self.writer.local[1]
        if not getattr(local, 'depth', 0):
            raise Unavailable('Caller-owned shared writer required')
        current = evidence.writer_identity(self.writer)
        # Config and writable coordination binds must refer to the very same
        # existing native state; lexical mount names are insufficient.
        native = Writer(self.config / 'media-writer', create=False)
        if evidence.writer_identity(native) != current:
            raise Unavailable('Native config and writer mounts differ')
        if (self.writer.fenced(tagger=True) or self.writer.fenced(release=True)
                or any(os.path.lexists(self.writer.root / name) for name in
                       ('tagger-publication-v1.json', 'nested-derivative-v1.json', 'tagger-recovery-v1.pending'))):
            raise Unavailable('Native publication recovery remains pending')
        if self.writer.fenced() and not getattr(local, 'allow_pending', False):
            raise Unavailable('Worker recovery ownership required')
        result=evidence.media_snapshot(self.database, self.writer.root / 'publication-v1.json')
        evidence.ordinary_purpose(self.writer)
        return result

    def check(self, source, owner, *, advisory=None):
        """Recompute source, complete authority and every matched correct owner."""
        try:
            deadline = time.monotonic() + evidence.TIMEOUT
            owner = evidence.exact_owner(owner)
            census, records = self.admission()
            source = Path(source)
            try:
                inventory = evidence.inventory(source, tool_root=self.tool_root, deadline=deadline)
            except evidence.Unavailable:
                diagnostic=None
                try:
                    from publication_archive_diagnostics import diagnose
                    diagnostic=diagnose(source,evidence,time.monotonic()+evidence.TIMEOUT)
                except Exception:
                    pass  # Diagnostic availability cannot change terminal refusal.
                raise ArchiveDiagnosticUnavailable(diagnostic) from None
            from publication_derivative_evidence import families
            payload_index, payload_groups = families(records)
            family = payload_index.get(inventory['payload'])
            matches = (list(payload_groups.get(family, {}).values())
                       if any(record['version']==2 for record in records.values()) else
                       [record for record in records.values() if record['inventory']['payload']==inventory['payload']])
            result = dict(version=1, action='check', advisory=True, census=census,
                          owner=owner, payload=inventory['payload'], decision='unknown')
            catalog_signature = None
            if matches:
                allowed = {evidence.canonical_digest(item): item
                           for record in matches for item in record['allowed']}
                rejected = {evidence.canonical_digest(item)
                            for record in matches for item in record['rejected']}
                if len(allowed) > 8:
                    raise Unavailable('Matched owners exceed bounds')
                # Native roots need not exist at their native spelling here.
                # The generated reader checks only their mapped counterparts.
                catalog_signature = evidence.signature(self.catalog.lstat())
                observed = {'observed': []}
                for key in sorted(allowed):
                    owner_proof = evidence.observe_owners(self.catalog, self.writer,
                        [allowed[key]], [native for native, _ in self.mappings],
                        tool_root=self.tool_root, path_mapper=self.mapped, deadline=deadline)
                    if payload_index.get(owner_proof['inventory']['payload']) != family:
                        raise Unavailable('Correct archive payload changed outside reviewed lineage')
                    observed['observed'].extend(owner_proof['observed'])
                proposed = evidence.canonical_digest(owner)
                result.update(decision='allowed' if proposed in allowed and proposed not in rejected else 'held',
                    reason='verified-correction', matched=sorted(evidence.attestation(record) for record in matches),
                    observed=observed['observed'], historical=[dict(attestation=evidence.attestation(record),
                        allowed=record['allowed'], rejected=record['rejected'], observed=record['observed'])
                        for record in matches])
            after, after_records = self.admission()
            if not evidence.same_json([census, records], [after, after_records]):
                raise Unavailable('Correction authority changed during worker observation')
            if matches:
                for facts in observed['observed']:
                    signature, checksum = evidence.file_hash(self.mapped(facts['catalog']['path']), deadline=deadline)
                    if signature != facts['signature'] or checksum != facts['source_sha256']:
                        raise Unavailable('Correct publication changed after observation')
                if (evidence.signature(self.catalog.lstat()) != catalog_signature
                        or any(os.path.lexists(str(self.catalog) + suffix)
                               for suffix in ('-journal', '-wal', '-shm'))):
                    raise Unavailable('Native catalog changed after observation')
            signature, checksum = evidence.file_hash(source, deadline=deadline)
            if signature != inventory['source_signature'] or checksum != inventory['source_sha256']:
                raise Unavailable('Worker source changed during observation')
            if advisory is not None and not evidence.same_json(advisory, result):
                raise Unavailable('Native advisory no longer matches local evidence')
            if result['decision'] not in ('allowed', 'unknown'):
                raise Unavailable('Verified publication correction requires review')
            evidence.ordinary_purpose(self.writer)
            return dict(version=1, source=str(source), inventory=inventory, authority=result)
        except ArchiveDiagnosticUnavailable:
            raise
        except (OSError, ValueError, TypeError, KeyError, IndexError) as error:
            raise Unavailable('Current worker publication evidence unavailable') from error

    def unowned_check(self, source):
        """Absent catalog identity cannot authorize a registered payload."""
        before = self.admission()
        inventory = evidence.inventory(Path(source), tool_root=self.tool_root)
        for row in before[1].values():
            for observed in row['observed']:
                if (Path(source)==self.mapped(observed['catalog']['path'])
                        or inventory['source_signature'][:2]==observed['signature'][:2]):
                    raise Unavailable('Registered path or physical archive has no unowned permission')
        from publication_derivative_evidence import families
        index, _ = families(before[1])
        if inventory['payload'] in index:
            raise Unavailable('Registered payload requires an exact current owner')
        signature, checksum = evidence.file_hash(source)
        if (signature != inventory['source_signature'] or checksum != inventory['source_sha256']
                or not evidence.same_json(before, self.admission())):
            raise Unavailable('Unowned source or authority changed')
        return dict(version=1, source=str(source), inventory=inventory, census=before[0])

    def import_check(self, source, match):
        """Resolve the proposed unfiltered native owner anew at each boundary."""
        if (not isinstance(match, dict) or set(match) != {'issueid', 'comicid'}
                or any(not isinstance(value, str) or re.fullmatch('[1-9][0-9]{0,15}',value) is None
                       for value in match.values())):
            raise Unavailable('Exact proposed import identity required')
        before = self.admission()
        owner = evidence.catalog_owner(self.config, match['issueid'], match['comicid'])
        if owner is None:
            raise Unavailable('Proposed native import owner missing')
        result = self.check(source, owner)
        if not evidence.same_json(owner, evidence.catalog_owner(
                self.config, match['issueid'], match['comicid'])):
            raise Unavailable('Proposed native import owner changed')
        if not evidence.same_json(before, self.admission()):
            raise Unavailable('Correction authority changed during import binding')
        return result

    def catalog_absence(self, source, inventory):
        """No current native path or physical archive may be discarded."""
        from contextlib import closing
        import sqlite3
        source = Path(source)
        census = self.admission()
        before = evidence.signature(self.catalog.lstat())
        sidecars = [str(self.catalog)+suffix for suffix in ('-journal','-wal','-shm')]
        if any(os.path.lexists(path) for path in sidecars):
            raise Unavailable('Uncataloged check requires stable native catalog')
        rows = {};count = size = 0
        deadline = time.monotonic()+evidence.TIMEOUT
        with closing(sqlite3.connect(self.catalog.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
            db.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
            if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:
                raise Unavailable('Uncataloged check requires readable native catalog')
            for table,fields in (('comics',('ComicID','ComicLocation')),
                    ('issues',('IssueID','ComicID','Location')),
                    ('annuals',('IssueID','ComicID','Location'))):
                total,bytes_used = db.execute('SELECT count(*),coalesce(sum('+
                    '+'.join('coalesce(length(CAST('+field+' AS BLOB)),0)' for field in fields)+
                    '),0) FROM '+table).fetchone()
                count+=total;size+=bytes_used
                if count>evidence.CATALOG_ROWS or size>evidence.CATALOG_BYTES:
                    raise Unavailable('Uncataloged projection exceeds bounds')
                rows[table]=[dict(zip(fields,row)) for row in db.execute('SELECT '+','.join(fields)+' FROM '+table)]
                if any(value is not None and not isinstance(value,str) for row in rows[table] for value in row.values()):
                    raise Unavailable('Malformed uncataloged projection')
        parents = {}
        for row in rows['comics']:parents.setdefault(row['ComicID'],[]).append(row['ComicLocation'])
        for row in rows['issues']+rows['annuals']:
            if time.monotonic()>=deadline:raise Unavailable('Uncataloged observation timed out')
            if not row['Location']:continue
            parent=parents.get(row['ComicID'],[])
            if len(parent)!=1:raise Unavailable('Ambiguous uncataloged path parent')
            path=evidence._catalog_path(parent[0],row['Location'],[root for root,_ in self.mappings])
            mapped=self.mapped(path)
            for component in (mapped,*mapped.parents):evidence._claim_identity(component)
            physical=evidence._claim_identity(mapped)
            if (mapped==source or (physical is not None and list(physical[:2])==inventory['source_signature'][:2])):
                raise Unavailable('Native catalog relocation requires an exact owned handoff')
        signature,checksum=evidence.file_hash(source)
        if (evidence.signature(self.catalog.lstat())!=before or any(os.path.lexists(path) for path in sidecars)
                or signature!=inventory['source_signature'] or checksum!=inventory['source_sha256']
                or not evidence.same_json(census,self.admission())):
            raise Unavailable('Uncataloged source/catalog authority changed')
        return before

    def uncataloged_check(self, source):
        """Require full current catalog path/physical absence before relocation."""
        source=Path(source)
        if not any(source.is_relative_to(mapped) for _,mapped in self.mappings):
            raise Unavailable('Uncataloged source is outside mapped library')
        proof=self.unowned_check(source)
        signature=self.catalog_absence(source,proof['inventory'])
        fresh=self.unowned_check(source)
        if (evidence.signature(self.catalog.lstat())!=signature
                or any(os.path.lexists(str(self.catalog)+suffix) for suffix in ('-journal','-wal','-shm'))
                or not evidence.same_json(proof,fresh)):
            raise Unavailable('Uncataloged source/catalog authority changed')
        return dict(proof,catalog_signature=signature)

    def target_match(self, target):
        """Resolve an actual mapped catalog path, never a filename suggestion."""
        from contextlib import closing
        import sqlite3
        target = Path(target)
        native = [root / target.relative_to(mapped) for root, mapped in self.mappings
                  if target.is_relative_to(mapped)]
        if len(native) != 1:
            raise Unavailable('Duplicate target has no unique native mapping')
        self.admission()
        before = evidence.signature(self.catalog.lstat())
        if any(os.path.lexists(str(self.catalog)+suffix) for suffix in ('-journal','-wal','-shm')):
            raise Unavailable('Duplicate target catalog requires recovery')
        matches = []
        deadline = time.monotonic() + evidence.TIMEOUT
        with closing(sqlite3.connect(self.catalog.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
            db.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
            for table in ('comics','issues','annuals'):
                if db.execute('SELECT count(*) FROM '+table).fetchone()[0] > evidence.CATALOG_ROWS:
                    raise Unavailable('Duplicate target catalog exceeds bounds')
            for table in ('issues','annuals'):
                matches.extend(db.execute('SELECT i.IssueID,i.ComicID FROM '+table+
                    " i JOIN comics c ON c.ComicID=i.ComicID WHERE (CASE WHEN substr(i.Location,1,1)='/' "
                    "THEN i.Location ELSE rtrim(c.ComicLocation,'/') || '/' || i.Location END)=? LIMIT 3",
                    (str(native[0]),)).fetchall())
        if (len(matches)!=1 or evidence.signature(self.catalog.lstat())!=before
                or any(os.path.lexists(str(self.catalog)+suffix) for suffix in ('-journal','-wal','-shm'))):
            raise Unavailable('Duplicate target has no stable unique catalog owner')
        match = dict(issueid=matches[0][0],comicid=matches[0][1])
        # The unfiltered owner/observer below rejects deleted, shadowed,
        # inactive, malformed or physical-alias claims independently.
        self.import_check(target,match)
        if (evidence.signature(self.catalog.lstat())!=before
                or any(os.path.lexists(str(self.catalog)+suffix) for suffix in ('-journal','-wal','-shm'))):
            raise Unavailable('Duplicate target catalog changed after owner binding')
        return match

    def cleanup_check(self, source, target, *, match=None):
        """Bind eligible duplicate bytes to the current catalog publication."""
        before = self.admission()
        source, target = Path(source), Path(target)
        source_signature = evidence.signature(source.lstat())
        if source_signature[:2] == evidence.signature(target.lstat())[:2]:
            raise Unavailable('Catalog original or physical alias cannot be cleaned')
        for row in before[1].values():
            for observed in row['observed']:
                if (source == self.mapped(observed['catalog']['path'])
                        or source_signature[:2] == observed['signature'][:2]):
                    raise Unavailable('Protected catalog original cannot be cleaned')
        resolved = self.target_match(target)
        if match is not None and not evidence.same_json(match,resolved):
            raise Unavailable('Duplicate cleanup owner changed')
        proof = self.confirmation_check(source,target,resolved)
        self.catalog_absence(source,proof['source']['inventory'])
        if (not evidence.same_json(proof,self.confirmation_check(source,target,resolved))
                or not evidence.same_json(before,self.admission())):
            raise Unavailable('Duplicate cleanup authority changed')
        return dict(version=1,match=resolved,confirmation=proof)

    def confirmation_check(self, source, target, match):
        """A pack destination must still be this owner's unique catalog archive."""
        source_proof = self.import_check(source, match)
        target_proof = self.import_check(target, match)
        owner = source_proof['authority']['owner']
        for record in self.admission()[1].values():
            if any(evidence.same_json(owner,allowed) for allowed in record['allowed']):
                if target_proof['inventory']['payload']!=record['inventory']['payload']:
                    raise Unavailable('Registered owner archive changed outside reviewed lineage')
        signature = evidence.signature(self.catalog.lstat())
        observed = evidence.observe_owners(self.catalog, self.writer, [owner],
            [native for native, _ in self.mappings], tool_root=self.tool_root,
            path_mapper=self.mapped)
        if (self.mapped(observed['observed'][0]['catalog']['path']) != Path(target)
                or any(proof['inventory']['payload'] != observed['inventory']['payload']
                       for proof in (source_proof, target_proof))):
            raise Unavailable('Pack confirmation is not the current owner archive')
        for path, before in ((source,source_proof),(target,target_proof)):
            if not evidence.same_json(before,self.import_check(path,match)):
                raise Unavailable('Pack confirmation source or authority changed')
        if (evidence.signature(self.catalog.lstat()) != signature
                or any(os.path.lexists(str(self.catalog)+suffix) for suffix in ('-journal','-wal','-shm'))):
            raise Unavailable('Pack confirmation catalog changed')
        return dict(source=source_proof,target=target_proof,observed=observed)


def current(worker):
    """Only the coordinator's current thread may use its owned local adapter."""
    value = getattr(_ACTIVE, 'value', None)
    if value is None or value[0] is not worker or type(value[1]) is not Authority:
        raise Unavailable('Owned worker publication cycle required')
    authority = value[1]
    if not getattr(authority.writer.local[1], 'depth', 0):
        raise Unavailable('Worker writer exclusion was released')
    return authority


def import_check(worker, source, match):
    """Standalone compatibility never waives configured coordination ownership."""
    if worker.config.get('writer_state') is None:
        return None
    return current(worker).import_check(source, match)


def catalog_path(worker, path):
    """Translate only native catalog paths through the active owned mapping."""
    path=Path(path)
    if worker.config.get('writer_state') is None:return path
    return current(worker).mapped(str(path))


def confirmation_check(worker, source, target, match):
    if worker.config.get('writer_state') is None:
        return None
    return current(worker).confirmation_check(source,target,match)


def remote_unlocked(worker):
    """Reject HTTP before a guarded native handler waits for our own Writer."""
    value = getattr(_ACTIVE, 'value', None)
    if value is not None:
        raise Unavailable('Native API work must occur outside shared writer exclusion')
    # Also cover direct callers holding the configured Writer without scope.
    root = worker.config.get('writer_state')
    if root is not None:
        writer = Writer(root, create=False)
        if getattr(writer.local[1], 'depth', 0):
            raise Unavailable('Native API work must occur outside shared writer exclusion')
        # A second bind spelling can have a separate Python registry entry but
        # the same flock inode. Probe and release, never retain it across HTTP.
        try:
            with writer.hold(allow_pending=True, allow_tagger_pending=True,
                             allow_release_pending=True, timeout=0):
                pass
        except Busy:
            raise Unavailable('Native API work waits for shared writer release') from None


@contextmanager
def scope(worker, writer, *, native_batch=None):
    """Bind complete authority before journals/fences and recheck before clear."""
    if getattr(_ACTIVE, 'value', None) is not None:
        raise Unavailable('Nested worker publication cycle is unavailable')
    settings = worker.config.get('mylar') or {}
    if not isinstance(settings, dict):
        raise Unavailable('Trusted Mylar configuration required')
    authority = Authority(settings.get('config_dir', '/mylar'), writer,
                          worker.config.get('publication_roots'))
    if native_batch is not None:
        if type(native_batch) is not NativeBatch or native_batch.worker is not worker:
            raise Unavailable('Exact current native work batch required')
        authority.native_batch = native_batch
    before = authority.admission()
    _ACTIVE.value = (worker, authority)
    try:
        yield authority
        after = authority.admission()
        if not evidence.same_json(before, after):
            raise Unavailable('Correction authority changed during worker cycle')
    finally:
        _ACTIVE.value = None
