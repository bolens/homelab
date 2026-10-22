"""Original graph assembly controls; synthetic evidence never proves NFS/factories."""
import ast
import copy
import hashlib
import importlib.util
import os
import stat
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import genuine_active_inputs as g


# Exact predecessor parent block; immutable RED evidence, not a production loader.
LEGACY_PARENT_BLOCK = "parent = p.absolute(probe['fixture_parent']); stamp = p.nine(os.lstat(parent))\nneed(stamp == probe['fixture_parent_signature'] and stat.S_ISDIR(stamp[5])\n     and stamp[0] == probe['expected_device'] == os.lstat(probe['library_root']).st_dev, 'active-original-probe-parent')\nself.remember(p.parents(parent)); self.remember({str(parent): p.five(os.lstat(parent))})\n"
LEGACY_PARENT_BLOCK_SHA256 = 'e721c5628b79a514c42f866d933b58cb255d05bdc3b2e03290dce92b1f6edb77'

def owning_precreation(outer, roots, library):
    """Execute the exact owning Parent block and genuine lifecycle method.

    Only mount observation/role selection/emission are explicit test doubles;
    all directory absence/full9/NFS-choice/creation predicates are genuine.
    This local disposable filesystem is not actual NFS acceptance.
    """
    import comic_negative_nfs_active_lifecycle as lifecycle
    source = Path(g.active.__file__).read_text(); tree = ast.parse(source)
    body = next(n.body for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_run_owned_lifecycle')
    first = next(i for i,n in enumerate(body) if isinstance(n, ast.Assign) and any(isinstance(t,ast.Name) and t.id=='core' for t in n.targets))
    last = next(i for i,n in enumerate(body[first:],first) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Subscript) and isinstance(t.value,ast.Name) and t.value.id=='core' for t in n.targets))
    selected = ast.Module(body=body[first:last+1], type_ignores=[])
    scope = dict(Path=Path, outer=outer, roots=roots, initial={'mapping':'explicit-role-double'}, roles=None,
        selected_library_root=lambda mapping,roles:library, canonical=g.active.canonical,
        stamp=g.active.stamp, observe_mount=lambda path:outer['probe_plan']['mount_identity'],
        check=g.active.check, output=Path(outer['operation_output']), module=lifecycle,
        gated=True, ancestors={}, emit=lambda *args:None)
    exec(compile(selected,str(Path(g.active.__file__)),'exec'),scope)
    return scope['parent'],scope['core']


class Fixture:
    def __init__(self, root, config_ref=None):
        self.root = root; self.refs = {}; self.serial = 0; self.nonce = 'a' * 64
        self.facts = root / 'facts'; self.facts.mkdir(mode=0o700)
        self.nfs = root / 'nfs'; self.nfs.mkdir(mode=0o700)
        self.library = self.nfs / 'L'; self.library.mkdir(mode=0o700)
        self.config = root / 'config'; self.config.mkdir(mode=0o700)
        self.index = self.config / 'index'; self.index.mkdir(mode=0o700)
        self.fonts = self.config / 'fonts'
        self.native = root / 'native'; self.native.mkdir(mode=0o700)
        self.grandparent = self.nfs / 'R'; self.grandparent.mkdir(mode=0o700)
        self.parent = self.grandparent / ('.comic-nfs-private-' + 'c' * 32)
        self.output_parent = root / 'outputs'; self.output_parent.mkdir(mode=0o700)
        self.output = self.output_parent / 'assembled'
        now = int(time.time()); images = {role: 'sha256:' + str(n) * 64 for n, role in enumerate(('native', 'reader', 'worker'), 1)}
        self.roles = {}
        for n, role in enumerate(('native', 'reader', 'worker'), 1):
            cid = str(n) * 64
            state = dict(Status='created' if role == 'worker' else 'running', Running=role != 'worker', Pid=0 if role == 'worker' else 100 + n, StartedAt='original-epoch', Paused=False, Restarting=False)
            profile = dict(Id=cid, Image=images[role], Name='/archive-bootstrap-' + self.nonce[:16] + '-' + role,
                Path='original-disposable', Args=[], Config=dict(Labels={g.composer.bootstrap.LABEL: self.nonce, g.composer.bootstrap.PURPOSE: 'genuine-archive-fixture'}),
                HostConfig={}, Mounts=[], NetworkSettings={})
            self.roles[role] = dict(id=cid, image=images[role], profile=profile, epoch=state)
        current = self.fact(dict(nonce=self.nonce, observed=now, roles=self.roles, native_process=dict(process='explicit-source-fixture')))
        self.current = current
        cfg = self.fact(dict(komga=dict(url='http://reader:25600', api_key='disposable-fixture-key')))
        self.query = self.fact(dict(version=1, kind='approved-active-komga-library-query', configuration=g.pair(cfg), expected_base_url='http://reader:25600'))
        reader = self.roles['reader']; service = dict(reader['profile'], State=reader['epoch'])
        runtime = self.fact(dict(kind='reviewed-komga-effective-scope-runtime', observed=now, container=service, pid=102, start_time=456, jar_sha256='b' * 64, source_commit='c' * 40))
        producer = self.raw('producer.class', b'explicit source-mode compiled fixture')
        parent_source = self.raw('parent.py', b'# explicit source-mode parent fixture\n')
        database = self.config / 'main.sqlite'; database.write_bytes(b'source-fixture-only')
        tasks = self.config / 'tasks.sqlite'; tasks.write_bytes(b'source-fixture-only')
        scopes = {k: dict(host_path=str(v)) for k, v in dict(config=self.config, database=database, tasks=tasks, index=self.index, fonts=self.fonts).items()}
        identities = {str(v): list(g.p.five(v.lstat())) for v in (self.config, database, tasks, self.index)}
        config_files = {}
        if config_ref is not None:
            self.refs[config_ref['path']] = config_ref
            config_files[config_ref['path']] = {k: config_ref[k] for k in ('sha256', 'signature9')}
        report = self.fact(dict(kind='komga-effective-persistent-scope-observation', image=images['reader'], container_id=reader['id'], pid=102, start_time=456,
            jar_sha256='b' * 64, source_commit='c' * 40, runtime_sha256=runtime['sha256'], source_sha256=producer['sha256'], scope_observation_verified=False, final_ack_required=True,
            scopes=scopes, scope_presence={k: k != 'fonts' for k in scopes}, scope_identities=identities,
            optional_absent_scopes={str(self.fonts): dict(nearest_existing_ancestor=str(self.config), ancestor_identity=list(g.p.five(self.config.lstat())))}, config_files=config_files, absent_config_files=[]))
        rights = {k: False for k in g.RIGHTS}
        ack = self.fact(dict(scope_observation_verified=True, report_sha256=report['sha256'], **rights))
        acceptance = self.fact(dict(kind='accepted-komga-effective-scope', scope_observation_verified=False, final_ack_required=True, same_process_verified=True,
            report_sha256=report['sha256'], source_sha256=parent_source['sha256'], helper_sha256=producer['sha256'], **rights))
        parent_ack = self.fact(dict(scope_observation_verified=True, same_process_verified=True, report_sha256=report['sha256'], acceptance_sha256=acceptance['sha256'], **rights))
        review = self.fact({k: g.pair(v) for k, v in dict(producer=producer, parent_source=parent_source, report=report, ack=ack, runtime=runtime, acceptance=acceptance, parent_ack=parent_ack).items()})
        self.review = review
        sources = {role: g.pair(self.fact(dict(explicit_source_fixture=role))) for role in g.cohort_source.ROLES}
        sources.update(effective_helper=g.pair(producer), effective_parent=g.pair(parent_source))
        logs = {name: g.pair(self.raw(name + '.log', b'explicit source-mode log')) for name in ('stdout', 'stderr')}
        cohort_parent = self.raw('cohort-parent.py', b'# source-mode fixture\n')
        cimages = dict(images, selected=images['native'])
        receipt = self.fact(dict(kind='owned-nfs-current-source-fixture-readiness', images=cimages, parent_sha256=cohort_parent['sha256'],
            source_pins={k: v['sha256'] for k, v in sources.items()}, exit_code=0, zero_skips=True, count=1, **{k: False for k in g.cohort_source.RIGHTS}))
        cohort = self.fact(dict(version=1, kind='approved-disposable-nfs-current-source-cohort', images=cimages, sources=sources, logs=logs, parent=g.pair(cohort_parent), receipt=g.pair(receipt)))
        # Discard overwritten unused source fixture references from the finite graph.
        used_source_paths = {x['path'] for x in sources.values()}
        for path in tuple(self.refs):
            value = g.p.decode(g.p.read(self.refs[path])) if path.endswith('.json') else {}
            if type(value) is dict and value.get('explicit_source_fixture') in ('effective_helper', 'effective_parent') and path not in used_source_paths:self.refs.pop(path)
        scope_sources = {name: g.pair(self.fact(dict(explicit_source_fixture=name))) for name in ('current_mylar_hold', 'current_worker_created', 'protected_catalog_cache_recovery_scope', 'continuous_raw_writer_lease')}
        scope_sources.update(current_runtime_bracket=g.pair(current), current_komga_libraries=g.pair(self.query), current_komga_effective_scope=g.pair(report))
        scope = self.fact(dict(version=2, kind='root-reviewed-nfs-active-disposable-scope', approved_disposable_diagnostic=True, observed=now,
            current_active_scanner_publication_paths_reviewed=True, future_mylar_destination_verified=False, future_mylar_destination=None,
            writer_lifecycle_resume_authorized=False, forbidden_roots=[str(self.library), str(self.config)], sources=scope_sources))
        self.scope = scope
        mount = dict(source='source-fixture:/export', target=str(self.nfs), fstype='nfs4', fsroot='/', options='rw,source-fixture', **{'maj:min': '0:123'})
        device = self.library.lstat().st_dev
        probe = dict(version=2, kind='approved-negative-nfs-active-probe-parent', scope=g.pair(scope), fixture_parent=str(self.parent), fixture_name='.comic-nfs-probe-' + 'd' * 32,
            fixture_parent_signature=None, library_root=str(self.library), expected_device=device, mount_identity=mount, output_root=str(self.output_parent / 'nfs-operation' / 'probe'))
        self.document = dict(version=1, kind='disposable-original-active-input-assembly', nonce=self.nonce, observed=now, current_roles=current,
            active_scope=scope, query=self.query, native_controls=receipt, effective_observer_review=review, source_cohort=cohort,
            parent_admission=dict(path=str(self.parent), grandparent_signature=g.p.nine(self.grandparent.lstat()), expected_device=device, mount_identity=mount), probe_plan=probe, operation_output=str(self.output_parent / 'nfs-operation'),
            originals=self.refs, sources={name: self.ref(Path(module.__file__).absolute()) for name, module in {
                'genuine_active_inputs.py': g, 'genuine_plan13_producer.py': g.composer,
                'comic_negative_nfs_active_parent.py': g.active, 'genuine_source_cohort.py': g.cohort_source}.items()})

    def ref(self, path):return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), signature9=g.p.nine(path.lstat()))
    def raw(self, name, raw):
        path = self.facts / name; path.write_bytes(raw); path.chmod(0o600); ref = self.ref(path); self.refs[str(path)] = ref; return ref
    def fact(self, value):
        self.serial += 1
        return self.raw('fact-' + str(self.serial) + '.json', g.p.encode(value))
    def request(self):
        return self.raw('request.json', g.p.encode(self.document))
    def change(self, role, modify):
        old = self.document[role]; value = g.p.decode(g.p.read(old)); modify(value)
        ref = self.fact(value); self.refs.pop(old['path']); self.document[role] = ref
        return ref


def empty_producer_stderr(f):
    """Genuine emitter payload shape; supplied facts are disposable doubles only."""
    import genuine_source_cohort as emitter
    cohort = g.p.decode(g.p.read(f.document['source_cohort']))
    old_receipt = cohort['receipt']; stderr = f.raw('stderr.log', b'')
    logs = dict(cohort['logs'], stderr=g.pair(stderr)); cohort['logs'] = logs
    receipt = f.fact(emitter.payload(cohort, g.pair(f.query), g.pair(f.query),
        dict(tests=1), logs['stdout'], logs['stderr']))
    f.refs.pop(old_receipt['path'])
    f.document['native_controls'] = receipt
    f.change('source_cohort', lambda value:value.update(logs=logs, receipt=g.pair(receipt)))
    return stderr


class ActiveInputsTests(unittest.TestCase):
    def fixture(self):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        return Fixture(Path(directory.name))

    def request(self, f):
        # The assembly request is an original, not part of its nested graph.
        ref = f.request(); f.refs.pop(ref['path']); return ref

    def test_genuine_composer_consumes_fresh_graph_without_grants(self):
        f = self.fixture(); ref = self.request(f); owner = g.Assembly(ref, f.output)
        original = os.listdir; seen = []
        def census(fd):
            if fd == owner.fd:
                # Model the observed Btrfs stale persistent-description census.
                return []
            if isinstance(fd, int) and owner.fd is not None:
                self.assertEqual(g.p.five(os.fstat(fd)), owner.output5)
                seen.append(fd)
            return original(fd)
        try:
            with patch.object(g.os, 'listdir', side_effect=census):result = owner.execute()
            self.assertTrue(seen)
            for fd in set(seen):
                with self.assertRaises(OSError):os.fstat(fd)
        finally:owner.release()
        originals = g.composer.Originals(); active, docs = g.composer.nested_originals(originals, result['active_input'], result['originals']); originals.close()
        self.assertEqual(active['probe_plan'], f.document['probe_plan']); self.assertEqual(docs['effective_observer_review'], g.p.decode(g.p.read(f.review)))
        for key in ('publication_acceptance', 'actual_nfs_verified', 'installed_factories_verified', 'mutation_authority', 'automatic_replay'):self.assertIs(result[key], False)
        self.assertEqual(set(x.name for x in f.output.iterdir()), {'active-input.json', 'composer-inputs.json'})

    def test_genuine_empty_stderr_crosses_assembly_composer_and_original_close(self):
        f = self.fixture(); stderr = empty_producer_stderr(f); original = copy.deepcopy(stderr)
        with self.assertRaises(g.p.Held):g.p.read(stderr)
        result = g.assemble(self.request(f), f.output)
        originals = g.composer.Originals()
        try:
            _, docs = g.composer.nested_originals(originals, result['active_input'], result['originals'])
            self.assertEqual(docs['source_cohort']['logs']['stderr'], g.pair(stderr))
            self.assertEqual(originals.read_cohort_stderr(f.document['source_cohort'], stderr), b'')
            originals.close()
        finally:originals.close()
        self.assertEqual(f.ref(Path(stderr['path'])), original)
        self.assertEqual(Path(stderr['path']).read_bytes(), b'')
        for flag in ('publication_acceptance','actual_nfs_verified','installed_factories_verified','mutation_authority','automatic_replay'):
            self.assertIs(result[flag], False)

    def test_empty_stderr_role_policy_and_private_mode_remain_strict(self):
        f = self.fixture(); stderr = empty_producer_stderr(f); cohort_ref = f.document['source_cohort']
        self.assertEqual(g.p.read_cohort_stderr(cohort_ref, stderr), b'')
        ordinary = f.raw('ordinary-empty.json', b'')
        with self.assertRaises(g.p.Held):g.p.read(ordinary)
        with self.assertRaisesRegex(g.p.Held, 'cohort-empty-stderr-role'):g.p.read_cohort_stderr(cohort_ref, ordinary)
        bad = dict(stderr, sha256='0'*64)
        with self.assertRaisesRegex(g.p.Held, 'cohort-empty-stderr-role'):g.p.read_cohort_stderr(cohort_ref, bad)
        Path(stderr['path']).chmod(0o400)
        changed = f.ref(Path(stderr['path']))
        with self.assertRaisesRegex(g.p.Held, 'ref-attributes'):g.p.read_cohort_stderr(cohort_ref, changed)

    def test_late_empty_stderr_or_original_cohort_change_refuses(self):
        for role in ('stderr','cohort'):
            with self.subTest(role=role):
                f = self.fixture(); stderr = empty_producer_stderr(f)
                owner = g.Assembly(self.request(f), f.output)
                try:
                    path = Path(stderr['path'] if role == 'stderr' else f.document['source_cohort']['path'])
                    path.chmod(0o400); path.chmod(0o600)
                    with self.assertRaises(g.p.Held):owner.execute()
                finally:owner.release()
                self.assertFalse(f.output.exists())

    def test_missing_unknown_and_conflicting_facts_refuse_before_output(self):
        for change in ('missing', 'unknown', 'conflict'):
            with self.subTest(change=change):
                f = self.fixture()
                if change == 'missing':f.refs.pop(f.query['path'])
                elif change == 'unknown':f.fact(dict(unreviewed=True))
                else:f.refs[f.query['path']] = dict(f.query, sha256='0' * 64)
                ref = self.request(f)
                with self.assertRaises(ValueError):g.assemble(ref, f.output)
                self.assertFalse(f.output.exists())

    def test_expired_or_foreign_nonce_and_roles_refuse(self):
        for change in ('expired', 'nonce', 'image', 'role'):
            with self.subTest(change=change):
                f = self.fixture()
                if change == 'expired':f.document['observed'] -= 121
                if change == 'nonce':f.document['nonce'] = 'f' * 64
                if change in ('image', 'role'):
                    f.change('current_roles', lambda v: v['roles']['reader'].update(**({'image': 'sha256:' + 'f' * 64} if change == 'image' else {'id': v['roles']['native']['id']})))
                    # Original runtime bracket deliberately remains the previous reference.
                ref = self.request(f)
                with self.assertRaises(ValueError):g.assemble(ref, f.output)
                self.assertFalse(f.output.exists())

    def test_public0644_original_source_roles_remain_original_and_accepted(self):
        f=self.fixture()
        review=g.p.decode(g.p.read(f.review));cohort=g.p.decode(g.p.read(f.document['source_cohort']))
        selected=[review['producer'],review['parent_source'],cohort['sources']['probe'],cohort['parent']]
        for pair in selected:
            path=Path(pair['path']);path.chmod(0o644);f.refs[str(path)]['signature9']=g.p.nine(path.lstat())
        result=g.assemble(self.request(f),f.output)
        for pair in selected:self.assertEqual(result['originals'][pair['path']]['signature9'][5]&0o777,0o644)
        self.assertFalse(result['actual_nfs_verified'])

    def test_public_mode_is_not_allowed_for_private_log(self):
        f=self.fixture();cohort=g.p.decode(g.p.read(f.document['source_cohort']));pair=cohort['logs']['stdout']
        path=Path(pair['path']);path.chmod(0o644);f.refs[str(path)]['signature9']=g.p.nine(path.lstat())
        with self.assertRaises(g.p.Held):g.assemble(self.request(f),f.output)
        self.assertFalse(f.output.exists())

    def test_late_public_source_change_refuses_with_original_full9(self):
        f=self.fixture();review=g.p.decode(g.p.read(f.review));path=Path(review['producer']['path'])
        path.chmod(0o644);f.refs[str(path)]['signature9']=g.p.nine(path.lstat())
        owner=g.Assembly(self.request(f),f.output)
        try:
            path.write_bytes(b'changed-public-source')
            with self.assertRaises(g.p.Held):owner.execute()
        finally:owner.release()
        self.assertFalse(f.output.exists())
        # A genuinely loaded same-byte dependency may have its own original URI;
        # its original full9 still refuses later source mutation before output.
        f = self.fixture(); source = f.root / 'genuine_plan13_producer.py'
        source.write_bytes(Path(g.composer.__file__).read_bytes()); source.chmod(0o600)
        spec = importlib.util.spec_from_file_location('genuine_plan13_producer', source)
        module = importlib.util.module_from_spec(spec); exec(compile(source.read_bytes(), str(source), 'exec'), module.__dict__)
        f.document['sources']['genuine_plan13_producer.py'] = f.ref(source)
        with patch.object(g, 'composer', module), patch.dict(sys.modules, {'genuine_plan13_producer': module}):
            owner = g.Assembly(self.request(f), f.output)
            try:
                source.write_bytes(b'changed-owning-dependency')
                with self.assertRaises(g.p.Held):owner.execute()
            finally:owner.release()
        self.assertFalse(f.output.exists())

    def test_unreviewed_scope_or_foreign_probe_refuses(self):
        for change in ('review', 'probe', 'output'):
            with self.subTest(change=change):
                f = self.fixture()
                if change == 'review':f.change('active_scope', lambda v: v.update(approved_disposable_diagnostic=False))
                if change == 'probe':f.document['probe_plan']['expected_device'] += 1
                if change == 'output':f.document['operation_output'] = str(f.output)
                ref = self.request(f)
                with self.assertRaises(ValueError):g.assemble(ref, f.output)
                self.assertFalse(f.output.exists())

    def test_missing_ack_source_pin_and_changed_original_refuse(self):
        for change in ('ack', 'source', 'original', 'alias', 'module-identity', 'module-role', 'module-fake'):
            with self.subTest(change=change):
                f = self.fixture(); ref = self.request(f)
                if change == 'ack':
                    review = g.p.decode(g.p.read(f.review)); Path(review['parent_ack']['path']).unlink()
                if change == 'source':
                    value = copy.deepcopy(f.document); value['sources']['genuine_plan13_producer.py']['sha256'] = '0' * 64
                    Path(ref['path']).write_bytes(g.p.encode(value)); ref = f.ref(Path(ref['path']))
                if change == 'original':Path(f.query['path']).write_bytes(b'changed')
                if change == 'alias':
                    alias = f.root / 'genuine_plan13_producer.py'; alias.write_bytes(Path(g.composer.__file__).read_bytes()); alias.chmod(0o600)
                    value = copy.deepcopy(f.document); value['sources']['genuine_plan13_producer.py'] = f.ref(alias)
                    Path(ref['path']).write_bytes(g.p.encode(value)); ref = f.ref(Path(ref['path']))
                if change == 'module-fake':
                    fake = type('ForeignModule', (), {'__name__':'genuine_plan13_producer', '__file__':g.composer.__file__, 'Originals':g.composer.Originals})()
                    with patch.object(g, 'composer', fake), patch.dict(sys.modules, {'genuine_plan13_producer':fake}), self.assertRaisesRegex(ValueError, 'active-source-origin'):
                        g.assemble(ref, f.output)
                elif change == 'module-identity':
                    with patch.dict(sys.modules, {'genuine_plan13_producer': object()}), self.assertRaisesRegex(ValueError, 'active-source-origin'):
                        g.assemble(ref, f.output)
                elif change == 'module-role':
                    with patch.object(g.composer, '__name__', 'foreign_role'), self.assertRaisesRegex(ValueError, 'active-source-origin'):
                        g.assemble(ref, f.output)
                else:
                    with self.assertRaises((ValueError, OSError)):g.assemble(ref, f.output)
                self.assertFalse(f.output.exists())

    def test_output_parent_replacement_does_not_adopt_new_directory(self):
        f = self.fixture(); actor = g.Assembly(self.request(f), f.output)
        f.output_parent.rename(f.root / 'old-outputs'); f.output_parent.mkdir(mode=0o700)
        with self.assertRaises(ValueError):actor.execute()
        self.assertFalse(f.output.exists()); self.assertFalse((f.root / 'old-outputs' / 'assembled').exists())
        f = self.fixture(); owner = g.Assembly(self.request(f), f.output)
        original = os.listdir; changed = []
        retained = f.output_parent / 'retained-original'
        def replace_during_empty_census(fd):
            names = original(fd)
            if isinstance(fd, int) and owner.fd is not None and not changed:
                changed.append(True); f.output.rename(retained); f.output.mkdir(mode=0o700)
            return names
        try:
            with patch.object(g.os, 'listdir', side_effect=replace_during_empty_census), self.assertRaisesRegex(ValueError, 'active-output-census-close'):
                owner.execute()
        finally:owner.release()
        self.assertTrue(changed)
        self.assertEqual(list(retained.iterdir()), []); self.assertEqual(list(f.output.iterdir()), [])

    def test_late_original_and_absence_changes_refuse(self):
        for change in ('file', 'fonts'):
            with self.subTest(change=change):
                f = self.fixture(); actor = g.Assembly(self.request(f), f.output)
                if change == 'file':Path(f.query['path']).write_bytes(b'changed')
                else:f.fonts.mkdir()
                with self.assertRaises(ValueError):actor.execute()
                self.assertFalse(f.output.exists())

    def test_postwrite_drift_refuses_and_keeps_partial_evidence(self):
        f = self.fixture(); actor = g.Assembly(self.request(f), f.output); original = g.composer.nested_originals
        def change(*args):
            value = original(*args); (f.output / 'active-input.json').write_bytes(b'changed'); return value
        with patch.object(g.composer, 'nested_originals', change), self.assertRaises(ValueError):actor.execute()
        self.assertTrue((f.output / 'active-input.json').exists()); self.assertFalse((f.output / 'composer-inputs.json').exists())

    def test_exclusive_output_refuses_replay(self):
        f = self.fixture(); ref = self.request(f); g.assemble(ref, f.output)
        with self.assertRaises(ValueError):g.assemble(ref, f.output)

    def test_real_host_owner_originals_do_not_enter_uid1000_child_guard(self):
        import os
        f = self.fixture(); ref = self.request(f)
        self.assertEqual(ref['signature9'][6], os.geteuid())
        self.assertEqual(g.p.read(ref), Path(ref['path']).read_bytes())
        with patch.object(g.active, 'validate', side_effect=AssertionError('child phase must not run')):
            result = g.assemble(ref, f.output)
        self.assertEqual(result['active_input']['signature9'][6], os.geteuid())
        self.assertFalse(result['actual_nfs_verified'])
        self.assertFalse(result['installed_factories_verified'])

    def test_expiry_after_validation_and_unknown_outcome_never_replay(self):
        f = self.fixture(); actor = g.Assembly(self.request(f), f.output)
        with patch.object(g.time, 'time', return_value=f.document['observed'] + 121), self.assertRaises(ValueError):actor.execute()
        self.assertFalse(f.output.exists())
        f = self.fixture(); ref = self.request(f)
        with patch.object(g.composer, 'nested_originals', side_effect=TimeoutError('unknown composer validation outcome')):
            with self.assertRaises(TimeoutError):g.assemble(ref, f.output)
        self.assertEqual(set(x.name for x in f.output.iterdir()), {'active-input.json'})
        with self.assertRaises(ValueError):g.assemble(ref, f.output)

    def test_foreign_final_ack_and_scope_physical_drift_refuse(self):
        for change in ('ack', 'parent'):
            with self.subTest(change=change):
                f = self.fixture()
                if change == 'ack':
                    review = g.p.decode(g.p.read(f.review)); full = f.refs[review['parent_ack']['path']]
                    value = g.p.decode(g.p.read(full)); value['acceptance_sha256'] = '0' * 64
                    Path(full['path']).write_bytes(g.p.encode(value)); newer = f.ref(Path(full['path']))
                    f.refs.pop(full['path']); f.refs[newer['path']] = newer
                    review['parent_ack'] = g.pair(newer)
                    old = f.document['effective_observer_review']; replacement = f.fact(review)
                    f.refs.pop(old['path']); f.document['effective_observer_review'] = replacement
                else:
                    # A same-spelled replacement is not the reviewed grandparent9.
                    f.grandparent.rename(f.nfs / 'retained-grandparent'); f.grandparent.mkdir(mode=0o700)
                ref = self.request(f)
                with self.assertRaises(ValueError):g.assemble(ref, f.output)
                self.assertFalse(f.output.exists())

    def test_original_nonprivate_config_mode_is_retained_and_drift_refuses(self):
        for changed in (False, True):
            with self.subTest(changed=changed):
                directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
                root = Path(directory.name); path = root / 'original-application.properties'
                path.write_bytes(b'original.public.fixture.setting=true\n'); path.chmod(0o640)
                ref = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), signature9=g.p.nine(path.lstat()))
                f = Fixture(root, config_ref=ref); request = self.request(f)
                if changed:path.write_bytes(b'changed.public.fixture.setting=true\n')
                if changed:
                    with self.assertRaises(ValueError):g.assemble(request, f.output)
                    self.assertFalse(f.output.exists())
                else:
                    result = g.assemble(request, f.output)
                    self.assertEqual(result['originals'][str(path)], ref)
                    self.assertEqual(g.p.nine(path.lstat()), ref['signature9'])
                    self.assertEqual(path.read_bytes(), b'original.public.fixture.setting=true\n')

    def test_public_root_owned_source_config_reference_when_available(self):
        # An installed public stdlib SOURCE file supplies a different owner on
        # normal unprivileged hosts; no system configuration/personal data read.
        import os
        import unittest as standard_unittest
        candidates = [Path(standard_unittest.__file__).resolve(strict=True),
                      *(x.resolve(strict=True) for x in Path('/usr/lib').glob('python3.*/unittest/__init__.py'))]
        path = next((x for x in candidates if x.lstat().st_uid != os.geteuid()), candidates[0])
        ref = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), signature9=g.p.nine(path.lstat()))
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        f = Fixture(Path(directory.name), config_ref=ref)
        result = g.assemble(self.request(f), f.output)
        self.assertEqual(result['originals'][str(path)], ref)
        self.assertEqual(g.p.nine(path.lstat()), ref['signature9'])
        if ref['signature9'][6] != os.geteuid():
            with self.assertRaises(ValueError):g.p.read(ref, private=True)
        # Every private evidence fact still uses private=True.
        f = self.fixture(); request = self.request(f); calls = []; original = g.composer.Originals.read
        def observe(owner, ref, *, private=True):
            calls.append((ref['path'], private)); return original(owner, ref, private=private)
        with patch.object(g.composer.Originals, 'read', observe):g.assemble(request, f.output)
        review=g.p.decode(g.p.read(f.review));cohort=g.p.decode(g.p.read(f.document['source_cohort']))
        public={v['path'] for v in (*cohort['sources'].values(),cohort['parent'],review['producer'],review['parent_source'])}
        self.assertTrue(all(private for name, private in calls if name in f.document['originals'] and name not in public))
        self.assertTrue(any(not private for name,private in calls if name in public))

    def test_source_contains_no_transport_or_admission_entry(self):
        import ast
        tree = ast.parse((g.HERE / 'genuine_active_inputs.py').read_text(), feature_version=(3, 10))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        self.assertFalse({'subprocess', 'sqlite3', 'urllib', 'Writer', 'ScopedDocker'} & names)


    def test_original_host_scope_red_for_actual_parent_precreation_contract(self):
        f = self.fixture(); actor = object.__new__(g.Assembly); actor.document=f.document;actor.originals=g.composer.Originals()
        self.assertEqual(hashlib.sha256(LEGACY_PARENT_BLOCK.encode()).hexdigest(),LEGACY_PARENT_BLOCK_SHA256)
        scope=dict(p=g.p,need=g.need,stat=stat,os=os,self=actor,probe=f.document['probe_plan'])
        with self.assertRaises(FileNotFoundError):exec(compile(LEGACY_PARENT_BLOCK,'original-parent-precreation-block','exec'),scope)
        self.assertFalse(f.parent.exists());self.assertFalse(f.output.exists())
        g.Assembly.host_scope(actor,g.p.decode(g.p.read(f.scope)),f.document['probe_plan']);actor.originals.close()
        self.assertFalse(f.parent.exists())

    def test_genuine_parent_precreation_consumes_assembled_none_and_derives_full9(self):
        self.assertEqual(os.geteuid(),1000,'genuine disposable parent source control runs as UID1000')
        f=self.fixture();result=g.assemble(self.request(f),f.output);outer=g.p.decode(g.p.read(result['active_input']))
        self.assertIsNone(outer['probe_plan']['fixture_parent_signature']);self.assertFalse(f.parent.exists())
        parent,derived=owning_precreation(outer,[f.library,f.config],f.library)
        self.assertEqual(parent['path'],str(f.parent));self.assertEqual(derived['fixture_parent_signature'],g.p.nine(f.parent.lstat()));self.assertEqual(derived['fixture_parent_signature'],parent['signature'])
        self.assertEqual(stat.S_IMODE(f.parent.stat().st_mode),0o700);self.assertFalse(list(f.parent.iterdir()))
        with self.assertRaises(ValueError):owning_precreation(outer,[f.library,f.config],f.library)
        for key in('publication_acceptance','actual_nfs_verified','installed_factories_verified','mutation_authority'):self.assertIs(result[key],False)

    def test_forged_existing_parent_signature_and_wrong_parent_or_output_refuse(self):
        for change in('signature','existing','name','admission','output','grandparent'):
            with self.subTest(change=change):
                f=self.fixture()
                if change=='signature':f.document['probe_plan']['fixture_parent_signature']=g.p.nine(f.grandparent.lstat())
                if change=='existing':f.parent.mkdir(mode=0o700)
                if change=='name':f.document['probe_plan']['fixture_parent']=str(f.grandparent/'not-an-owned-name');f.document['parent_admission']['path']=f.document['probe_plan']['fixture_parent']
                if change=='admission':f.document['parent_admission']['path']=str(f.grandparent/'foreign')
                if change=='output':f.document['probe_plan']['output_root']=str(f.output_parent/'detached-probe')
                if change=='grandparent':f.document['parent_admission']['grandparent_signature'][1]+=1
                with self.assertRaises(ValueError):g.assemble(self.request(f),f.output)
                self.assertFalse(f.output.exists())

    def test_late_parent_birth_or_grandparent_metadata_change_refuse_before_write(self):
        for change in('parent','grandparent'):
            with self.subTest(change=change):
                f=self.fixture();actor=g.Assembly(self.request(f),f.output)
                if change=='parent':f.parent.mkdir(mode=0o700)
                else:(f.grandparent/'foreign').write_bytes(b'explicit-disposable-mutation')
                with self.assertRaises(ValueError):actor.execute()
                self.assertFalse(f.output.exists())

if __name__ == '__main__':unittest.main()
