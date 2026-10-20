"""Explicit disposable bootstrap-originals -> checked plan13 composition.

This consumes original facts; it does not produce SourceCohort, effective-scope
ACKs, backups or stopped-reader authority. The checked Parent remains the sole
owning consumer of those protocols. No CLI, automatic installation, replay or
runtime/factory/NFS acceptance is supplied here.
"""
import copy
import os
from pathlib import Path
import stat
import time

import comic_reader_lifecycle_parent as p
import genuine_application_bootstrap as bootstrap
import install_configured_reader_parent as installer

need = p.need
EFFECTIVE = ('producer', 'parent_source', 'report', 'ack', 'runtime', 'acceptance', 'parent_ack')
NESTED = ('active_scope', 'effective_observer_review', 'source_cohort', 'native_controls')
RIGHTS = ('installed_factories_verified', 'actual_nfs_verified', 'publication_acceptance',
          'mutation_authority', 'automatic_replay')
OBSERVER_SHA = '59ccce44028d2bc6a7c9f80dd08ae6b239b4e131e5b0508eb8251da4b685815c'


class Originals:
    """Retain supplied full9, SHA and ancestor5; never adopt a new incarnation."""
    def __init__(self):
        self.refs = {}; self.nodes = {}; self.absent = set(); self.namespaces = {}

    def read(self, ref, *, private=True):
        need(type(ref) is dict and set(ref) == {'path', 'sha256', 'signature9'}, 'producer-original-ref')
        path = p.absolute(ref['path'])
        for name, value in p.parents(path).items():
            need(name not in self.nodes or self.nodes[name] == value, 'producer-original-ancestor')
            self.nodes[name] = value
        need(str(path) not in self.refs or self.refs[str(path)] == ref, 'producer-original-conflict')
        raw = p.read(ref, private=private)
        self.refs[str(path)] = copy.deepcopy(ref)
        return raw

    def json(self, ref, *, private=True):
        return p.decode(self.read(ref, private=private))

    def close(self):
        for ref in tuple(self.refs.values()):
            # Public source/UID1000 bootstrap originals retain their original
            # owner/mode in full9; they must not become private root copies.
            p.read(ref, private=False)
        p.final({name: tuple(ref['signature9']) for name, ref in self.refs.items()}, self.nodes, self.absent)
        for path, names in self.namespaces.items():
            need(set(os.listdir(path)) == names, 'producer-original-namespace')


def checked_installation(originals, result_ref, base_manifest_ref):
    """Re-derive the existing install result, without installing again.

    SourceCohort may already bind these paths. Any fresh copy/reinstall would
    change its originals. Even matching hashes cannot replace output full9.
    """
    result = originals.json(result_ref)
    need(type(result) is dict and set(result) == {'output', 'prepared', 'lifecycle_performed',
         'configured_admission_proven', 'root_signature5', 'output_refs'}
         and result['prepared'] is True and result['lifecycle_performed'] is False
         and result['configured_admission_proven'] is False, 'producer-original-installation')
    root = p.absolute(result['output']); root5 = result['root_signature5']
    need(list(p.five(os.lstat(root))) == root5 and stat.S_ISDIR(root5[2])
         and stat.S_IMODE(root5[2]) == 0o700 and root5[3] == os.geteuid(), 'producer-installation-root')
    refs = result['output_refs']
    names = set(installer.EXPECTED_NFS) | {
        'comic_reader_lifecycle_parent.py', 'comic_child_control_projection.py',
        'publication_reader_admission.py', 'comic_archive_repair_action.py',
        'comic_archive_backup_action.py', 'comic_archive_proof_producer.py',
        'comic_archive_evidence_adapter.py', 'comic_archive_worker_vectors.py',
        'comic_reader_backup.py', 'comic_reader_backup_primitives.py', 'comic_reader_schema.py',
        'publication_native_configured_scope.py', 'comic_native_process_probe.py',
        'publication_reader_admission.overlay.py', 'configured-sdk-map.json',
        'configured-cohort.json', 'configured-source-observation.json'}
    need(type(refs) is dict and set(refs) == {str(root / name) for name in names}
         and set(os.listdir(root)) == names, 'producer-installation-exact-namespace')
    originals.namespaces[str(root)] = names
    def ref(name):
        value = refs[str(root / name)]
        need(value['path'] == str(root / name), 'producer-installation-original-path')
        return copy.deepcopy(value)
    receipt = originals.json(ref('configured-source-observation.json'))
    sources = receipt['original_source_refs']
    need(set(sources) == set(installer.EXPECTED) | set(installer.EXPECTED_NFS), 'producer-installation-source-roles')
    raws = {role: originals.read(value, private=False) for role, value in sources.items()}
    profile = installer.worker_profile(receipt['worker_observation_profile'])
    for role in ('source', 'image_sources', 'image_metadata'):originals.read(profile[role])
    worker_image, _, _ = installer.worker_original_inputs(profile)
    artifacts, derived = installer.build({name: raws[name] for name in installer.EXPECTED},
        str(root / 'comic_reader_lifecycle_parent.py'), worker_observation=profile, worker_image=worker_image)
    base_sdk = originals.json(receipt['base_sdk_ref'])
    sdk, cohort = installer.configured_maps(base_sdk, originals.read(base_manifest_ref, private=False), artifacts, derived)
    expected = {**artifacts, **installer.build_nfs({name: raws[name] for name in installer.EXPECTED_NFS}),
        'publication_reader_admission.overlay.py': artifacts['publication_reader_admission.py'],
        'configured-sdk-map.json': installer_json(sdk), 'configured-cohort.json': installer_json(cohort)}
    for name, raw in expected.items():
        need(originals.read(ref(name), private=name != 'publication_reader_admission.overlay.py') == raw,
             'producer-installation-derived-bytes')
    need(all(receipt.get(key) == value for key, value in derived.items())
         and receipt.get('worker_observation_image') == worker_image
         and receipt.get('effective_sdk_map_sha256') == ref('configured-sdk-map.json')['sha256']
         and receipt.get('effective_cohort_sha256') == ref('configured-cohort.json')['sha256']
         and receipt.get('actual_overlay_origins_verified') is False
         and receipt.get('worker_observation_installed_parity_verified') is False
         and receipt.get('nfs_session_admission_proven') is False, 'producer-installation-derived-receipt')
    originals.close()
    return dict(root=root, refs={name: ref(name) for name in names}, receipt=receipt,
                worker=profile, worker_image=worker_image, sdk=sdk)


def installer_json(value):
    import json
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def nested_originals(originals, active_ref, supplied):
    """Close the finite existing NFS/effective graph using supplied full9 only."""
    need(type(supplied) is dict and 1 <= len(supplied) <= 128
         and all(name == ref.get('path') for name, ref in supplied.items()), 'producer-finite-original-facts')
    used = set()
    def follow(ref):
        need(type(ref) is dict and set(ref) == {'path', 'sha256'} and ref['path'] in supplied,
             'producer-missing-original-fact')
        full = supplied[ref['path']]
        need(full['sha256'] == ref['sha256'], 'producer-original-fact-pin')
        used.add(ref['path']); return originals.read(full)
    active = originals.json(active_ref)
    need(type(active) is dict and set(active) == {'version', 'kind', *NESTED, 'parent_admission',
         'probe_plan', 'operation_output'} and type(active['version']) is int and active['version'] == 1
         and active['kind'] == 'approved-active-nfs-owned-lifecycle', 'producer-active-original-schema')
    docs = {name: p.decode(follow(active[name])) for name in NESTED}
    review = docs['effective_observer_review']
    need(type(review) is dict and set(review) == set(EFFECTIVE), 'producer-effective-seven-originals')
    effective = {name: follow(review[name]) for name in EFFECTIVE}
    report = p.decode(effective['report'])
    need(type(report.get('config_files')) is dict and type(report.get('absent_config_files')) is list
         and type(report.get('optional_absent_scopes')) is dict, 'producer-effective-original-report')
    for path, row in report['config_files'].items():
        full = dict(path=path, **row)
        need(path in supplied and supplied[path] == full, 'producer-config-original-fact')
        used.add(path); originals.read(full, private=False)
    for path in (*report['absent_config_files'], *report['optional_absent_scopes']):
        path = p.absolute(path); need(not os.path.lexists(path), 'producer-original-absence')
        originals.absent.add(str(path))
        for name, value in p.parents(path).items():
            need(name not in originals.nodes or originals.nodes[name] == value, 'producer-absence-original-ancestor')
            originals.nodes[name] = value
    cohort = docs['source_cohort']; scope = docs['active_scope']
    need(type(cohort) is dict and type(cohort.get('sources')) is dict and len(cohort['sources']) == 16
         and type(cohort.get('logs')) is dict and set(cohort['logs']) == {'stdout', 'stderr'}
         and type(scope.get('sources')) is dict and 1 <= len(scope['sources']) <= 32,
         'producer-source-cohort-original-graph')
    for value in (*cohort['sources'].values(), *cohort['logs'].values(), cohort['parent'], cohort['receipt'], *scope['sources'].values()):follow(value)
    query = p.decode(follow(scope['sources']['current_komga_libraries']))
    need(query.get('kind') == 'approved-active-komga-library-query', 'producer-original-reader-query')
    follow(query['configuration'])
    need(used == set(supplied), 'producer-no-unscoped-original-facts')
    return active, docs


def compose(document, originals, installation):
    """Assemble a plan; no effect, transport callback or admission is performed."""
    required = {'version', 'kind', 'nonce', 'observed', 'seconds', 'bootstrap_plan', 'bootstrap_result',
        'catalog', 'installation', 'base_manifest', 'current_roles', 'publication_geometry', 'native',
        'mounts', 'bounds', 'operation', 'archive_request', 'archive_scopes', 'nfs_active_input',
        'nfs_intents', 'originals', 'selected_image_metadata', 'observer', 'base_admission'}
    need(type(document) is dict and set(document) == required and type(document['version']) is int
         and document['version'] == 1 and document['kind'] == 'disposable-original-plan13-input'
         and p.digest(document['nonce']) and type(document['observed']) is int
         and 0 <= time.time() - document['observed'] <= 120
         and type(document['seconds']) is int and 1 <= document['seconds'] <= 900, 'producer-input-schema-freshness')
    old = originals.json(document['bootstrap_plan'], private=False)
    result = originals.json(document['bootstrap_result'], private=False)
    catalog = originals.json(document['catalog'], private=False)
    current = originals.json(document['current_roles'])
    need(old.get('kind') == 'approved-disposable-application-bootstrap'
         and old.get('nonce') == result.get('nonce') == catalog.get('nonce') == current.get('nonce') == document['nonce']
         and result.get('kind') == 'disposable-application-bootstrap-observation'
         and catalog.get('kind') == 'disposable-native-catalog-processing-observation'
         and result.get('native_catalog_processing') == document['catalog']
         and result.get('native_catalog_processing_observed') is True
         and catalog.get('native_catalog_processing_observed') is True
         and result.get('ordinary_ack_verified') is False and catalog.get('ordinary_ack_verified') is False
         and catalog.get('birth_verified') is False and catalog.get('daemon_operation_identity') is False
         and all(result.get(key) is False and catalog.get(key) is False for key in RIGHTS), 'producer-bootstrap-catalog-crossjoin')
    need(type(current) is dict and set(current) == {'nonce', 'observed', 'roles', 'native_process'}
         and current['observed'] == document['observed'] and current['native_process'] == catalog['process'],
         'producer-current-process-original')
    roles = current['roles']; need(set(roles) == {'native', 'reader', 'worker'}, 'producer-three-roles')
    need(len({row['id'] for row in roles.values()}) == 3, 'producer-distinct-roles')
    for name, row in roles.items():
        need(set(row) == {'id', 'image', 'profile', 'epoch'} and row['id'] == old['roles'][name]['id']
             and row['image'] == old['images'][name] and p.digest(row['id']), 'producer-original-role')
        profile = row['profile']
        need(profile.get('Id') == row['id'] and profile.get('Image') == row['image']
             and profile.get('Name') == '/archive-bootstrap-' + document['nonce'][:16] + '-' + name
             and profile.get('Config', {}).get('Labels', {}).get(bootstrap.LABEL) == document['nonce']
             and profile['Config']['Labels'].get(bootstrap.PURPOSE) == 'genuine-archive-fixture', 'producer-disposable-role-purpose')
    bracket = result.get('reader_task_empty_observation')
    need(type(bracket) is dict and bracket.get('kind') == 'original-reader-task-empty-bracket'
         and bracket.get('nonce') == document['nonce'] and bracket.get('reader_image') == roles['reader']['image']
         and bracket.get('observation', {}).get('queue_empty_observed') is True
         and all(bracket.get(key) is False for key in ('application_quiescence_verified', 'future_exclusion_verified',
             'stop_authority', 'reader_resume_authority', 'publication_acceptance', 'mutation_authority', 'ordinary_ack_verified')),
         'producer-original-queue-observation-required')
    need(bracket['roles']['profiles'] == {name: row['profile'] for name, row in roles.items()}
         and bracket['roles']['epochs'] == {name: row['epoch'] for name, row in roles.items()}
         and bracket['roles']['reader'] == result['reader'], 'producer-original-bootstrap-role-bracket')
    need(catalog['native_CID'] == roles['native']['id'] and catalog['native_image'] == roles['native']['image']
         and installation['worker_image'] == roles['worker']['image'], 'producer-original-image-join')
    files = catalog['files']
    need(type(files) is list and len(files) == 2 and {row['role'] for row in files} == {'target', 'unrelated'}, 'producer-two-native-outputs')
    target = next(row for row in files if row['role'] == 'target')
    unrelated = next(row for row in files if row['role'] == 'unrelated')
    need(target['path'] != unrelated['path'] and target['owner'] != unrelated['owner'], 'producer-distinct-original-owners')
    need(all(row['signature9'][6:8] == [1000, 1000] and stat.S_IMODE(row['signature9'][5]) == 0o600 for row in files),
         'producer-native-output-owner-mode')
    books = result['reader']['books']
    need(type(books) is list and len(books) == 2 and {book['path'] for book in books} == {row['path'] for row in files}
         and all(next(book['hashes'] for book in books if book['path'] == row['path']) == row['pages'] for row in files),
         'producer-original-reader-native-output-join')
    request = originals.json(document['archive_request']); scopes = originals.json(document['archive_scopes'])
    need(type(request) is dict and set(request) == {'version', 'owner', 'operation_id', 'terminal'}
         and type(request['version']) is int and request['version'] == 2 and request['owner'] == target['owner']
         and p.digest(request['operation_id']) and request['terminal'] in ('forward', 'rollback'), 'producer-original-target-request')
    need(type(scopes) is dict and set(scopes) == {'version', 'scratch', 'retention_root'} and scopes['version'] == 1, 'producer-original-scopes')
    geometry = copy.deepcopy(document['publication_geometry'])
    need(set(geometry) == {'version', 'kind', 'common_root', 'library', 'retention'}, 'producer-current-geometry')
    for name in ('common_root', 'library', 'retention'):
        bootstrap.directory(geometry[name])
        need(tuple(geometry[name]['signature9'][i] for i in (0, 1, 5, 6, 7)) == tuple(old['geometry'][name]['signature9'][i] for i in (0, 1, 5, 6, 7)), 'producer-original-geometry-identity')
    common = Path(geometry['common_root']['path']); library = Path(geometry['library']['path'])
    need(result['reader']['library']['root'] == str(library), 'producer-original-reader-library-root')
    state = p.absolute(old['state_root']['path']); operation = p.absolute(document['operation'])
    scratch = p.absolute(scopes['scratch'])
    need(state.name == 'archive-bootstrap-' + document['nonce'] and common.name == 'archive-publication-' + document['nonce']
         and library.parent == common and Path(geometry['retention']['path']).parent == common
         and scopes['retention_root'] == geometry['retention']['path']
         and state in operation.parents and state in scratch.parents and operation != scratch
         and all(library in Path(row['path']).parents for row in files), 'producer-disposable-geometry')
    need(not os.path.lexists(operation), 'producer-operation-must-be-new')
    state9 = old['state_root']['signature9']; now_state = os.lstat(state)
    need(stat.S_ISDIR(now_state.st_mode) and stat.S_IMODE(now_state.st_mode) == 0o700
         and (now_state.st_uid, now_state.st_gid) == (1000, 1000)
         and tuple(p.five(now_state)) == tuple(state9[i] for i in (0, 1, 5, 6, 7)), 'producer-original-state-root')
    for row in files:originals.read({key: row[key] for key in ('path', 'sha256', 'signature9')}, private=False)
    mapping = p.Paths(document['mounts']); native = document['native']
    need(type(native) is dict and native.get('roots') == [str(library)]
         and mapping.host(native['data']) == str(Path(old['native_ini']['path']).parent)
         and mapping.host(str(library)) == str(library), 'producer-original-native-mapping')
    # The genuine Parent holds common-root FDs, excludes image overlays, bounds
    # every writable mount and validates actual NFS ownership and intent sources.
    active, docs = nested_originals(originals, document['nfs_active_input'], document['originals'])
    need(docs['source_cohort'].get('images') == dict(native=roles['native']['image'], selected=roles['native']['image'],
         reader=roles['reader']['image'], worker=roles['worker']['image']), 'producer-cohort-original-images')
    refs = installation['refs']
    need(docs['source_cohort']['parent'] == {key: refs['comic_negative_nfs_active_parent.py'][key] for key in ('path', 'sha256')}, 'producer-cohort-owning-parent-original')
    originals.read(document['nfs_intents']); originals.read(document['selected_image_metadata'])
    need(document['observer']['sha256'] == OBSERVER_SHA
         and Path(document['observer']['path']).name == 'comic_archive_terminal_vectors.py', 'producer-reviewed-observer')
    originals.read(document['observer'])
    need(document['base_admission']['sha256'] == installer.EXPECTED['admission'], 'producer-private-base-admission-pin')
    originals.read(document['base_admission'])
    source = refs['comic_reader_lifecycle_parent.py']
    plan = dict(version=13, kind='reviewed-archive-one-lifecycle-protocol', nonce=document['nonce'], seconds=document['seconds'],
        operation=str(operation), selected_image=roles['native']['image'], action='archive-one', terminal_mode='same-child-v1',
        reader=dict(id=roles['reader']['id'], profile=p.static(roles['reader']['profile'])),
        held_native=dict(id=roles['native']['id'], profile=p.static(roles['native']['profile'])),
        held_worker=dict(id=roles['worker']['id'], profile=p.static(roles['worker']['profile'])),
        provider=refs['comic_archive_repair_action.py'], producer=refs['comic_archive_evidence_adapter.py'],
        observer=copy.deepcopy(document['observer']), backup_provider=refs['comic_archive_backup_action.py'],
        sdk_map=refs['configured-sdk-map.json'], mounts=copy.deepcopy(document['mounts']), native=copy.deepcopy(native),
        producer_inputs={key: copy.deepcopy(document[key]) for key in ('archive_request', 'archive_scopes')},
        birth_source_sha256=installation['sdk']['publication_native_scope_birth.py'],
        scope_projection=refs['publication_native_configured_scope.py'], bounds=copy.deepcopy(document['bounds']),
        nfs=dict(adapter=refs['comic_nfs_factual_successor.py'], active_parent=refs['comic_negative_nfs_active_parent.py'], active_input=copy.deepcopy(document['nfs_active_input'])),
        worker_observation={key: copy.deepcopy(installation['worker'][key]) for key in ('mode', 'source', 'image_sources')}, publication_geometry=geometry)
    configured = dict(base_admission=copy.deepcopy(document['base_admission']),
        admission=refs['publication_reader_admission.py'], cohort=refs['configured-cohort.json'], image_metadata=copy.deepcopy(document['selected_image_metadata']))
    originals.close()
    # Parent's eight engine/session originals exclude active Parent and adapter,
    # which already have their distinct original plan.nfs roles.
    need(set(p.NFS_HOST_SOURCE_PINS) < set(installer.EXPECTED_NFS)
         and all(installer.EXPECTED_NFS[name] == pin for name, pin in p.NFS_HOST_SOURCE_PINS.items()), 'producer-nfs-host-source-selection')
    return plan, source, configured, {name: refs[name] for name in p.NFS_HOST_SOURCE_PINS}


class Producer:
    """One explicit attempt. Unknown outcomes retain every input and intent."""
    def __init__(self, request_ref, output):
        self.originals = Originals(); self.request_ref = copy.deepcopy(request_ref)
        self.document = self.originals.json(request_ref)
        self.output = p.absolute(str(output)); self.entered = False
        need(not os.path.lexists(self.output), 'producer-output-no-adoption')
        parent = os.lstat(self.output.parent)
        need(stat.S_ISDIR(parent.st_mode) and stat.S_IMODE(parent.st_mode) == 0o700
             and parent.st_uid == os.geteuid(), 'producer-private-output-parent')
        # Missing prerequisites refuse before writes, loading Parent or engine.
        need(type(self.document) is dict and {'installation', 'base_manifest'} <= set(self.document), 'producer-installation-required')
        installation = checked_installation(self.originals, self.document['installation'], self.document['base_manifest'])
        self.plan, self.source, self.configured, self.nfs_sources = compose(self.document, self.originals, installation)
        self.tape = p.encode(self.document); self.deadline = time.monotonic() + self.document['seconds']
        self.bound = p.encode(dict(plan=self.plan, source=self.source, configured=self.configured, nfs_sources=self.nfs_sources))
        catalog = self.originals.json(self.document['catalog'], private=False)
        self.target = next(row['path'] for row in catalog['files'] if row['role'] == 'target')

    def execute(self, *, activate=False):
        need(activate is True and os.geteuid() == 0, 'producer-explicit-root-activation')
        return self._enter()

    def _enter(self):
        """Finite owning call; host controls may exercise pre-engine refusal."""
        need(not self.entered and not os.path.lexists(self.output), 'producer-no-replay')
        self.originals.close(); need(time.monotonic() < self.deadline and p.encode(self.document) == self.tape, 'producer-original-lifetime')
        need(p.encode(dict(plan=self.plan, source=self.source, configured=self.configured, nfs_sources=self.nfs_sources)) == self.bound,
             'producer-derived-inputs-changed')
        # Use only the original configured source loader and its genuine engine.
        module = p.pinned_module(self.source)
        need(callable(getattr(module, 'run_operation', None)) and callable(getattr(module, 'ScopedDocker', None)), 'producer-owning-entry-required')
        self.originals.close()
        self.output.mkdir(mode=0o700)
        self.plan_ref = bootstrap.put(self.output / 'plan13.json', self.plan)
        bootstrap.put(self.output / 'entry-intent.json', dict(kind='checked-plan13-entry-intent', request=self.request_ref,
            plan=self.plan_ref, source=self.source, automatic_replay=False, publication_acceptance=False))
        self.entered = True
        try:
            self.originals.close(); p.read(self.plan_ref)
            # The owning Parent now guards the exact target's authorized rename
            # and retirement. It re-observes source/census/owner under Writer;
            # the composer must not demand the pre-operation target still exist
            # after a valid terminal operation. Every unrelated file/fact stays
            # in the outer original closure.
            self.originals.refs.pop(self.target)
            result = module.run_operation(self.plan_ref, self.source, engine=module.ScopedDocker(),
                configured=copy.deepcopy(self.configured), nfs_sources=copy.deepcopy(self.nfs_sources),
                nfs_intents=copy.deepcopy(self.document['nfs_intents']))
            self.originals.close(); p.read(self.plan_ref)
            # Preserve the owning return verbatim; it is not a new ACK schema.
            bootstrap.put(self.output / 'owning-return.json', result)
            return result
        except BaseException:
            try:bootstrap.put(self.output / 'held.json', dict(kind='checked-plan13-entry-outcome-unaccepted', automatic_replay=False,
                cleanup=False, reader_resume_authority=False, publication_acceptance=False))
            except Exception:pass
            raise
