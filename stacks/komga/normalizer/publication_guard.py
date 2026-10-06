"""Fresh local worker evidence under the existing shared writer.

This adapter does not register corrections, recover native state or call APIs.
Every mutation boundary must call check again; a returned snapshot is evidence,
never a reusable permission. Native final import must independently enforce it.
"""
import os
from pathlib import Path
import time

import publication_evidence as evidence
from media_writer import Writer

Unavailable = evidence.Unavailable


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
                       ('tagger-publication-v1.json', 'tagger-recovery-v1.pending'))):
            raise Unavailable('Native publication recovery remains pending')
        if self.writer.fenced() and not getattr(local, 'allow_pending', False):
            raise Unavailable('Worker recovery ownership required')
        return evidence.registry_snapshot(self.database, self.writer.root / 'publication-v1.json')

    def check(self, source, owner, *, advisory=None):
        """Recompute source, complete authority and every matched correct owner."""
        try:
            deadline = time.monotonic() + evidence.TIMEOUT
            owner = evidence.exact_owner(owner)
            census, records = self.admission()
            source = Path(source)
            inventory = evidence.inventory(source, tool_root=self.tool_root, deadline=deadline)
            matches = [record for record in records.values()
                       if record['inventory']['payload'] == inventory['payload']]
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
                observed = evidence.observe_owners(self.catalog, self.writer,
                    [allowed[key] for key in sorted(allowed)],
                    [native for native, _ in self.mappings], tool_root=self.tool_root,
                    path_mapper=self.mapped, deadline=deadline)
                if observed['inventory']['payload'] != inventory['payload']:
                    raise Unavailable('Correct archive payload changed')
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
            return dict(version=1, source=str(source), inventory=inventory, authority=result)
        except (OSError, ValueError, TypeError, KeyError, IndexError) as error:
            raise Unavailable('Current worker publication evidence unavailable') from error
