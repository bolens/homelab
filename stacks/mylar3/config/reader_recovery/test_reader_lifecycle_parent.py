"""Explicit fake engine/producer fixtures; no installed or actual runtime proof."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('parent_candidate', ROOT / 'comic_reader_lifecycle_parent.py')
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)


def fixture_ref(path, value):
    path.write_bytes(value); path.chmod(0o600)
    return dict(path=str(path), sha256=hashlib.sha256(value).hexdigest(), signature9=p.nine(path.lstat()))


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.root.chmod(0o700)
        self.operation = self.root / 'operation'; self.operation.mkdir(mode=0o700)
        self.provider = fixture_ref(self.root / 'provider.py', b'x = 1\n')
        self.source = fixture_ref(self.root / 'parent.py', b'x = 2\n')
        self.sdk = fixture_ref(self.root / 'sdk.json', b'{}')
        self.action = fixture_ref(self.root / 'action.json', b'{}')
        self.proof = fixture_ref(self.root / 'native.json', b'{}')
        self.parent = object.__new__(p.LifecycleParent)
        x = self.parent
        x.plan = dict(nonce='a' * 64, operation=str(self.operation), selected_image='sha256:' + 'b' * 64,
                      provider=self.provider, sdk_map=self.sdk, action_inputs={'prepare': self.action, 'execute': self.action},
                      native=dict(data='/data', roots=['/library']), bounds=dict(files=100, bytes=100000),
                      admission_source_sha256='c' * 64)
        x.op = self.operation; x.op_fact = tuple(p.five(x.op.lstat()))
        x.plan['mounts'] = [dict(host=str(self.root), child='/fixture', write=False),
                            dict(host=str(self.operation), child='/operation', write=True)]
        x.mapping = p.Paths(x.plan['mounts'])
        x.source_ref = self.source; x.plan_ref = self.action; x.generated = {}; x.files = {}; x.nodes = {}
        x.thread = p.threading.get_ident(); x.deadline = p.time.monotonic() + 100; x.engine = object()
        x.core = p.encode(dict(plan=x.plan, files=x.files, nodes=x.nodes, source=x.source_ref,
                              input=x.plan_ref, engine=id(x.engine), thread=x.thread, deadline=x.deadline))
        p._CORES[x] = x.core; p._GENERATED[x] = p.encode(x.generated); p._PHASES[x] = {}
        # Explicit fixture projector for pre-existing transport controls only.
        # New semantics tests below load the actual source-pinned scope module.
        p._PROJECTORS[x] = lambda value: value
        x.plan['birth_source_sha256'] = 'e'*64
        x.core = p.encode(dict(plan=x.plan, files=x.files, nodes=x.nodes, source=x.source_ref,
                              input=x.plan_ref, engine=id(x.engine), thread=x.thread, deadline=x.deadline)); p._CORES[x] = x.core

    def ack(self):
        return dict(nonce='a' * 64, phase='prepare', source_sha256=self.provider['sha256'],
                    report=self.proof, publication_acceptance=False, reader_resume_authority=False)

    def test_exact_six_field_ack(self):
        self.assertEqual(p.validate_ack(self.ack(), 'prepare', 'a' * 64, self.provider['sha256']), self.proof)

    def test_old_four_field_ack_refused(self):
        a = self.ack(); del a['reader_resume_authority']; del a['publication_acceptance']
        with self.assertRaises(p.Held): p.validate_ack(a, 'prepare', 'a' * 64, self.provider['sha256'])

    def test_ack_false_rights_identity(self):
        for key in p.FALSE_RIGHTS:
            for value in (True, 0, None):
                a = self.ack(); a[key] = value
                with self.assertRaises(p.Held): p.validate_ack(a, 'prepare', 'a' * 64, self.provider['sha256'])

    def test_wrong_phase_nonce_source(self):
        for key in ('nonce', 'phase', 'source_sha256'):
            a = self.ack(); a[key] = 'wrong'
            with self.assertRaises(p.Held): p.validate_ack(a, 'prepare', 'a' * 64, self.provider['sha256'])

    def test_duplicate_json(self):
        with self.assertRaises(p.Held): p.decode(b'{"a":1,"a":2}')

    def test_mount_bijection(self):
        self.assertEqual(self.parent.mapping.child(self.provider['path']), '/fixture/provider.py')
        self.assertEqual(self.parent.mapping.host('/fixture/provider.py'), self.provider['path'])

    def test_unmapped_path(self):
        with self.assertRaises(p.Held): self.parent.mapping.host('/elsewhere/provider.py')

    def test_shadowed_mount(self):
        mapper = p.Paths([dict(host=str(self.root), child='/fixture', write=False),
                          dict(host=str(self.operation), child='/fixture/provider.py', write=False)])
        with self.assertRaises(p.Held): mapper.child(self.provider['path'])

    def test_duplicate_mount(self):
        with self.assertRaises(p.Held): p.Paths([dict(host='/a', child='/x', write=False), dict(host='/b', child='/x', write=False)])

    def test_provider_real_command_contract(self):
        source = ROOT / '_reader_parent_fixtures' / 'fixture_provider.py'
        spec = importlib.util.spec_from_file_location('provider_real', source)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        template = p.command_template(dict(path=str(source), sha256=self.provider['sha256']), 'prepare', '/operation/prepare-input.json')
        actual = p.actual_command(template, 'd' * 64)
        args = types.SimpleNamespace(input_sha256='d' * 64, input='/operation/prepare-input.json',
                                     phase='prepare', source_sha256=self.provider['sha256'])
        self.assertEqual(module.actual_command(dict(command_template=template), args, actual), actual)

    def test_current_canonical_provider_command_contract(self):
        source = ROOT / 'comic_negative_reader_action.py'
        spec = importlib.util.spec_from_file_location('provider_current', source)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        ref = dict(path=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        template = p.command_template(ref, 'prepare', '/operation/prepare-input.json')
        actual = p.actual_command(template, 'd'*64)
        args = types.SimpleNamespace(input_sha256='d'*64, input='/operation/prepare-input.json', phase='prepare', source_sha256=ref['sha256'])
        self.assertEqual(module.actual_command(dict(command_template=template),args,actual),actual)

    def test_current_canonical_provider_wrong_placeholder_position(self):
        source = ROOT / 'comic_negative_reader_action.py'
        spec = importlib.util.spec_from_file_location('provider_current',source)
        module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        template = p.command_template(dict(path=str(source),sha256='c'*64),'prepare','/operation/prepare-input.json')
        template[7]='<INPUT_SHA256>';template[9]='d'*64
        args=types.SimpleNamespace(input_sha256='d'*64,input='/operation/prepare-input.json',phase='prepare',source_sha256='c'*64)
        with self.assertRaises(module.Held):module.actual_command(dict(command_template=template),args,template)

    def test_duplicate_placeholder(self):
        with self.assertRaises(p.Held): p.actual_command(['<INPUT_SHA256>', '<INPUT_SHA256>'], 'd' * 64)

    def test_backup_input_no_circular_digest(self):
        value, command = self.parent.phase_input('backup', dict(runtime={}))
        doc = p.decode(p.read(value))
        self.assertEqual(doc['command_template'][-3], '<INPUT_SHA256>')
        self.assertEqual(command[-3], value['sha256'])
        self.assertFalse((self.operation / 'backup-input.lifecycle.json').exists())

    def prebirth(self):
        def produce(phase, context):
            seed = dict(version=1, kind='selected-child-native-scope-birth', invocation=context['invocation'],
                        parent_source=self.parent.mapping.child_ref(self.source),
                        birth_source=dict(path='/app/mylar3/mylar/publication_native_scope_birth.py', sha256='e'*64),
                        config=dict(path='/data/config.ini', sha256='f'*64), worker_library='/library',
                        selected_image=self.parent.plan['selected_image'])
            return dict(reader=dict(config_root='/config'), proofs={}, birth_seed=seed)
        self.parent.produce = produce
        return self.parent.phase_input('prepare', dict(controls={}), dict(backup={}))

    def test_real_seed_after_actual_input_before_sidecar(self):
        value, command = self.prebirth()
        doc = p.decode((self.operation/'prepare-input.birth.json').read_bytes())
        self.assertEqual(doc['invocation']['command'], command)
        self.assertEqual(doc['invocation']['input_sha256'], value['sha256'])
        self.assertEqual(doc['parent_source']['path'], '/fixture/parent.py')
        self.assertNotIn('ancestors', doc)
        self.assertFalse((self.operation/'prepare-input.lifecycle.json').exists())

    def test_missing_custody_holds(self):
        with self.assertRaises(p.Held): self.parent.phase_input('prepare', {}, None)
        self.assertTrue((self.operation / 'prepare-input.json').exists())
        self.assertFalse((self.operation / 'prepare-input.lifecycle.json').exists())

    def test_exclusive_phase_input(self):
        self.parent.phase_input('backup', {})
        with self.assertRaises(FileExistsError): self.parent.phase_input('backup', {})

    def test_operation_replacement_holds_before_write(self):
        self.operation.rename(self.root / 'old-operation'); self.operation.mkdir(mode=0o700)
        with self.assertRaises(p.Held): self.parent.emit('proof.json', {})
        self.assertFalse((self.operation / 'proof.json').exists())

    def test_same_bytes_replacement_refused(self):
        raw = p.read(self.proof); path = Path(self.proof['path']); path.unlink(); path.write_bytes(raw); path.chmod(0o600)
        with self.assertRaises(p.Held): p.read(self.proof)

    def test_symlink_refused(self):
        path = Path(self.proof['path']); path.unlink(); path.symlink_to(self.action['path'])
        with self.assertRaises((p.Held, OSError)): p.read(self.proof)

    def test_private_mode_refused(self):
        Path(self.proof['path']).chmod(0o640)
        with self.assertRaises(p.Held): p.read(self.proof)

    def test_output_reseal_cannot_refresh_registry(self):
        self.parent.generated['forged'] = self.proof
        with self.assertRaises(p.Held): self.parent.left()

    def test_original_plan_reseal_cannot_refresh_registry(self):
        self.parent.plan['nonce'] = 'f' * 64; self.parent.core = b'forged'
        with self.assertRaises(p.Held): self.parent.left()

    def test_late_helper_claim_raw_final(self):
        original = self.root / 'source'; original.write_bytes(b'original'); fact = p.nine(original.lstat())
        files = {str(original): tuple(fact)}; shadow = self.root / 'shadow'
        with patch.object(p, 'nine', side_effect=AssertionError('no stat helpers in final')):
            shadow.symlink_to(original)
            with self.assertRaises(p.Held): p.final(files, {}, (str(shadow),))

    def test_producer_schema_requires_actual_phase(self):
        self.parent.plan['producer'] = self.proof
        self.parent.core = p.encode(dict(plan=self.parent.plan, files={}, nodes={}, source=self.source,
                                        input=self.action, engine=id(self.parent.engine), thread=self.parent.thread,
                                        deadline=self.parent.deadline))
        p._CORES[self.parent] = self.parent.core
        self.parent.producer = types.SimpleNamespace(produce=lambda phase, request, **kwargs: dict(version=1, phase='wrong', nonce='a' * 64, evidence={}))
        with self.assertRaises(p.Held): self.parent.produce('native-observation', {})

    def child_fixture(self, late=False, forged=False, phase='backup', skip_birth=False, bad_sequence=False, health_change=False, restart_change=False):
        x = self.parent
        self.continuous_fixture()
        rows = copy.deepcopy(x.baselines)
        x.continuous = lambda: copy.deepcopy(rows)
        input_ref, actual = self.prebirth() if phase == 'prepare' else x.phase_input('backup', dict(runtime={}))
        state = dict(FinishedAt='',StartedAt='start',ExitCode=0,Error='',Status='created', Running=False, Pid=0, Paused=False, Restarting=False, Dead=False, OOMKilled=False)
        cid = '4' * 64
        row = dict(Id=cid, Name='fixture', Image=x.plan['selected_image'], Path='/lsiopy/bin/python3', Args=actual[1:],
                   Config=dict(User='1000:1000', Entrypoint=['/lsiopy/bin/python3'], Cmd=actual[1:], OpenStdin=True, Tty=False,
                               Labels={'com.homelab.reader.lifecycle': 'reader-' + phase + '-' + x.plan['nonce'][:16]}),
                   HostConfig=dict(ReadonlyRootfs=True, Privileged=False, NetworkMode='none', IpcMode='private', PidMode='',
                                   CapDrop=['ALL'], SecurityOpt=['no-new-privileges'], PidsLimit=32, Memory=2*1024**3,
                                   MemorySwap=2*1024**3, RestartPolicy=dict(Name='no')),
                   Mounts=[dict(Type='bind', Source=str(self.root), Destination='/fixture', RW=False),
                           dict(Type='bind', Source=str(self.operation), Destination='/operation', RW=True)],
                   NetworkSettings={}, State=state)
        calls = []
        class Engine:
            def run(_, args, seconds):
                calls.append(args[0])
                if args[0] == 'create': return cid.encode()
                if args[0] == 'inspect': return p.encode([row])
                raise AssertionError(args)
            def interactive(_, identity, callback, seconds):
                state.update(Status='running', Running=True, Pid=123)
                message = dict(protocol='reader-lifecycle-pipe-v1', type='challenge', nonce=x.plan['nonce'],
                               input_sha256=input_ref['sha256'], parent_sha256=x.source_ref['sha256'],
                               sequence=1, challenge='e'*64)
                observed = p.decode(callback(message))
                self.assertEqual(observed['child_mounts'], row['Mounts'])
                self.assertIn('native', observed); self.assertIn('worker', observed)
                if phase == 'prepare' and not skip_birth:
                    pending = p._PHASES[x][phase]
                    body = dict(version=1, kind='existing-native-configured-scope', invocation=pending['invocation'],
                                native=observed['native'], worker=observed['worker'], child_mounts=observed['child_mounts'],
                                config=dict(path='/data/config.ini', sha256='f'*64), config_module={}, main_module={},
                                worker_library='/library', tool_root='/opt/archiving-utils', ancestors={'/':[1,2,16877,1000,1000]})
                    proof = fixture_ref(self.operation/'prepare-input.native-scope.json', p.encode(body))
                    message.update(type='birth-commit', sequence=3 if bad_sequence else 2,
                                   birth=dict(source_sha256='e'*64, seed_sha256=pending['seed_ref']['sha256'],
                                              native_scope=x.mapping.child_ref(proof)))
                    reply = p.decode(callback(message))
                    self.assertEqual(reply['type'], 'birth-accepted')
                    del message['birth']; message.update(type='challenge', sequence=3, challenge='f'*64)
                    self.assertEqual(p.decode(callback(message))['sequence'], 3)
                state.update(Status='exited', Running=False, Pid=0, ExitCode=0)
                report = fixture_ref(self.operation / phase / (phase+'-report.json'),
                                     p.encode(dict(phase=phase, nonce=x.plan['nonce'],
                                              provider_continuity_verified=False, final_ack_required=True)))
                return dict(nonce=x.plan['nonce'], phase=phase, source_sha256=x.plan['provider']['sha256'],
                            report=x.mapping.child_ref(report), publication_acceptance=forged, reader_resume_authority=False)
        x.engine = Engine()
        del x.inspect
        x.core = p.encode(dict(plan=x.plan, files={}, nodes={}, source=x.source_ref, input=x.plan_ref,
                              engine=id(x.engine), thread=x.thread, deadline=x.deadline)); p._CORES[x] = x.core
        def produce(phase, context):
            result = dict(native=dict(inspect=copy.deepcopy(context['observations']['held_native'])), worker=copy.deepcopy(context['observations']['held_worker']), child_mounts=copy.deepcopy(row['Mounts']))
            if health_change:
                result['native']['inspect']['State']['Health']['Log'] = [{'End':'between-producer'}]
                result['worker']['State']['Health']['Log'] = [{'End':'between-producer'}]
            if restart_change: result['native']['inspect']['State']['StartedAt'] = 'restarted'
            if late: row['Config']['User'] = '0:0'
            return result
        x.produce = produce
        return x, input_ref, actual, calls

    def test_real_transport_fake_engine_challenge(self):
        x, inp, command, calls = self.child_fixture()
        result = x.child_phase('backup', inp, command)
        self.assertEqual(result['phase'], 'backup')
        self.assertNotIn('start', calls)
        self.assertTrue((self.operation/'backup-ack.json').exists())

    def test_last_producer_changed_child_holds(self):
        x, inp, command, _ = self.child_fixture(late=True)
        with self.assertRaises(p.Held): x.child_phase('backup', inp, command)
        self.assertFalse((self.operation/'backup-ack.json').exists())

    def test_child_actual_ack_grant_refused(self):
        x, inp, command, _ = self.child_fixture(forged=True)
        with self.assertRaises(p.Held): x.child_phase('backup', inp, command)

    def test_actual_producer_inputs_roles(self):
        values = dict(schema=self.sdk, reviewed_selection=self.action, timestamp_evidence=self.proof)
        self.assertEqual(p.producer_inputs(values), values)

    def test_missing_producer_input_refused(self):
        with self.assertRaises(p.Held): p.producer_inputs(dict(schema=self.sdk))

    def test_last_input_read_cannot_change_earlier_input(self):
        values = dict(schema=self.sdk, reviewed_selection=self.action, timestamp_evidence=self.proof)
        real = p.read
        def late(value, private=True):
            raw = real(value, private)
            if value['path'] == self.proof['path']:
                Path(self.sdk['path']).chmod(0o640)
            return raw
        with patch.object(p, 'read', side_effect=late):
            with self.assertRaises(p.Held): p.producer_inputs(values)

    def birth_fixture(self):
        value, actual = self.prebirth(); pending = p._PHASES[self.parent]['prepare']
        fresh = dict(native={'inspect': {}}, worker={}, child_mounts=[], reader={})
        body = dict(version=1, kind='existing-native-configured-scope', invocation=pending['invocation'],
                    native=fresh['native'], worker=fresh['worker'], child_mounts=fresh['child_mounts'],
                    config=dict(path='/data/config.ini', sha256='f'*64, signature9=[0]*9),
                    config_module={}, main_module={}, worker_library='/library', tool_root='/opt/archiving-utils',
                    ancestors={'/': [123, 456, 16877, 1000, 1000], '/app': [123, 457, 16877, 1000, 1000]})
        host_proof = fixture_ref(self.operation/'prepare-input.native-scope.json', p.encode(body))
        child_ref = self.parent.mapping.child_ref(host_proof)
        child_ref['signature9'][0] += 987  # CHILD dev differs from HOST; do not compare.
        message = dict(protocol='reader-lifecycle-pipe-v1', type='birth-commit', nonce='a'*64,
                       input_sha256=value['sha256'], parent_sha256=self.source['sha256'], sequence=2, challenge='c'*64,
                       birth=dict(source_sha256='e'*64, seed_sha256=pending['seed_ref']['sha256'], native_scope=child_ref))
        child = dict(Id='4'*64,Image=self.parent.plan['selected_image'],Name='fixture',Path='/init',Args=[],Config={},HostConfig={},Mounts=[],NetworkSettings={},State=dict(Running=True,Status='running',Pid=123,StartedAt='start',FinishedAt='',ExitCode=0,Error='',Paused=False,Restarting=False,OOMKilled=False,Dead=False))
        self.parent.continuous = lambda: {}
        self.parent.inspect = lambda cid: copy.deepcopy(child)
        return value, actual, message, fresh, child

    def test_birth_actual_child_ref_without_host_dev_guess(self):
        value, actual, message, fresh, child = self.birth_fixture()
        response = p.decode(self.parent.accept_birth('prepare', value, actual, message, fresh, child))
        sidecar = p.decode((self.operation/'prepare-input.lifecycle.json').read_bytes())
        self.assertEqual(sidecar['proofs']['native_scope'], message['birth']['native_scope'])
        self.assertFalse(response['execution_authority']); self.assertFalse(response['publication_acceptance'])
        self.assertEqual(response['type'], 'birth-accepted')
        self.assertTrue(p._PHASES[self.parent]['prepare']['accepted'])

    def test_birth_replay_refused(self):
        args = self.birth_fixture(); self.parent.accept_birth('prepare', *args)
        with self.assertRaises(p.Held): self.parent.accept_birth('prepare', *args)

    def test_birth_wrong_source(self):
        args = self.birth_fixture(); args[2]['birth']['source_sha256'] = '0'*64
        with self.assertRaises(p.Held): self.parent.accept_birth('prepare', *args)

    def test_birth_wrong_seed(self):
        args = self.birth_fixture(); args[2]['birth']['seed_sha256'] = '0'*64
        with self.assertRaises(p.Held): self.parent.accept_birth('prepare', *args)

    def test_birth_wrong_fixed_proof_path(self):
        args = self.birth_fixture(); args[2]['birth']['native_scope']['path'] = '/elsewhere/proof.json'
        with self.assertRaises(p.Held): self.parent.accept_birth('prepare', *args)

    def test_last_birth_callback_changes_proof_holds(self):
        args = self.birth_fixture()
        def late():
            (self.operation/'prepare-input.native-scope.json').chmod(0o640)
            return {}
        self.parent.continuous = late
        with self.assertRaises(p.Held): self.parent.accept_birth('prepare', *args)
        self.assertFalse(p._PHASES[self.parent]['prepare']['accepted'])

    def test_last_birth_callback_changes_child_holds(self):
        args = self.birth_fixture()
        self.parent.inspect = lambda cid: {'Id': cid, 'State': {'Running': False}}
        with self.assertRaises(p.Held): self.parent.accept_birth('prepare', *args)
        self.assertFalse(p._PHASES[self.parent]['prepare']['accepted'])

    def test_last_birth_response_encoding_changes_proof_holds(self):
        args = self.birth_fixture(); real = p.encode
        def late(value):
            raw = real(value)
            if type(value) is dict and value.get('type') == 'birth-accepted':
                (self.operation/'prepare-input.native-scope.json').chmod(0o640)
            return raw
        with patch.object(p, 'encode', side_effect=late):
            with self.assertRaises(p.Held): self.parent.accept_birth('prepare', *args)
        self.assertFalse(p._PHASES[self.parent]['prepare']['accepted'])

    def test_capture_birth_commit_same_sequence_transport(self):
        x, inp, command, _ = self.child_fixture(phase='prepare')
        self.assertEqual(x.child_phase('prepare', inp, command)['phase'], 'prepare')
        self.assertTrue(p._PHASES[x]['prepare']['accepted'])

    def test_ack_without_birth_cannot_complete_prepare(self):
        x, inp, command, _ = self.child_fixture(phase='prepare', skip_birth=True)
        with self.assertRaisesRegex(p.Held, 'before-birth'): x.child_phase('prepare', inp, command)
        self.assertFalse((self.operation/'prepare-input.lifecycle.json').exists())

    def test_birth_out_of_sequence_cannot_create_sidecar(self):
        x, inp, command, _ = self.child_fixture(phase='prepare', bad_sequence=True)
        with self.assertRaises(p.Held): x.child_phase('prepare', inp, command)
        self.assertFalse((self.operation/'prepare-input.lifecycle.json').exists())

    def real_scope_fixture(self):
        source = ROOT / '_reader_parent_fixtures' / 'fixture_scope.py'
        copied = fixture_ref(self.root/'scope.py', source.read_bytes())
        projector = p.pinned_module(copied)
        p._PROJECTORS[self.parent] = projector.observed_native
        self.parent.plan['scope_projection'] = copied
        census = dict(version=1, epoch='a'*64, revision=0, keys=[], digest=hashlib.sha256(b'[]').hexdigest())
        row = dict(Id='1'*64, Image='sha256:'+'2'*64, Name='native', Path='/python', Args=['daemon'],
                   Config={}, HostConfig={}, Mounts=[], NetworkSettings={},
                   State=dict(Running=True, Status='running', Pid=123, StartedAt='exact-start', Paused=False,
                              Restarting=False, Dead=False, OOMKilled=False))
        return dict(inspect=row, process=dict(pid=124, start_ticks=789, argv=['python','daemon']),
                    publication=dict(state='held', reason='startup-restart-required', census=census, request_counter=1))

    def test_actual_scope_counter_only_change_permitted(self):
        original = self.real_scope_fixture(); changed = copy.deepcopy(original)
        changed['publication']['request_counter'] = 222
        self.assertTrue(self.parent.native_equivalent(original, changed))

    def test_actual_scope_process_pid_change_held(self):
        original = self.real_scope_fixture(); changed = copy.deepcopy(original); changed['process']['pid'] += 1
        self.assertFalse(self.parent.native_equivalent(original, changed))

    def test_actual_scope_startticks_change_held(self):
        original = self.real_scope_fixture(); changed = copy.deepcopy(original); changed['process']['start_ticks'] += 1
        self.assertFalse(self.parent.native_equivalent(original, changed))

    def test_actual_scope_image_change_held(self):
        original = self.real_scope_fixture(); changed = copy.deepcopy(original); changed['inspect']['Image'] = 'sha256:'+'3'*64
        self.assertFalse(self.parent.native_equivalent(original, changed))

    def test_actual_scope_complete_census_change_held(self):
        original = self.real_scope_fixture(); changed = copy.deepcopy(original)
        changed['publication']['census'].update(keys=['4'*64], revision=1,
                                              digest=hashlib.sha256(p.encode(['4'*64])).hexdigest())
        self.assertFalse(self.parent.native_equivalent(original, changed))

    def test_scope_source_mode_change_held(self):
        original = self.real_scope_fixture(); Path(self.parent.plan['scope_projection']['path']).chmod(0o640)
        with self.assertRaises(p.Held): self.parent.native_equivalent(original, original)

    def projected_birth_fixture(self, census_change=False):
        args = self.birth_fixture()
        original = self.real_scope_fixture(); current = copy.deepcopy(original)
        current['publication']['request_counter'] += 1
        if census_change:
            current['publication']['census']['epoch'] = '5'*64
        path = self.operation/'prepare-input.native-scope.json'
        body = p.decode(path.read_bytes()); body['native'] = original
        host_ref = fixture_ref(path, p.encode(body))
        args[2]['birth']['native_scope'] = self.parent.mapping.child_ref(host_ref)
        args[3]['native'] = current
        x = self.parent
        x.core = p.encode(dict(plan=x.plan, files=x.files, nodes=x.nodes, source=x.source_ref,
                              input=x.plan_ref, engine=id(x.engine), thread=x.thread, deadline=x.deadline))
        p._CORES[x] = x.core
        return args

    def test_whole_birth_counter_only_commit_accepted(self):
        args = self.projected_birth_fixture()
        reply = p.decode(self.parent.accept_birth('prepare', *args))
        self.assertEqual(reply['type'], 'birth-accepted')
        self.assertFalse(reply['publication_acceptance'])

    def test_whole_birth_census_change_no_sidecar(self):
        args = self.projected_birth_fixture(census_change=True)
        with self.assertRaises(p.Held): self.parent.accept_birth('prepare', *args)
        self.assertFalse((self.operation/'prepare-input.lifecycle.json').exists())

    def admit_original_control(self, control):
        x = self.parent
        x.files[control['path']] = tuple(control['signature9'])
        x.nodes.update(p.parents(Path(control['path'])))
        x.core = p.encode(dict(plan=x.plan, files=x.files, nodes=x.nodes, source=x.source_ref,
                              input=x.plan_ref, engine=id(x.engine), thread=x.thread, deadline=x.deadline))
        p._CORES[x] = x.core

    def test_literal_last_inspect_chmods_original_source_held(self):
        args = self.birth_fixture(); self.admit_original_control(self.source)
        def late(cid):
            Path(self.source['path']).chmod(0o640)
            return copy.deepcopy(args[-1])
        self.parent.inspect = late
        with self.assertRaises(p.Held): self.parent.accept_birth('prepare', *args)
        self.assertFalse(p._PHASES[self.parent]['prepare']['accepted'])
        self.assertTrue((self.operation/'prepare-input.lifecycle.json').exists())

    def test_last_inspect_replaces_samebytes_original_held(self):
        args = self.birth_fixture(); self.admit_original_control(self.source)
        def late(cid):
            path = Path(self.source['path']); raw = path.read_bytes(); path.unlink(); fixture_ref(path, raw)
            return copy.deepcopy(args[-1])
        self.parent.inspect = late
        with self.assertRaises(p.Held): self.parent.accept_birth('prepare', *args)
        self.assertFalse(p._PHASES[self.parent]['prepare']['accepted'])

    def test_literal_last_inspect_chmods_scope_projection_held(self):
        args = self.projected_birth_fixture()
        control = self.parent.plan['scope_projection']; self.admit_original_control(control)
        def late(cid):
            Path(control['path']).chmod(0o640)
            return copy.deepcopy(args[-1])
        self.parent.inspect = late
        with self.assertRaises(p.Held): self.parent.accept_birth('prepare', *args)
        self.assertFalse(p._PHASES[self.parent]['prepare']['accepted'])

    def continuous_fixture(self):
        x = self.parent
        def row(kind):
            state = dict(Status=kind, Running=kind=='running', Paused=False, Restarting=False,
                         OOMKilled=False, Dead=False, Pid=123 if kind=='running' else 0,
                         ExitCode=0, Error='', StartedAt='start', FinishedAt='finish',
                         Health=dict(Status='healthy', FailingStreak=0, Log=[{'End':'old'}]))
            return dict(Id={'running':'2','created':'3','exited':'1'}[kind]*64,
                        Image='sha256:'+'b'*64, Name=kind, Path='/init', Args=[], Config={},
                        HostConfig={}, Mounts=[], NetworkSettings={}, State=state)
        values = dict(reader=row('exited'), held_native=row('running'), held_worker=row('created'))
        x.baselines = copy.deepcopy(values); x.stop_state = copy.deepcopy(values['reader']['State'])
        for key,value in values.items(): x.plan[key] = dict(id=value['Id'])
        x.plan.update(producer=self.provider,observer=self.provider)
        x.inspect = lambda cid: next(copy.deepcopy(v) for v in values.values() if v['Id']==cid)
        x.events = lambda: None
        x.core = p.encode(dict(plan=x.plan, files=x.files, nodes=x.nodes, source=x.source_ref,
                              input=x.plan_ref, engine=id(x.engine), thread=x.thread, deadline=x.deadline))
        p._CORES[x] = x.core
        return values

    def test_genuine_continuous_health_logs_only_allowed(self):
        values = self.continuous_fixture()
        for value in values.values(): value['State']['Health'] = dict(Status='unhealthy',FailingStreak=9,Log=[{'End':'later'}])
        self.assertEqual(p.LifecycleParent.continuous(self.parent),values)

    def test_between_continuous_producer_health_only_allowed(self):
        x, inp, command, calls = self.child_fixture(health_change=True)
        self.assertEqual(x.child_phase('backup', inp, command)['phase'],'backup')

    def test_between_continuous_producer_restart_held(self):
        x, inp, command, calls = self.child_fixture(restart_change=True)
        with self.assertRaisesRegex(p.Held,'fresh-native-worker-mounts'): x.child_phase('backup', inp, command)

    def test_genuine_continuous_native_restart_held(self):
        values=self.continuous_fixture(); values['held_native']['State']['StartedAt']='new'
        with self.assertRaises(p.Held): p.LifecycleParent.continuous(self.parent)

    def test_genuine_continuous_native_pause_held(self):
        values=self.continuous_fixture(); values['held_native']['State']['Paused']=True
        with self.assertRaises(p.Held): p.LifecycleParent.continuous(self.parent)

    def test_genuine_continuous_native_exit_held(self):
        values=self.continuous_fixture(); values['held_native']['State'].update(Status='exited',Running=False,Pid=0)
        with self.assertRaises(p.Held): p.LifecycleParent.continuous(self.parent)

    def test_genuine_continuous_native_image_held(self):
        values=self.continuous_fixture(); values['held_native']['Image']='sha256:'+'c'*64
        with self.assertRaises(p.Held): p.LifecycleParent.continuous(self.parent)

    def test_genuine_continuous_native_network_held(self):
        values=self.continuous_fixture(); values['held_native']['NetworkSettings']['Networks']={'unexpected':{}}
        with self.assertRaises(p.Held): p.LifecycleParent.continuous(self.parent)

    def test_genuine_continuous_native_mount_held(self):
        values=self.continuous_fixture(); values['held_native']['Mounts'].append({'Source':'/foreign'})
        with self.assertRaises(p.Held): p.LifecycleParent.continuous(self.parent)

    def test_genuine_continuous_unknown_lifecycle_field_held(self):
        values=self.continuous_fixture(); values['held_native']['State']['Unknown']=True
        with self.assertRaises(p.Held): p.LifecycleParent.continuous(self.parent)

    def test_genuine_continuous_reader_pid_held(self):
        values=self.continuous_fixture(); values['reader']['State']['Pid']=4
        with self.assertRaises(p.Held): p.LifecycleParent.continuous(self.parent)

    def test_unknown_execute_ack_does_not_resume(self):
        x = self.parent; calls = []
        x.plan['reader'] = dict(id='1' * 64)
        x.core = p.encode(dict(plan=x.plan, files={}, nodes={}, source=x.source_ref, input=x.plan_ref,
                              engine=id(x.engine), thread=x.thread, deadline=x.deadline)); p._CORES[x] = x.core
        class FakeEngine:
            def run(_, args, seconds):
                calls.append(args)
                if args[0] == 'stop': return ('1' * 64).encode()
                raise AssertionError('unexpected actual engine operation')
        x.engine = FakeEngine()
        x.core = p.encode(dict(plan=x.plan, files={}, nodes={}, source=x.source_ref, input=x.plan_ref,
                              engine=id(x.engine), thread=x.thread, deadline=x.deadline)); p._CORES[x] = x.core
        x.continuous = lambda: dict(reader=dict(State={}, Mounts=[]))
        x.child_phase = lambda *args: (_ for _ in ()).throw(p.Held('unknown-child-ACK'))
        with self.assertRaisesRegex(p.Held, 'no-replay-or-resume'): x.execute()
        self.assertFalse(any(args[0] == 'start' for args in calls))
        self.assertEqual(x.phase, 'uncertain')


if __name__ == '__main__':
    unittest.main()
