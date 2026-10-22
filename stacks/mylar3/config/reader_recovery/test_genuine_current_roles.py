"""Real original files and owning role checks, explicit transport responses only.

These controls do not execute Docker/getHealth/NFS, instantiate an admitted
Parent or claim runtime source parity. No engine/SDK/Parent class is patched.
"""
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
# Exercise the owning config parser, not the reader-fixture source copy.
sys.path.insert(0, str(HERE.parent))
import publication_native_configured_scope as owning_scope_parser
import genuine_current_roles as g
import test_genuine_application_bootstrap as original


def ref(path):
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), signature9=g.p.nine(path.stat()))


class Transport(original.Engine):
    """Known response double; no Docker/HTTP/SDK objects or admitted facts."""
    def __init__(self, fixture):
        super().__init__(fixture.plan, fixture.sdk)
        self.fixture = fixture; self.probes = 0; self.maps = 0; self.after_probe = None; self.reply_change = None
        # Original source fixture explicitly models the already completed own
        # bootstrap restart. It is NEVER adopted from the later inspect reply.
        for role in self.rows:self.rows[role]['State'] = copy.deepcopy(fixture.epochs[next(name for name, row in fixture.plan['roles'].items() if row['id'] == role)])

    def run(self, args, seconds, data=None):
        self.calls.append(tuple(args))
        if args[0] == 'inspect':return g.p.encode([self.rows[args[1]]])
        if args[:2] == ['network', 'inspect']:return g.p.encode([self.network])
        if args[-1] == g.b.IMAGE_PROGRAM:
            self.maps += 1
            return g.p.encode(self.sdk if self.fail != 'sdk' else dict(self.sdk, **{'worker_health.py': 'f' * 64}))
        if args[-1] == Path(self.plan['native_probe']['path']).read_text():
            self.probes += 1
            if self.fail == 'timeout':raise subprocess.TimeoutExpired('explicit-readonly-probe-double', seconds)
            value = dict(version=1, nonce=self.plan['nonce'], source_sha256=g.PROBE_SHA,
                publication=dict(state='ready'), **copy.deepcopy(self.fixture.process))
            if self.reply_change:self.reply_change(value)
            if self.after_probe:self.after_probe()
            return g.p.encode(value)
        raise AssertionError('Unexpected transport call')


class Fixture:
    def __init__(self, case):
        base = original.BootstrapTests(); base.setUp(); case.addCleanup(base.doCleanups)
        self.base = base.base; self.plan = copy.deepcopy(base.plan); self.sdk = copy.deepcopy(base.sdk)
        self.sdk['native_writers.py'] = 'c' * 64
        # Preserve a fresh original map; this is a response fixture, never an
        # assertion that these fake SDK bytes are actually installed.
        self.plan['native_sdk'] = g.b.put(self.base / 'sdk-current.json', self.sdk)
        self.profiles = {name: copy.deepcopy(row['profile']) for name, row in self.plan['roles'].items()}
        self.epochs = {name: copy.deepcopy(row['epoch']) for name, row in self.plan['roles'].items()}
        self.epochs['native']['StartedAt'] = 'already-completed-bootstrap-restart'
        self.process = dict(process=dict(pid=123, start_ticks=456, argv=['/lsiopy/bin/python3', '/app/mylar3/Mylar.py', '--datadir', '/config']),
            config=dict(self.plan['native_ini'], path='/config/config.ini'))
        self.catalog = dict(version=1, kind='disposable-native-catalog-processing-observation', nonce=self.plan['nonce'],
            native_CID=self.plan['roles']['native']['id'], native_image=self.plan['images']['native'], process=self.process,
            **{key: False for key in g.composer.RIGHTS}, ordinary_ack_verified=False,
            native_catalog_processing_observed=True, birth_verified=False, daemon_operation_identity=False)
        self.catalog_ref = self.put(self.catalog)
        reader = dict(library=dict(root=self.plan['geometry']['library']['path']), books=[])
        bracket = dict(kind='original-reader-task-empty-bracket', nonce=self.plan['nonce'], reader_image=self.plan['images']['reader'],
            helper=ref(HERE / 'genuine_reader_quiescence.py'), observation=dict(queue_empty_observed=True),
            roles=dict(profiles=self.profiles, epochs=self.epochs, network=self.plan['network']['profile'], reader=reader),
            **{key: False for key in ('application_quiescence_verified', 'future_exclusion_verified', 'stop_authority',
                'reader_resume_authority', 'publication_acceptance', 'mutation_authority', 'ordinary_ack_verified')})
        self.result = dict(kind='disposable-application-bootstrap-observation', nonce=self.plan['nonce'],
            native_catalog_processing=self.catalog_ref, native_catalog_processing_observed=True,
            reader=reader, reader_task_empty_observation=bracket, ordinary_ack_verified=False, **{key: False for key in g.composer.RIGHTS})
        self.result_ref = self.put(self.result); self.plan_ref = self.put(self.plan)
        self.sources = {name: ref((HERE.parent if name == 'publication_native_configured_scope.py' else HERE) / name)
                        for name in (*g.SOURCE_PINS, 'genuine_current_roles.py')}
        self.output = self.base / 'current-roles.json'; self.engine = Transport(self)
        self.serial = 0

    def put(self, value):
        import secrets
        return g.b.put(self.base / ('input-' + secrets.token_hex(8) + '.json'), value)

    def owner(self, **kwargs):
        return g.Capture(self.plan_ref, self.result_ref, self.catalog_ref, self.sources, self.output, engine=self.engine, **kwargs)


class Tests(unittest.TestCase):
    def setUp(self):self.f = Fixture(self)

    def test_exact_composer_output_from_saved_postrestart_epoch(self):
        owner = self.f.owner(); saved = Path(self.f.result_ref['path']).read_bytes()
        result = g.p.decode(g.p.read(owner.execute()))
        self.assertEqual(set(result), {'nonce', 'observed', 'roles', 'native_process'})
        self.assertEqual(result['nonce'], self.f.plan['nonce']); self.assertEqual(result['native_process'], self.f.process)
        self.assertEqual(result['roles']['native']['epoch'], self.f.epochs['native'])
        self.assertNotEqual(result['roles']['native']['epoch'], self.f.plan['roles']['native']['epoch'])
        self.assertEqual(Path(self.f.result_ref['path']).read_bytes(), saved)
        self.assertEqual((self.f.engine.maps, self.f.engine.probes), (2, 1))
        self.assertIsNone(owner.geometry)

    def relocate_original_context(self):
        # Distinct original Bootstrap source generation, with real full9 refs.
        directory = self.f.base / 'original-bootstrap-sources'; directory.mkdir(mode=0o700)
        names = ('genuine_bootstrap_http.py', 'genuine_reader_quiescence.py',
                 'comic_native_process_probe.py', 'publication_native_configured_scope.py')
        for name in names:
            path = directory / name; path.write_bytes((HERE / name).read_bytes()); path.chmod(0o644)
        for role, name in (('helper', names[0]), ('native_probe', names[2]), ('scope_source', names[3])):
            self.f.plan[role] = ref(directory / name)
        self.f.result['reader_task_empty_observation']['helper'] = ref(directory / names[1])
        self.f.plan_ref = self.f.put(self.f.plan); self.f.result_ref = self.f.put(self.f.result)
        self.f.engine = Transport(self.f)
        return directory

    def test_original_bootstrap_generation_uris_and_owning_parser(self):
        directory = self.relocate_original_context(); owner = self.f.owner()
        retained = copy.deepcopy(self.f.result['reader_task_empty_observation']['helper'])
        self.assertIs(g.scope_parser, owning_scope_parser)
        self.assertEqual(Path(g.scope_parser.__file__).absolute(), HERE.parent / 'publication_native_configured_scope.py')
        owner.execute()
        self.assertEqual(owner.originals.refs[str(directory / 'genuine_reader_quiescence.py')], retained)
        self.assertEqual(self.f.epochs['reader'], self.f.plan['roles']['reader']['epoch'])
        self.assertEqual(self.f.profiles['reader'], self.f.plan['roles']['reader']['profile'])

    def test_current_alias_or_wrong_original_queue_context_refuses(self):
        self.relocate_original_context()
        self.f.result['reader_task_empty_observation']['helper'] = ref(HERE / 'genuine_reader_quiescence.py')
        self.f.result_ref = self.f.put(self.f.result)
        with self.assertRaisesRegex(g.p.Held, 'capture-original-queue-source'):self.f.owner()
        self.assertEqual(self.f.engine.calls, [])

    def test_original_native_source_alias_and_original_late_drift_refuse(self):
        directory = self.relocate_original_context()
        old = self.f.plan['native_probe']; self.f.plan['native_probe'] = ref(HERE / 'comic_native_process_probe.py')
        self.f.plan_ref = self.f.put(self.f.plan)
        with self.assertRaisesRegex(g.p.Held, 'capture-original-native-source'):self.f.owner()
        self.f.plan['native_probe'] = old; self.f.plan_ref = self.f.put(self.f.plan)
        owner = self.f.owner()
        self.f.engine.after_probe = lambda: (directory / 'genuine_reader_quiescence.py').write_bytes(b'changed original')
        with self.assertRaises(g.p.Held):owner.execute()
        self.assertFalse(self.f.output.exists())

    def test_new_observer_retains_actual_loaded_older_roles_and_parser(self):
        directory = self.f.base / 'new-observer'; directory.mkdir(mode=0o700)
        source = directory / 'genuine_current_roles.py'; source.write_bytes((HERE / source.name).read_bytes()); source.chmod(0o644)
        spec = importlib.util.spec_from_file_location('original_mixed_current_roles', source)
        mixed = importlib.util.module_from_spec(spec); spec.loader.exec_module(mixed)
        self.assertIs(mixed.b, g.b); self.assertIs(mixed.p, g.p)
        self.assertIs(mixed.scope_parser, owning_scope_parser)
        sources = copy.deepcopy(self.f.sources); sources[source.name] = ref(source)
        bad = copy.deepcopy(sources); bad['publication_native_configured_scope.py'] = ref(HERE / 'publication_native_configured_scope.py')
        with self.assertRaisesRegex(g.p.Held, 'capture-original-source-pin'):
            mixed.Capture(self.f.plan_ref, self.f.result_ref, self.f.catalog_ref, bad, self.f.output, engine=self.f.engine)
        self.assertEqual(self.f.engine.calls, [])
        owner = mixed.Capture(self.f.plan_ref, self.f.result_ref, self.f.catalog_ref, sources, self.f.output, engine=self.f.engine)
        self.assertEqual(owner.sources['genuine_application_bootstrap.py'], self.f.sources['genuine_application_bootstrap.py'])
        owner.execute(); self.assertTrue(self.f.output.exists())
        late_output = self.f.base / 'mixed-late.json'
        late = mixed.Capture(self.f.plan_ref, self.f.result_ref, self.f.catalog_ref, sources, late_output, engine=self.f.engine)
        self.f.engine.after_probe = lambda: source.write_bytes(b'changed actual observer')
        with self.assertRaises(g.p.Held):late.execute()
        self.assertFalse(late_output.exists())

    def test_current_directory_mtime_after_bootstrap_is_not_old_identity_adoption(self):
        library = Path(self.f.plan['geometry']['library']['path']); (library / 'completed-native-output.cbz').write_bytes(b'fixture')
        owner = self.f.owner()
        self.assertNotEqual(owner.geometry_originals['library']['signature9'], self.f.plan['geometry']['library']['signature9'])
        self.assertEqual(owner.geometry_originals['library']['signature9'][:2], self.f.plan['geometry']['library']['signature9'][:2])
        owner.execute()

    def test_source_missing_or_bad_pin_refuses_before_transport(self):
        for change in ('missing', 'pin'):
            sources = copy.deepcopy(self.f.sources)
            if change == 'missing':sources.pop('genuine_plan13_producer.py')
            else:sources['genuine_application_bootstrap.py']['sha256'] = 'f' * 64
            with self.subTest(change=change), self.assertRaises(g.p.Held):
                g.Capture(self.f.plan_ref, self.f.result_ref, self.f.catalog_ref, sources, self.f.output, engine=self.f.engine)
        self.assertEqual(self.f.engine.calls, [])

    def test_late_original_source_replacement_refuses(self):
        owner = self.f.owner(); old = self.f.sources['genuine_current_roles.py']
        # Change supplied original metadata, not the shared real source bytes.
        owner.originals.refs[old['path']]['signature9'][3] += 1
        with self.assertRaises(g.p.Held):owner.execute()
        self.assertFalse(self.f.output.exists()); self.assertEqual(self.f.engine.calls, [])

    def test_changed_result_original_refuses_before_transport(self):
        owner = self.f.owner(); Path(self.f.result_ref['path']).write_bytes(b'changed')
        with self.assertRaises(g.p.Held):owner.execute()
        self.assertEqual(self.f.engine.calls, [])

    def test_foreign_role_image_epoch_and_mount_refuse_without_adoption(self):
        native = self.f.plan['roles']['native']['id']; row = copy.deepcopy(self.f.engine.rows[native])
        for field, change in (('Image', 'sha256:' + 'f' * 64), ('State', dict(row['State'], StartedAt='foreign-restart')),
                              ('Mounts', []), ('HostConfig', dict(row['HostConfig'], Privileged=True))):
            self.f.engine.rows[native] = dict(copy.deepcopy(row), **{field: change})
            owner = self.f.owner()
            with self.subTest(field=field), self.assertRaises(g.p.Held):owner.execute()
            self.assertFalse(self.f.output.exists())

    def test_worker_start_and_network_epoch_change_refuse(self):
        worker = self.f.plan['roles']['worker']['id']; self.f.engine.rows[worker]['State'].update(Status='running', Running=True, Pid=444)
        with self.assertRaises(g.p.Held):self.f.owner().execute()
        self.f.engine.rows[worker]['State'] = copy.deepcopy(self.f.epochs['worker']); self.f.engine.network['Containers']['foreign'] = {}
        with self.assertRaises(g.p.Held):self.f.owner().execute()

    def test_late_role_drift_after_probe_refuses_output(self):
        native = self.f.plan['roles']['native']['id']
        self.f.engine.after_probe = lambda: self.f.engine.rows[native]['State'].update(Pid=999)
        with self.assertRaises(g.p.Held):self.f.owner().execute()
        self.assertFalse(self.f.output.exists()); self.assertEqual(self.f.engine.probes, 1)

    def test_config_process_nonce_pin_or_hold_response_refuses(self):
        for name in ('config', 'process', 'nonce', 'source_sha256', 'publication'):
            self.f.engine.reply_change = lambda value, name=name: value.update({name: {'state': 'held'} if name == 'publication' else {}})
            with self.subTest(name=name), self.assertRaises(g.p.Held):self.f.owner().execute()
            self.assertFalse(self.f.output.exists())

    def test_sdk_parity_refuses_before_probe(self):
        self.f.engine.fail = 'sdk'
        with self.assertRaisesRegex(g.p.Held, 'installed-source-parity'):self.f.owner().execute()
        self.assertEqual(self.f.engine.probes, 0)

    def test_late_installed_source_drift_and_ini_drift_refuse(self):
        owner = self.f.owner()
        self.f.engine.after_probe = lambda: self.f.engine.sdk.update({'worker_health.py': 'f' * 64})
        with self.assertRaisesRegex(g.p.Held, 'installed-source-parity'):owner.execute()
        self.assertFalse(self.f.output.exists())
        self.f.engine.sdk = copy.deepcopy(self.f.sdk)
        self.f.engine.sdk['worker_health.py'] = 'b' * 64
        owner = self.f.owner(); path = Path(self.f.plan['native_ini']['path'])
        self.f.engine.after_probe = lambda: path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaises(g.p.Held):owner.execute()
        self.assertFalse(self.f.output.exists())

    def test_timeout_and_expired_deadline_never_retry(self):
        self.f.engine.fail = 'timeout'; owner = self.f.owner()
        with self.assertRaises(subprocess.TimeoutExpired):owner.execute()
        with self.assertRaisesRegex(g.p.Held, 'no-replay'):owner.execute()
        self.assertEqual(self.f.engine.probes, 1); self.assertFalse(self.f.output.exists())
        owner = self.f.owner(); owner.end = time.monotonic() - 1
        with self.assertRaisesRegex(g.p.Held, 'deadline'):owner.execute()

    def test_geometry_replacement_symlink_or_late_full9_change_refuses(self):
        library = Path(self.f.plan['geometry']['library']['path']); saved = library.with_name('saved-L')
        library.rename(saved); library.mkdir(mode=0o700)
        with self.assertRaisesRegex(g.p.Held, 'directory-identity'):self.f.owner()
        library.rmdir(); library.symlink_to(saved, target_is_directory=True)
        with self.assertRaises(g.p.Held):self.f.owner()
        library.unlink(); saved.rename(library)
        owner = self.f.owner(); self.f.engine.after_probe = lambda: (library / 'foreign').write_bytes(b'x')
        with self.assertRaisesRegex(g.p.Held, 'directory-full9'):owner.execute()

    def test_bad_primary_key_and_duplicate_key_refuse_before_transport(self):
        path = Path(self.f.plan['native_ini']['path']); old = path.read_bytes()
        for raw in (old.replace(b'K' * 32, b'K' * 31), old + b'\n[Other]\napi_key=' + b'K' * 32 + b'\n'):
            path.write_bytes(raw); path.chmod(0o600)
            plan = copy.deepcopy(self.f.plan); plan['native_ini'] = ref(path)
            catalog = copy.deepcopy(self.f.catalog); catalog['process']['config'] = dict(plan['native_ini'], path='/config/config.ini')
            catalog_ref = self.f.put(catalog); result = copy.deepcopy(self.f.result); result['native_catalog_processing'] = catalog_ref
            with self.subTest(size=len(raw)), self.assertRaises(g.p.Held):
                g.Capture(self.f.put(plan), self.f.put(result), catalog_ref, self.f.sources, self.f.output, engine=self.f.engine)
        self.assertEqual(self.f.engine.calls, [])

    def test_original_sse_unavailable_or_role_bracket_changed_refuses(self):
        for change in ('missing', 'image', 'purpose'):
            result = copy.deepcopy(self.f.result)
            if change == 'missing':result.pop('reader_task_empty_observation')
            elif change == 'image':result['reader_task_empty_observation']['reader_image'] = 'sha256:' + 'f' * 64
            else:result['reader_task_empty_observation']['roles']['profiles']['reader']['Config']['Labels'][g.b.PURPOSE] = 'foreign'
            with self.subTest(change=change), self.assertRaises(g.p.Held):
                g.Capture(self.f.plan_ref, self.f.put(result), self.f.catalog_ref, self.f.sources, self.f.output, engine=self.f.engine)

    def test_owning_parser_refuses_credential_shaped_or_alternate_config_argv(self):
        for argv in (['--apikey', 'not-a-real-key'], ['--config', '/foreign.ini'], ['--port', '9999']):
            catalog = copy.deepcopy(self.f.catalog); catalog['process']['process']['argv'] += argv
            catalog_ref = self.f.put(catalog); result = copy.deepcopy(self.f.result); result['native_catalog_processing'] = catalog_ref
            with self.subTest(flag=argv[0]), self.assertRaises(ValueError):
                g.Capture(self.f.plan_ref, self.f.put(result), catalog_ref, self.f.sources, self.f.output, engine=self.f.engine)
        self.assertEqual(self.f.engine.calls, [])

    def test_finite_transport_policy_has_no_mutation_or_foreign_exec(self):
        owner = self.f.owner(); policy = g.ReadOnlyDocker(owner)
        for args in (['restart', self.f.plan['roles']['native']['id']], ['inspect', 'f' * 64], ['network', 'connect', 'x'],
                     ['exec', '--interactive', '--user', '0', self.f.plan['roles']['native']['id'], '/bin/sh']):
            with self.subTest(args=args), self.assertRaises(g.p.Held):policy.approve(args, None)
        prefix = ['exec', '--interactive', '--user', '1000:1000', self.f.plan['roles']['native']['id'], '/lsiopy/bin/python3', '-I', '-B', '-c']
        policy.approve(prefix + [g.b.IMAGE_PROGRAM], g.p.encode(sorted(owner.sdk)))
        policy.approve(prefix + [owner.probe_program], g.p.encode(owner.probe_request(10)))
        with self.assertRaises(g.p.Held):policy.approve(prefix + [owner.probe_program], g.p.encode(dict(owner.probe_request(10), nonce='f' * 64)))
        self.assertEqual(self.f.engine.calls, [])

    def test_existing_output_and_disabled_entry_cannot_adopt(self):
        self.f.output.write_text('retained')
        with self.assertRaisesRegex(g.p.Held, 'no-adoption'):self.f.owner()
        with self.assertRaisesRegex(g.p.Held, 'activation'):
            g.run(None, None, None, None, None)

    def test_output_parent_replaced_after_probe_never_adopted(self):
        parent = self.f.base / 'output'; parent.mkdir(mode=0o700); self.f.output = parent / 'roles.json'
        owner = self.f.owner()
        def replace():
            parent.rename(parent.with_name('retained-output')); parent.mkdir(mode=0o700)
        self.f.engine.after_probe = replace
        with self.assertRaises(g.p.Held):owner.execute()
        self.assertFalse(self.f.output.exists())

    def test_same_byte_output_leaf_replacement_during_write_refuses(self):
        owner = self.f.owner(); fsync = os.fsync; replaced = []
        def replace(fd):
            fsync(fd)
            if self.f.output.exists() and os.fstat(fd).st_ino == self.f.output.stat().st_ino and not replaced:
                raw = self.f.output.read_bytes(); self.f.output.unlink(); self.f.output.write_bytes(raw); self.f.output.chmod(0o600); replaced.append(True)
        with patch.object(g.os, 'fsync', side_effect=replace), self.assertRaises(g.p.Held):owner.execute()
        self.assertEqual(replaced, [True])

    def test_fresh_catalog_ini_accepts_prior_ctime_change_but_not_later_drift(self):
        path = Path(self.f.plan['native_ini']['path']); old = self.f.plan['native_ini']; raw = path.read_bytes()
        path.chmod(0o600); fresh = ref(path)
        self.assertEqual(old['signature9'][:4], fresh['signature9'][:4]); self.assertNotEqual(old['signature9'][4], fresh['signature9'][4])
        self.assertEqual(path.read_bytes(), raw)
        self.f.process['config'] = dict(fresh, path='/config/config.ini')
        self.f.catalog['process'] = copy.deepcopy(self.f.process); self.f.catalog_ref = self.f.put(self.f.catalog)
        self.f.result['native_catalog_processing'] = self.f.catalog_ref; self.f.result_ref = self.f.put(self.f.result)
        owner = self.f.owner(); result = g.p.decode(g.p.read(owner.execute()))
        self.assertEqual(result['native_process']['config'], self.f.process['config'])
        self.f.output = self.f.base / 'roles-second.json'; owner = self.f.owner()
        path.chmod(0o600)
        with self.assertRaises(g.p.Held):owner.execute()
        self.assertFalse(self.f.output.exists())

    def test_primary_probe_error_survives_parent_closure_failure(self):
        parent = self.f.base / 'output'; parent.mkdir(mode=0o700); self.f.output = parent / 'roles.json'
        owner = self.f.owner()
        def fail():
            parent.rename(parent.with_name('retained-output')); parent.mkdir(mode=0o700)
            raise RuntimeError('original-probe-error')
        self.f.engine.after_probe = fail
        with self.assertRaisesRegex(RuntimeError, 'original-probe-error'):owner.execute()
        self.assertFalse(self.f.output.exists())


if __name__ == '__main__':unittest.main()
