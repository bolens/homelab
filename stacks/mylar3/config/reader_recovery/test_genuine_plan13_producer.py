"""Disposable composition/custody controls; never genuine NFS/factory proof.

Facts below are explicit source-mode fixtures, not admitted SourceCohort/ACKs.
The only owning invocation test uses genuine configured Parent and deliberately
refuses BEFORE engine access. No Parent/Birth/SDK object is replaced.
"""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).parent))
import genuine_plan13_producer as g

HERE = Path(__file__).parent


class Fixture:
    def __init__(self, root):
        self.root = root; self.serial = 0; self.nonce = 'a' * 64
        self.state = root / ('archive-bootstrap-' + self.nonce); self.state.mkdir(mode=0o700)
        self.facts = root / 'facts'; self.facts.mkdir(mode=0o700)
        self.output = root / 'installed'; self.output.mkdir(mode=0o700)
        self.common = root / ('archive-publication-' + self.nonce); self.common.mkdir(mode=0o700)
        self.library = self.common / 'L'; self.library.mkdir(mode=0o700)
        self.retention = self.common / 'R'; self.retention.mkdir(mode=0o700)
        self.data = self.state / 'native'; self.data.mkdir(mode=0o700)
        self.scratch = self.state / 'scratch'; self.scratch.mkdir(mode=0o700)
        self.image = 'sha256:' + 'b' * 64; self.worker_image = 'sha256:' + 'c' * 64
        self.refs = {}
        self.installation()
        self.document()

    def put(self, value, *, path=None):
        self.serial += 1
        return g.bootstrap.put(path or self.facts / ('fact-' + str(self.serial) + '.json'), value)

    def raw(self, path, raw):
        path.write_bytes(raw); path.chmod(0o600)
        return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), signature9=g.p.nine(os.lstat(path)))

    def directory(self, path):
        return dict(path=str(path), signature9=g.p.nine(os.lstat(path)))

    def installation(self):
        locators = json.loads((HERE / 'INSTALLER-SOURCE-LOCATORS.json').read_bytes())
        source_paths = {key: (HERE / value).resolve() for key, value in locators.items()}
        source_paths.update({name: HERE / name for name in g.installer.EXPECTED_NFS})
        sources = {key: path.read_bytes() for key, path in source_paths.items()}
        source_refs = {key: dict(path=str(path), sha256=g.installer.sha(sources[key]), signature9=g.p.nine(path.stat())) for key, path in source_paths.items()}
        worker = dict(mode='original-pipes-v1',
            source=self.raw(self.facts / 'archive_terminal_observation.py', (HERE / '_archive_worker_fixtures/archive_terminal_observation.py').read_bytes()),
            image_sources=self.put({'/app/archive_terminal_observation.py': g.installer.WORKER_OBSERVER_SOURCE_SHA}),
            image_metadata=self.put([dict(Id=self.worker_image, Os='linux', Architecture='amd64')]))
        base_path = HERE / 'configured_reader_parent_base_sources.json'
        base = json.loads(base_path.read_bytes())
        sdk_ref = self.put({name: base['base_installed_sources'][name] for name in base['required_sdk_names']})
        self.base_manifest = dict(path=str(base_path), sha256=g.installer.sha(base_path.read_bytes()), signature9=g.p.nine(base_path.stat()))
        self.base_admission = self.raw(self.facts / 'base-admission.py', sources['admission'])
        artifacts, receipt = g.installer.build({key: sources[key] for key in g.installer.EXPECTED},
            str(self.output / 'comic_reader_lifecycle_parent.py'), worker_observation=worker, worker_image=self.worker_image)
        sdk, cohort = g.installer.configured_maps(g.p.decode(g.p.read(sdk_ref)), base_path.read_bytes(), artifacts, receipt)
        blobs = {**artifacts, **g.installer.build_nfs({key: sources[key] for key in g.installer.EXPECTED_NFS}),
            'publication_reader_admission.overlay.py': artifacts['publication_reader_admission.py'],
            'configured-sdk-map.json': g.installer_json(sdk), 'configured-cohort.json': g.installer_json(cohort)}
        self.original_source_refs = source_refs
        receipt.update(original_source_refs=source_refs, base_sdk_ref=sdk_ref, worker_observation_profile=worker,
            worker_observation_image=self.worker_image, worker_observation_installed_parity_verified=False,
            nfs_session_admission_proven=False, actual_overlay_origins_verified=False,
            effective_sdk_map_sha256=g.installer.sha(blobs['configured-sdk-map.json']), effective_cohort_sha256=g.installer.sha(blobs['configured-cohort.json']))
        blobs['configured-source-observation.json'] = g.installer_json(receipt)
        self.refs = {name: self.raw(self.output / name, raw) for name, raw in blobs.items()}
        self.install_ref = self.put(dict(output=str(self.output), prepared=True, lifecycle_performed=False,
            configured_admission_proven=False, root_signature5=list(g.p.five(self.output.stat())),
            output_refs={ref['path']: ref for ref in self.refs.values()}))

    def nfs(self):
        originals = {}
        def pair(ref):
            originals[ref['path']] = ref
            return {key: ref[key] for key in ('path', 'sha256')}
        def fact(value):return pair(self.put(value))
        query = fact(dict(version=1, kind='approved-active-komga-library-query',
            configuration=fact(dict(komga=dict(url='http://reader:25600', api_key='fixture-only'))), expected_base_url='http://reader:25600'))
        scope = fact(dict(sources=dict(current_komga_libraries=query), forbidden_roots=[str(self.data)]))
        cohort = fact(dict(images=dict(native=self.image, selected=self.image, reader=self.image, worker=self.worker_image),
            sources={str(n): fact(dict(fixture=n)) for n in range(16)}, logs={name: fact(dict(fixture=name)) for name in ('stdout', 'stderr')},
            parent=pair(self.original_source_refs['comic_negative_nfs_active_parent.py']), receipt=fact(dict(source_mode_fixture=True))))
        review = {}
        for role in g.EFFECTIVE:
            review[role] = fact(dict(config_files={}, absent_config_files=[], optional_absent_scopes={}, scopes={}) if role == 'report' else dict(source_mode_fixture=role))
        active = self.put(dict(version=1, kind='approved-active-nfs-owned-lifecycle', active_scope=scope,
            parent_admission={}, probe_plan={}, operation_output=str(self.state / 'nfs-output'), native_controls=fact({}),
            effective_observer_review=fact(review), source_cohort=cohort))
        return active, originals

    def document(self):
        now = int(time.time())
        roles = {}
        for index, role in enumerate(('native', 'reader', 'worker')):
            image = self.worker_image if role == 'worker' else self.image
            cid = str(index + 1) * 64
            profile = dict(Id=cid, Image=image, Name='/archive-bootstrap-' + self.nonce[:16] + '-' + role,
                Path='fixture', Args=[], Config=dict(Labels={g.bootstrap.LABEL: self.nonce, g.bootstrap.PURPOSE: 'genuine-archive-fixture'}), HostConfig={}, Mounts=[], NetworkSettings={})
            roles[role] = dict(id=cid, image=image, profile=profile, epoch=dict(source_mode_fixture=True))
        ini = self.put({}, path=self.data / 'config.ini')
        geometry = dict(version=1, kind='private-common-root-nfs', common_root=self.directory(self.common),
            library=self.directory(self.library), retention=self.directory(self.retention))
        old = dict(kind='approved-disposable-application-bootstrap', nonce=self.nonce, roles=roles,
            images={key: value['image'] for key, value in roles.items()}, geometry=geometry,
            state_root=self.directory(self.state), native_ini=ini)
        files = []
        for index, role in enumerate(('target', 'unrelated')):
            ref = self.raw(self.library / (role + '.cbz'), ('source-mode-' + role).encode())
            files.append(dict(ref, role=role, owner=dict(table='issues', issueid=str(index + 1), parentcomicid=str(index + 3), releasecomicid=str(index + 3)), pages=['d' * 64]))
        process = dict(process=dict(pid=123, started='fixture'), config=ini)
        catalog = dict(version=1, kind='disposable-native-catalog-processing-observation', nonce=self.nonce,
            native_CID=roles['native']['id'], native_image=self.image, process=process, files=files,
            native_catalog_processing_observed=True, ordinary_ack_verified=False, birth_verified=False,
            daemon_operation_identity=False, **{key: False for key in g.RIGHTS})
        catalog_ref = self.put(catalog)
        reader = dict(library=dict(root=str(self.library)), books=[dict(path=row['path'], hashes=row['pages']) for row in files])
        bracket = dict(kind='original-reader-task-empty-bracket', nonce=self.nonce, reader_image=self.image,
            observation=dict(queue_empty_observed=True), roles=dict(profiles={key: value['profile'] for key, value in roles.items()},
            epochs={key: value['epoch'] for key, value in roles.items()}, reader=reader),
            **{key: False for key in ('application_quiescence_verified', 'future_exclusion_verified', 'stop_authority',
                'reader_resume_authority', 'publication_acceptance', 'mutation_authority', 'ordinary_ack_verified')})
        result = dict(kind='disposable-application-bootstrap-observation', nonce=self.nonce,
            native_catalog_processing=catalog_ref, native_catalog_processing_observed=True,
            reader=reader, reader_task_empty_observation=bracket, ordinary_ack_verified=False, **{key: False for key in g.RIGHTS})
        active, originals = self.nfs()
        self.doc = dict(version=1, kind='disposable-original-plan13-input', nonce=self.nonce, observed=now, seconds=60,
            bootstrap_plan=self.put(old), bootstrap_result=self.put(result), catalog=catalog_ref,
            installation=self.install_ref, base_manifest=self.base_manifest,
            base_admission=self.base_admission,
            current_roles=self.put(dict(nonce=self.nonce, observed=now, roles=roles, native_process=process)),
            publication_geometry=dict(geometry, library=self.directory(self.library)),
            native=dict(data='/fixture-native', roots=[str(self.library)]),
            mounts=[dict(host=str(path), child=child, write=True) for path, child in (
                (self.common, str(self.common)), (self.data, '/fixture-native'), (self.scratch, '/scratch'), (self.state / 'operation', '/_operation'))],
            bounds={}, operation=str(self.state / 'operation'),
            archive_request=self.put(dict(version=2, owner=files[0]['owner'], operation_id='e' * 64, terminal='forward')),
            archive_scopes=self.put(dict(version=1, scratch=str(self.scratch), retention_root=str(self.retention))),
            nfs_active_input=active, nfs_intents=self.put(dict(source_mode_fixture=True)), originals=originals,
            selected_image_metadata=self.put([dict(Id=self.image, Os='linux', Architecture='amd64', Config={})]),
            observer=self.raw(self.facts / 'comic_archive_terminal_vectors.py', (HERE / 'comic_archive_terminal_vectors.py').read_bytes()))

    def compose(self, doc=None):
        frame = g.Originals()
        installation = g.checked_installation(frame, self.install_ref, self.base_manifest)
        return g.compose(copy.deepcopy(self.doc if doc is None else doc), frame, installation), frame


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.f = Fixture(self.root)

    def test_exact_checked_derivation_and_plan13_composition_no_effect(self):
        (plan, source, configured, nfs), frame = self.f.compose()
        self.assertEqual(plan['version'], 13); self.assertEqual(plan['terminal_mode'], 'same-child-v1')
        self.assertEqual(plan['producer_inputs']['archive_request'], self.f.doc['archive_request'])
        self.assertEqual(source, self.f.refs['comic_reader_lifecycle_parent.py'])
        self.assertEqual(configured['cohort'], self.f.refs['configured-cohort.json'])
        self.assertEqual(nfs, {name: self.f.refs[name] for name in g.p.NFS_HOST_SOURCE_PINS})
        self.assertEqual(len(nfs), 8)
        self.assertEqual(plan['observer'], self.f.doc['observer'])
        self.assertFalse(Path(plan['operation']).exists()); frame.close()

    def test_cohort_parent_is_original_canonical_source_not_derived_output(self):
        (plan, _, _, _), frame=self.f.compose()
        self.assertNotEqual(self.f.original_source_refs['comic_negative_nfs_active_parent.py']['path'],self.f.refs['comic_negative_nfs_active_parent.py']['path'])
        self.assertEqual(plan['nfs']['active_parent'],self.f.refs['comic_negative_nfs_active_parent.py']);frame.close()

    def test_cohort_foreign_original_path_or_hash_refuses(self):
        for change in ('path','hash'):
            frame=g.Originals();installation=g.checked_installation(frame,self.f.install_ref,self.f.base_manifest)
            original=installation['receipt']['original_source_refs']['comic_negative_nfs_active_parent.py']
            original['path' if change=='path' else 'sha256']='/different/original.py' if change=='path' else '0'*64
            with self.assertRaisesRegex(g.p.Held,'producer-cohort-owning-parent-original'):g.compose(copy.deepcopy(self.f.doc),frame,installation)

    def test_tampered_installed_parent_derivative_refuses_original_join(self):
        frame=g.Originals();installation=g.checked_installation(frame,self.f.install_ref,self.f.base_manifest)
        installation['refs']['comic_negative_nfs_active_parent.py']['sha256']='0'*64
        with self.assertRaisesRegex(g.p.Held,'producer-cohort-owning-parent-original'):g.compose(copy.deepcopy(self.f.doc),frame,installation)

    def searchable(self):
        old=g.p.decode(g.p.read(self.f.doc['bootstrap_plan']));self.f.common.chmod(0o711)
        geometry=dict(self.f.doc['publication_geometry'],version=2,kind='searchable-common-root-nfs',common_root=self.f.directory(self.f.common))
        old['geometry']=copy.deepcopy(geometry);self.f.doc['bootstrap_plan']=self.f.put(old);self.f.doc['publication_geometry']=geometry

    def test_real_searchable_common711_geometry_composes(self):
        self.searchable();(plan,_,_,_),frame=self.f.compose()
        self.assertEqual(plan['publication_geometry']['common_root']['signature9'][5]&0o777,0o711);frame.close()

    def test_wrong_geometry_kind_and_legacy_common711_refuse(self):
        self.searchable()
        for version,kind in ((2,'unknown'),(1,'private-common-root-nfs')):
            doc=copy.deepcopy(self.f.doc);doc['publication_geometry'].update(version=version,kind=kind)
            with self.assertRaises(g.p.Held):self.f.compose(doc)

    def test_searchable_leaf711_refuses(self):
        self.searchable();self.f.library.chmod(0o711);self.f.doc['publication_geometry']['library']=self.f.directory(self.f.library)
        with self.assertRaises(g.p.Held):self.f.compose()

    def test_changed_installed_bytes_never_adopted_even_new_hash(self):
        path = Path(self.f.refs['comic_archive_repair_action.py']['path']); path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaises(g.p.Held):self.f.compose()

    def test_original_installed_output_same_bytes_recreated_is_not_adopted(self):
        original=self.f.refs['comic_archive_repair_action.py']
        path=Path(original['path']);raw=path.read_bytes()
        path.rename(self.root/'retained-old-action.py')
        replacement=self.f.raw(path,raw)
        self.assertEqual(replacement['sha256'],original['sha256'])
        self.assertNotEqual(replacement['signature9'],original['signature9'])
        with self.assertRaises(g.p.Held):self.f.compose()

    def test_extra_installed_namespace_refuses(self):
        (self.f.output / 'unexpected').write_text('x')
        with self.assertRaisesRegex(g.p.Held, 'exact-namespace'):self.f.compose()

    def test_missing_fact_refuses_before_plan_or_operation(self):
        doc = copy.deepcopy(self.f.doc); doc['originals'].pop(next(iter(doc['originals'])))
        with self.assertRaisesRegex(g.p.Held, 'missing-original-fact'):self.f.compose(doc)
        self.assertFalse(Path(doc['operation']).exists())

    def test_fact_pin_crossjoin_refuses(self):
        doc = copy.deepcopy(self.f.doc); next(iter(doc['originals'].values()))['sha256'] = 'f' * 64
        with self.assertRaisesRegex(g.p.Held, 'original-fact-pin'):self.f.compose(doc)

    def test_changed_original_after_composition_refuses(self):
        _, frame = self.f.compose()
        Path(self.f.doc['nfs_intents']['path']).write_text('changed')
        with self.assertRaises(g.p.Held):frame.close()

    def test_unscoped_fact_refuses(self):
        doc = copy.deepcopy(self.f.doc); ref = self.f.put({'foreign': True}); doc['originals'][ref['path']] = ref
        with self.assertRaisesRegex(g.p.Held, 'no-unscoped'):self.f.compose(doc)

    def test_stale_request_and_changed_nonce_refuse(self):
        for change in (dict(observed=int(time.time()) - 121), dict(nonce='f' * 64)):
            doc = dict(self.f.doc, **change)
            with self.subTest(change=change), self.assertRaises(g.p.Held):self.f.compose(doc)

    def test_other_native_target_owner_refuses(self):
        doc = dict(self.f.doc, archive_request=self.f.put(dict(version=2, owner={}, operation_id='e' * 64, terminal='forward')))
        with self.assertRaisesRegex(g.p.Held, 'original-target-request'):self.f.compose(doc)

    def test_private_original_base_admission_required_and_exact(self):
        doc = dict(self.f.doc, base_admission=self.f.put({'not': 'base-admission'}))
        with self.assertRaisesRegex(g.p.Held, 'base-admission-pin'):self.f.compose(doc)
        source = g.p.decode(g.p.read(self.f.install_ref))['output_refs']
        self.assertNotEqual(self.f.doc['base_admission'], source[str(self.f.output / 'publication_reader_admission.py')])

    def test_wrong_fresh_process_refuses(self):
        current = g.p.decode(g.p.read(self.f.doc['current_roles'])); current['native_process'] = {}
        with self.assertRaisesRegex(g.p.Held, 'current-process-original'):self.f.compose(dict(self.f.doc, current_roles=self.f.put(current)))

    def test_wrong_reader_page_hash_refuses(self):
        result = g.p.decode(g.p.read(self.f.doc['bootstrap_result'])); result['reader']['books'][0]['hashes'] = []
        # Keep its original bracket equal so this tests the page/native join.
        result['reader_task_empty_observation']['roles']['reader'] = copy.deepcopy(result['reader'])
        with self.assertRaisesRegex(g.p.Held, 'reader-native-output-join'):self.f.compose(dict(self.f.doc, bootstrap_result=self.f.put(result)))

    def test_geometry_cannot_be_adopted_by_same_name(self):
        doc = copy.deepcopy(self.f.doc); old = self.f.retention; old.rename(old.with_name('old-R')); old.mkdir(mode=0o700)
        doc['publication_geometry']['retention'] = self.f.directory(old)
        doc['publication_geometry']['common_root'] = self.f.directory(self.f.common)
        with self.assertRaisesRegex(g.p.Held, 'geometry-identity'):self.f.compose(doc)

    def test_missing_queue_observation_does_not_infer_exclusion(self):
        result = g.p.decode(g.p.read(self.f.doc['bootstrap_result'])); result.pop('reader_task_empty_observation')
        with self.assertRaisesRegex(g.p.Held, 'queue-observation-required'):self.f.compose(dict(self.f.doc, bootstrap_result=self.f.put(result)))

    def test_replaced_source_same_bytes_still_refuses(self):
        _, frame = self.f.compose(); path = Path(self.f.doc['observer']['path']); raw = path.read_bytes()
        path.unlink(); path.write_bytes(raw); path.chmod(0o600)
        with self.assertRaises(g.p.Held):frame.close()

    def test_missing_inputs_do_not_prepare_or_install(self):
        output = self.root / 'attempt'
        with self.assertRaises(g.p.Held):g.Producer(self.f.put({}), output)
        self.assertFalse(output.exists())

    def test_execute_disabled_and_old_output_never_adopted(self):
        owner = g.Producer(self.f.put(self.f.doc), self.root / 'attempt')
        with self.assertRaisesRegex(g.p.Held, 'explicit-root-activation'):owner.execute()
        owner.output.mkdir(mode=0o700)
        with self.assertRaisesRegex(g.p.Held, 'no-replay'):owner._enter()

    def test_late_original_loss_refuses_before_planwrite(self):
        owner = g.Producer(self.f.put(self.f.doc), self.root / 'attempt')
        Path(self.f.doc['nfs_intents']['path']).unlink()
        with self.assertRaises(FileNotFoundError):owner._enter()
        self.assertFalse(owner.output.exists())

    def test_real_owning_constructor_refusal_is_retained_no_replay(self):
        owner = g.Producer(self.f.put(self.f.doc), self.root / 'attempt')
        # This source-mode fixture has no genuine native Writer directory.
        # Owning constructor refuses during original-lock admission, before
        # inspect or operation creation. No Parent or engine is doubled.
        with self.assertRaises(FileNotFoundError) as refusal:owner._enter()
        self.assertEqual(refusal.exception.filename, str(self.f.data / 'media-writer'))
        self.assertTrue((owner.output / 'entry-intent.json').is_file())
        self.assertTrue((owner.output / 'held.json').is_file())
        self.assertFalse(Path(self.f.doc['operation']).exists())
        with self.assertRaisesRegex(g.p.Held, 'no-replay'):owner._enter()
        self.assertFalse((owner.output / 'owning-return.json').exists())

    def test_mutated_derived_plan_refuses_before_writes(self):
        owner = g.Producer(self.f.put(self.f.doc), self.root / 'attempt'); owner.plan['version'] = 12
        with self.assertRaisesRegex(g.p.Held, 'derived-inputs-changed'):owner._enter()
        self.assertFalse(owner.output.exists())

    def test_exact_owning_entry_no_callback_or_install_in_execute(self):
        tree = ast.parse(Path(g.__file__).read_text(), feature_version=(3, 10))
        enter = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == '_enter')
        calls = [node for node in ast.walk(enter) if isinstance(node, ast.Call)]
        owning = [node for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr == 'run_operation']
        self.assertEqual(len(owning), 1)
        self.assertEqual({keyword.arg for keyword in owning[0].keywords}, {'engine', 'configured', 'nfs_sources', 'nfs_intents'})
        self.assertFalse(any(isinstance(node.func, ast.Attribute) and node.func.attr == 'install' for node in calls))


if __name__ == '__main__':unittest.main()
