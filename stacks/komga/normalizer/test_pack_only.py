"""Selected capture controls; original copy/ACK suites remain separate."""
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import test_pack_recovery

HERE=Path(__file__).parent

class SelectedPackTests(unittest.TestCase):
    def fixture(self):
        f=test_pack_recovery.PackTest();f.setUp();self.addCleanup(f.doCleanups)
        f.archive(f.pack/'Test Comic 001 (2017).cbz',extra=False)
        f.record['source_generation']=test_pack_recovery.source_state(f.pack,content=True)
        f.m.mylar=Mock(side_effect=lambda command,**kw:{'enabled':True,'packs':[f.record], 'protected':['/cache/pack']}
            if command=='packWork' else {'phase':'review'})
        return f

    def test_real_inventory_selected_pass_resumes_exact_receipt_no_scan(self):
        f=self.fixture()
        # Source ownership/inventory/hash/copy are genuine. Member action is held
        # deliberately; this test does not synthesize a native ACK or import.
        with patch.object(f.packs,'member',side_effect=lambda member,directory:member.update(phase='review',reason='fixture hold')):
            f.packs.cycle('a'*64,'1',scan=False)
            receipt=f.packs.root/('a'*64)/'receipt.json';first=json.loads(receipt.read_text())
            self.assertTrue(first['inventory_complete']);self.assertTrue(first['members'])
            f.packs.cycle('a'*64,'1',scan=False)
            second=json.loads(receipt.read_text())
        self.assertEqual([m['id'] for m in first['members']],[m['id'] for m in second['members']])
        self.assertTrue((f.pack/'Test Comic 001 (2017).cbz').exists())
        f.worker.reader.call.assert_not_called()

    def test_other_capture_is_rejected_before_inventory_even_same_ddl(self):
        f=self.fixture()
        with patch.object(f.packs,'inventory') as inventory,self.assertRaises(ValueError):
            f.packs.cycle('b'*64,'1',scan=False)
        inventory.assert_not_called()

    def test_import_dispatch_empty_selected_set_ignores_unrelated_prepared(self):
        f=self.fixture();f.worker.config['writer_state']=str(f.root/'writer')
        from media_writer import Writer
        Writer(f.worker.config['writer_state'],create=True)
        root=f.m.state/'imports';root.mkdir();(root/('b'*64+'.json')).write_text('{"phase":"prepared"}')
        from import_recovery import dispatch_prepared
        with patch('import_recovery.handoff_read',side_effect=AssertionError('unrelated receipt read')):
            self.assertEqual(dispatch_prepared(f.m,()),0)

    def test_native_dispatch_empty_selected_set_ignores_unrelated_prepared(self):
        f=self.fixture();f.worker.config['writer_state']=str(f.root/'writer')
        from media_writer import Writer
        Writer(f.worker.config['writer_state'],create=True)
        root=f.m.state/'native-handoffs';root.mkdir();(root/('b'*64+'.json')).write_text('{"phase":"prepared"}')
        from native_handoff import dispatch
        with patch('native_handoff.handoff_read',side_effect=AssertionError('unrelated receipt read')):
            self.assertEqual(dispatch(f.m,()),0)

    def test_cli_refuses_combined_health_before_config_read(self):
        import normalize
        with patch('sys.argv',['normalize.py','--config','/does-not-exist','--health','--pack-capture','a'*64,'--pack-ddl','1']),self.assertRaises(SystemExit) as error:
            normalize.main()
        self.assertEqual(error.exception.code,2)


from test_publication_guard import AuthorityFixture
class OwnedPassTests(AuthorityFixture, unittest.TestCase):
    def setup_pass(self):
        import publication_guard as g
        import pack_only
        from publication_guard import NativeBatch
        state=self.root/'worker-state';state.mkdir();(state/'jobs').mkdir()
        cfg={'writer_state':str(self.writer.root),'mylar':{'config_dir':str(self.config)},
             'publication_roots':[{'native':str(self.native_root),'worker':str(self.library)}],
             'maintenance':{'pack_import':True}}
        worker=SimpleNamespace(config=cfg,state=state,jobs=state/'jobs',roots=[self.library])
        record={'id':'a'*64,'ddl_id':'1','source':'/cache/original'}
        batch=NativeBatch(worker,{'packWork':{'enabled':True,'packs':[record]}})
        m=SimpleNamespace(worker=worker,state=state/'maintenance',prepare=Mock(return_value=batch),idle=lambda:True)
        original=g.Authority.__init__
        def init(value,config,writer,mappings,**kw):return original(value,config,writer,mappings,tool_root=self.tool)
        return pack_only,worker,m,init

    def test_real_writer_and_sql_authority_pass_without_bulk_or_unrelated_dispatch(self):
        module,worker,m,init=self.setup_pass()
        def owned_cycle(*args,**kw):
            from publication_guard import current
            self.assertEqual(current(worker).writer.root, self.writer.root)
            self.assertTrue(self.writer.fenced())
            self.assertEqual(args,('a'*64,'1'));self.assertEqual(kw,{'scan':False})
        with patch('publication_guard.Authority.__init__',init),patch.object(module,'Maintenance',return_value=m),patch.object(module,'Packs') as packs,patch('import_recovery.dispatch_prepared',return_value=0) as imports,patch('native_handoff.dispatch',return_value=0) as reports:
            packs.return_value.cycle.side_effect=owned_cycle
            result=module.run(worker,'a'*64,'1')
        self.assertFalse(result['complete']);imports.assert_called_once_with(m,());reports.assert_called_once_with(m,())
        self.assertFalse(self.writer.fenced())

    def test_cli_preserves_zero_request_and_finite_dispatch_diagnostic(self):
        module,worker,m,init=self.setup_pass()
        diagnostic=dict(state='held',stage='health',reason='protocol-unavailable',exception=None)
        def dispatch(*args):m.import_dispatch_status=dict(diagnostic);return 0
        with patch('publication_guard.Authority.__init__',init),patch.object(module,'Maintenance',return_value=m),patch.object(module,'Packs'),patch('import_recovery.dispatch_prepared',side_effect=dispatch),patch('native_handoff.dispatch',return_value=0):
            result=module.run(worker,'a'*64,'1')
        self.assertEqual(result['import_requests'],0);self.assertFalse(result['complete']);self.assertEqual(result['import_dispatch'],diagnostic)

    def test_contended_real_writer_refuses_before_native_collection(self):
        module,worker,m,init=self.setup_pass()
        from media_writer import Busy
        import os,fcntl
        fd=os.open(self.writer.lock,os.O_RDWR)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with patch.object(module,'Maintenance',return_value=m),self.assertRaises(Busy):
                module.run(worker,'a'*64,'1')
        finally:os.close(fd)
        m.prepare.assert_not_called()

    def test_uncertain_selected_pass_retains_real_pending_fence(self):
        module,worker,m,init=self.setup_pass()
        with patch('publication_guard.Authority.__init__',init),patch.object(module,'Maintenance',return_value=m),patch.object(module,'Packs') as packs:
            packs.return_value.cycle.side_effect=RuntimeError('fixture uncertainty')
            with self.assertRaises(RuntimeError):module.run(worker,'a'*64,'1')
        self.assertTrue(self.writer.fenced())

class ProducedReceiptTests(unittest.TestCase):
    def test_existing_selected_native_receipt_is_recollected_and_only_it_dispatched(self):
        from test_native_handoff import HandoffTest
        from native_handoff import dispatch
        f=HandoffTest();f.setUp();self.addCleanup(f.doCleanups)
        f.m._pack_only_native=set();selected=f.prepare()
        f.arguments=dict(f.arguments,catalog_attempt='2');f.prepare()
        unrelated=next(p for p in (f.m.state/'native-handoffs').glob('*.json') if p!=selected)
        f.arguments=dict(f.arguments,catalog_attempt='1');f.m._pack_only_native.clear();f.prepare()
        self.assertEqual(f.m._pack_only_native,{selected})
        def selected_api(command,**kwargs):
            if command=='getHealth':return f.api(command,**kwargs)
            self.assertFalse(getattr(f.writer.local[1],'depth',0))
            self.assertFalse(f.writer.fenced())
            self.assertEqual(command,'packCatalog')
            packet=json.loads(kwargs['maintenance_handoff'])
            self.assertEqual(packet['token'],selected.stem)
            self.assertEqual(json.loads(selected.read_text())['phase'],'dispatching')
            self.assertEqual(packet['sources'][0]['path'],str(f.native_root/f.source.name))
            return {'phase':'ready','issueid':'999','comicid':'888'}
        f.m.mylar.side_effect=selected_api
        with patch('native_handoff.scope',f.portable):
            self.assertEqual(dispatch(f.m,tuple(f.m._pack_only_native)),1)
            self.assertEqual(dispatch(f.m,tuple(f.m._pack_only_native)),0)
        self.assertEqual(sum(call.args[0]=='packCatalog' for call in f.m.mylar.call_args_list),1)
        self.assertEqual(json.loads(unrelated.read_text())['phase'],'prepared')
        self.assertEqual(json.loads(selected.read_text())['phase'],'complete')

    def test_existing_selected_import_is_recollected_without_replaying_uncertain_reply(self):
        from test_import_recovery import CoordinatedRecoveryTest
        from import_recovery import submit,dispatch_prepared
        from publication_guard import scope
        f=CoordinatedRecoveryTest();f.setUp();self.addCleanup(f.doCleanups)
        f.m._pack_only_imports=set();source,receipt=f.prepared()
        f.m._pack_only_imports.clear()
        with f.writer.hold(),scope(f.m.worker,f.writer) as authority:
            authority.tool_root=f.tool
            self.assertEqual(submit(f.m,source,f.match),'import_review')
        self.assertEqual(f.m._pack_only_imports,{receipt})
        # Existing typed dispatch is genuine; the remote HTTP result is an
        # explicit fixture boundary, not an ordinary import acknowledgement.
        f.m.mylar.side_effect=f.native_api
        self.assertEqual(f.dispatch(),1)
        original=receipt.read_bytes()
        self.assertEqual(dispatch_prepared(f.m,tuple(f.m._pack_only_imports)),0)
        self.assertEqual(receipt.read_bytes(),original)


class AdmissionWaitTests(AuthorityFixture, unittest.TestCase):
    def selected(self):
        return OwnedPassTests.setup_pass(self)

    def execute(self, module, worker, maintenance, init, cycle=None, **kwargs):
        with (patch('publication_guard.Authority.__init__', init),
              patch.object(module, 'Maintenance', return_value=maintenance),
              patch.object(module, 'Packs') as packs,
              patch('import_recovery.dispatch_prepared', return_value=0),
              patch('native_handoff.dispatch', return_value=0)):
            packs.return_value.cycle.side_effect = cycle
            result = module.run(worker, 'a' * 64, '1', **kwargs)
        return result, packs

    def lock(self):
        import os, fcntl
        fd = os.open(self.writer.lock, os.O_RDWR)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd

    def test_initial_real_contention_releases_outside_writer(self):
        import fcntl
        module, worker, maintenance, init = self.selected()
        fd = self.lock()
        batch = maintenance.prepare.return_value
        def prepare(*args):
            self.assertFalse(getattr(self.writer.local[1], 'depth', 0))
            self.assertFalse(self.writer.fenced())
            return batch
        maintenance.prepare.side_effect = prepare
        with patch('pack_only.time.sleep', side_effect=lambda _: fcntl.flock(fd, fcntl.LOCK_UN)) as sleep:
            result, packs = self.execute(module, worker, maintenance, init, admission_wait=30)
        self.assertEqual(sleep.call_count, 1)
        maintenance.prepare.assert_called_once_with('a' * 64, '1')
        packs.return_value.cycle.assert_called_once_with('a' * 64, '1', scan=False)
        self.assertEqual(result['import_requests'], 0)
        self.assertFalse(self.writer.fenced())

    def test_second_real_contention_recollects_fresh_batch(self):
        import fcntl, os
        from publication_guard import NativeBatch
        module, worker, maintenance, init = self.selected()
        fd = os.open(self.writer.lock, os.O_RDWR)
        self.addCleanup(os.close, fd)
        batches = []
        def prepare(*args):
            self.assertFalse(getattr(self.writer.local[1], 'depth', 0))
            batch = NativeBatch(worker, {'packWork': {'enabled': True, 'packs': [{'id': 'a' * 64, 'ddl_id': '1'}]}})
            batches.append(batch)
            if len(batches) == 1: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return batch
        maintenance.prepare.side_effect = prepare
        with patch('pack_only.time.sleep', side_effect=lambda _: fcntl.flock(fd, fcntl.LOCK_UN)) as sleep:
            def cycle(*args, **kwargs):
                from publication_guard import current
                self.assertIs(current(worker).native_batch, batches[-1])
            _, packs = self.execute(module, worker, maintenance, init, cycle=cycle, admission_wait=30)
        self.assertEqual(sleep.call_count, 1)
        self.assertEqual(maintenance.prepare.call_count, 2)
        self.assertIsNot(batches[0], batches[1])
        packs.return_value.cycle.assert_called_once()

    def test_persistent_real_contention_elapsed_and_attempt_bounds(self):
        from media_writer import Busy
        module, worker, maintenance, init = self.selected()
        self.lock()
        clock = [100.0]
        def pause(seconds): clock[0] += seconds
        with (patch('pack_only.time.monotonic', side_effect=lambda: clock[0]),
              patch('pack_only.time.sleep', side_effect=pause) as sleep, self.assertRaises(Busy)):
            self.execute(module, worker, maintenance, init, admission_wait=1)
        self.assertLessEqual(sum(c.args[0] for c in sleep.call_args_list), 1)
        self.assertLessEqual(sleep.call_count, 2)
        with (patch('pack_only.time.monotonic', return_value=100),
              patch('pack_only.time.sleep') as sleep, self.assertRaises(Busy)):
            self.execute(module, worker, maintenance, init, admission_wait=120)
        self.assertLessEqual(sleep.call_count, 240)
        maintenance.prepare.assert_not_called()

    def test_all_durable_markers_refuse_without_wait_or_prepare(self):
        from media_writer import Busy
        module, worker, maintenance, init = self.selected()
        names = ('normalizer-v1.pending', 'tagger-v2.pending', 'release-v1.pending',
                 'normalizer-state-adoption-v1.pending', 'negative-retirement-v1.pending',
                 'negative-retirement-v1.terminal-pending', 'archive-repair-v1.pending',
                 'archive-repair-v1.terminal-pending')
        for name in names:
            with self.subTest(marker=name):
                path = self.writer.root / name
                path.write_bytes(b'retained pending')
                try:
                    with patch('pack_only.time.sleep') as sleep, self.assertRaises(Busy):
                        self.execute(module, worker, maintenance, init, admission_wait=30)
                    maintenance.prepare.assert_not_called(); sleep.assert_not_called()
                    self.assertEqual(path.read_bytes(), b'retained pending')
                finally: path.unlink()

    def test_pending_born_during_prepare_is_not_retried(self):
        from media_writer import Busy
        module, worker, maintenance, init = self.selected()
        batch = maintenance.prepare.return_value
        def prepare(*args):
            self.writer.create_file(self.writer.pending)
            return batch
        maintenance.prepare.side_effect = prepare
        with patch('pack_only.time.sleep') as sleep, self.assertRaises(Busy):
            self.execute(module, worker, maintenance, init, admission_wait=30)
        sleep.assert_not_called(); self.assertEqual(maintenance.prepare.call_count, 1)
        self.assertTrue(self.writer.fenced())

    def test_scope_and_processing_busy_never_replay(self):
        from media_writer import Busy
        from contextlib import contextmanager
        module, worker, maintenance, init = self.selected()
        @contextmanager
        def refused_scope(*args, **kwargs):
            raise Busy('scope refusal is not a lock-entry retry')
            yield
        with patch.object(module, 'scope', refused_scope), patch('pack_only.time.sleep') as sleep, self.assertRaises(Busy):
            self.execute(module, worker, maintenance, init, admission_wait=30)
        sleep.assert_not_called(); maintenance.prepare.assert_not_called()
        with (patch('publication_guard.Authority.__init__', init), patch.object(module, 'Maintenance', return_value=maintenance),
              patch.object(module, 'Packs') as packs, patch('pack_only.time.sleep') as sleep, self.assertRaises(Busy)):
            packs.return_value.cycle.side_effect = Busy('downstream uncertainty')
            module.run(worker, 'a' * 64, '1', admission_wait=30)
        sleep.assert_not_called(); self.assertEqual(maintenance.prepare.call_count, 1)
        packs.return_value.cycle.assert_called_once(); self.assertTrue(self.writer.fenced())

    def test_prepare_errors_never_retry(self):
        from media_writer import Busy
        from publication_guard import Unavailable
        module, worker, maintenance, init = self.selected()
        for error in (Busy('not lock admission'), Unavailable('missing authenticated reply')):
            with self.subTest(error=type(error).__name__):
                maintenance.prepare.reset_mock(); maintenance.prepare.side_effect = error
                with patch('pack_only.time.sleep') as sleep, self.assertRaises(type(error)):
                    self.execute(module, worker, maintenance, init, admission_wait=30)
                self.assertEqual(maintenance.prepare.call_count, 1); sleep.assert_not_called()

    def test_invalid_wait_refuses_before_prepare(self):
        module, worker, maintenance, init = self.selected()
        for value in (True, -1, 121, 0.5, float('nan')):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                self.execute(module, worker, maintenance, init, admission_wait=value)
        maintenance.prepare.assert_not_called()

    def test_cli_enables_wait_without_new_flags(self):
        import normalize, tempfile
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary); config = state / 'config.json'
            config.write_text(json.dumps({'state': str(state)})); worker = SimpleNamespace()
            with (patch('sys.argv', ['normalize.py', '--config', str(config), '--pack-capture', 'a' * 64, '--pack-ddl', '1']),
                  patch.object(normalize, 'Normalizer', return_value=worker),
                  patch('pack_only.run', return_value={'complete': False}) as selected):
                normalize.main()
            selected.assert_called_once_with(worker, 'a' * 64, '1', admission_wait=30)

    def test_adoption_born_during_prepare_refuses_before_scope_or_binding(self):
        from media_writer import Busy
        module, worker, maintenance, init = self.selected()
        batch = maintenance.prepare.return_value
        marker = self.writer.root / 'normalizer-state-adoption-v1.pending'
        def prepare(*args):
            marker.write_bytes(b'original adoption')
            return batch
        maintenance.prepare.side_effect = prepare
        with patch('pack_only.time.sleep') as sleep, patch.object(module, 'bind_state') as bind, self.assertRaises(Busy):
            self.execute(module, worker, maintenance, init, admission_wait=30)
        sleep.assert_not_called(); bind.assert_not_called()
        self.assertEqual(maintenance.prepare.call_count, 1)
        self.assertEqual(marker.read_bytes(), b'original adoption')

    def test_symlink_pending_is_presence_not_absence(self):
        from media_writer import Busy
        module, worker, maintenance, init = self.selected()
        target = self.root / 'retained'; target.write_bytes(b'opaque pending')
        marker = self.writer.root / 'archive-repair-v1.pending'; marker.symlink_to(target)
        with patch('pack_only.time.sleep') as sleep, self.assertRaises(Busy):
            self.execute(module, worker, maintenance, init, admission_wait=30)
        sleep.assert_not_called(); maintenance.prepare.assert_not_called()
        self.assertTrue(marker.is_symlink()); self.assertEqual(target.read_bytes(), b'opaque pending')

    def test_second_acquired_scope_busy_is_not_retried(self):
        from contextlib import contextmanager
        from media_writer import Busy
        module, worker, maintenance, init = self.selected()
        original = module.scope
        @contextmanager
        def second_refusal(*args, **kwargs):
            if kwargs.get('native_batch') is not None:
                raise Busy('acquired publication scope requires review')
            with original(*args, **kwargs) as authority:
                yield authority
        with (patch.object(module, 'scope', second_refusal), patch('pack_only.time.sleep') as sleep,
              patch.object(module, 'bind_state') as bind, self.assertRaises(Busy)):
            self.execute(module, worker, maintenance, init, admission_wait=30)
        sleep.assert_not_called(); bind.assert_not_called()
        self.assertEqual(maintenance.prepare.call_count, 1); self.assertFalse(self.writer.fenced())

    def test_dispatch_busy_is_never_replayed(self):
        from media_writer import Busy
        module, worker, maintenance, init = self.selected()
        with (patch('publication_guard.Authority.__init__', init), patch.object(module, 'Maintenance', return_value=maintenance),
              patch.object(module, 'Packs') as packs, patch('pack_only.time.sleep') as sleep,
              patch('import_recovery.dispatch_prepared', side_effect=Busy('uncertain dispatch')) as dispatch,
              patch('native_handoff.dispatch') as reports, self.assertRaises(Busy)):
            module.run(worker, 'a' * 64, '1', admission_wait=30)
        sleep.assert_not_called(); self.assertEqual(maintenance.prepare.call_count, 1)
        packs.return_value.cycle.assert_called_once(); dispatch.assert_called_once(); reports.assert_not_called()
        self.assertFalse(self.writer.fenced())

    def test_lock_replacement_during_wait_is_not_adopted(self):
        import fcntl
        from media_writer import PROTOCOL
        module, worker, maintenance, init = self.selected()
        fd = self.lock()
        def replaced(_):
            fcntl.flock(fd, fcntl.LOCK_UN)
            replacement = self.writer.root / 'new-lock'; replacement.write_bytes(PROTOCOL)
            replacement.chmod(0o600); replacement.replace(self.writer.lock)
        with patch('pack_only.time.sleep', side_effect=replaced) as sleep, self.assertRaisesRegex(ValueError, 'lock changed'):
            self.execute(module, worker, maintenance, init, admission_wait=30)
        self.assertEqual(sleep.call_count, 1); maintenance.prepare.assert_not_called()

    def test_pending_after_probe_release_refuses_before_prepare(self):
        from contextlib import contextmanager
        from media_writer import Busy, Writer
        module, worker, maintenance, init = self.selected()
        original = Writer.hold
        calls = []
        marker = self.writer.root / 'normalizer-state-adoption-v1.pending'
        @contextmanager
        def hold(writer, **kwargs):
            calls.append(kwargs)
            with original(writer, **kwargs):
                yield writer
            if len(calls) == 1:
                self.assertFalse(getattr(writer.local[1], 'depth', 0))
                marker.write_bytes(b'original adoption')
        with patch.object(Writer, 'hold', hold), patch('pack_only.time.sleep') as sleep, self.assertRaises(Busy):
            self.execute(module, worker, maintenance, init, admission_wait=30)
        sleep.assert_not_called(); maintenance.prepare.assert_not_called()
        self.assertEqual(marker.read_bytes(), b'original adoption')


if __name__ == '__main__':
    unittest.main()


class PreparationAdmissionTests(AuthorityFixture, unittest.TestCase):
    selected = AdmissionWaitTests.selected
    execute = AdmissionWaitTests.execute

    def test_real_remote_prepare_contention_recollects_before_processing(self):
        import fcntl, os
        from publication_guard import remote_unlocked
        module, worker, maintenance, init = self.selected()
        fd = os.open(self.writer.lock, os.O_RDWR)
        self.addCleanup(os.close, fd)
        batch = maintenance.prepare.return_value
        def prepare(*args):
            self.assertFalse(getattr(self.writer.local[1], 'depth', 0))
            if maintenance.prepare.call_count == 1:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            remote_unlocked(worker)
            return batch
        maintenance.prepare.side_effect = prepare
        with patch('pack_only.time.sleep', side_effect=lambda _: fcntl.flock(fd, fcntl.LOCK_UN)) as sleep:
            _, packs = self.execute(module, worker, maintenance, init, admission_wait=30)
        self.assertEqual(maintenance.prepare.call_count, 2)
        sleep.assert_called_once()
        packs.return_value.cycle.assert_called_once()
        self.assertFalse(self.writer.fenced())

    def test_real_prepare_contention_uses_same_deadline_and_attempt_cap(self):
        import fcntl, os
        from publication_guard import remote_unlocked, RemoteWriterBusy
        module, worker, maintenance, init = self.selected()
        fd = os.open(self.writer.lock, os.O_RDWR)
        self.addCleanup(os.close, fd)
        def prepare(*args):
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try: remote_unlocked(worker)
            finally: fcntl.flock(fd, fcntl.LOCK_UN)
        maintenance.prepare.side_effect = prepare
        clock = [100.0]
        with (patch('pack_only.time.monotonic', side_effect=lambda: clock[0]),
              patch('pack_only.time.sleep', side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)) as sleep,
              self.assertRaises(RemoteWriterBusy)):
            self.execute(module, worker, maintenance, init, admission_wait=1)
        self.assertEqual(maintenance.prepare.call_count, 2)
        self.assertEqual(sum(c.args[0] for c in sleep.call_args_list), 1)
        maintenance.prepare.reset_mock()
        with (patch('pack_only.time.monotonic', return_value=100), patch('pack_only.time.sleep') as sleep,
              self.assertRaises(RemoteWriterBusy)):
            self.execute(module, worker, maintenance, init, admission_wait=120)
        self.assertEqual(maintenance.prepare.call_count, module._ADMISSION_ATTEMPTS)
        self.assertEqual(sleep.call_count, module._ADMISSION_ATTEMPTS - 1)
        self.assertFalse(self.writer.fenced())

    def test_prepare_contention_default_wait_does_not_retry(self):
        from publication_guard import RemoteWriterBusy
        module, worker, maintenance, init = self.selected()
        maintenance.prepare.side_effect = RemoteWriterBusy('remote admission')
        with patch('pack_only.time.sleep') as sleep, self.assertRaises(RemoteWriterBusy):
            self.execute(module, worker, maintenance, init)
        maintenance.prepare.assert_called_once(); sleep.assert_not_called()

    def test_recovery_born_during_prepare_never_waits(self):
        from publication_guard import RemoteWriterBusy
        module, worker, maintenance, init = self.selected()
        for name in module._RECOVERY_MARKERS:
            path = self.writer.root / name
            def prepare(*args):
                path.write_bytes(b'original recovery')
                raise RemoteWriterBusy('remote admission')
            maintenance.prepare.reset_mock(); maintenance.prepare.side_effect = prepare
            try:
                with self.subTest(marker=name), patch('pack_only.time.sleep') as sleep, self.assertRaises(RemoteWriterBusy):
                    self.execute(module, worker, maintenance, init, admission_wait=30)
                maintenance.prepare.assert_called_once(); sleep.assert_not_called()
                self.assertEqual(path.read_bytes(), b'original recovery')
            finally: path.unlink()

    def test_typed_contention_after_processing_never_replays(self):
        from publication_guard import RemoteWriterBusy
        module, worker, maintenance, init = self.selected()
        with (patch('publication_guard.Authority.__init__', init), patch.object(module, 'Maintenance', return_value=maintenance),
              patch.object(module, 'Packs') as packs, patch('pack_only.time.sleep') as sleep,
              self.assertRaises(RemoteWriterBusy)):
            packs.return_value.cycle.side_effect = RemoteWriterBusy('processing is outside admission')
            module.run(worker, 'a' * 64, '1', admission_wait=30)
        maintenance.prepare.assert_called_once(); packs.return_value.cycle.assert_called_once()
        sleep.assert_not_called(); self.assertTrue(self.writer.fenced())

    def test_remote_probe_distinguishes_real_contention_from_owned_scope(self):
        import fcntl, os
        from publication_guard import remote_unlocked, RemoteWriterBusy, Unavailable
        _, worker, _, _ = self.selected()
        with self.writer.hold():
            with self.assertRaises(Unavailable) as error: remote_unlocked(worker)
            self.assertNotIsInstance(error.exception, RemoteWriterBusy)
        fd = os.open(self.writer.lock, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(RemoteWriterBusy): remote_unlocked(worker)
        finally: os.close(fd)

    def test_remote_probe_correction_refusal_is_not_transient(self):
        from publication_guard import remote_unlocked, RemoteWriterBusy, Unavailable
        _, worker, _, _ = self.selected()
        for name in ('negative-retirement-v1.pending','negative-retirement-v1.terminal-pending',
                     'archive-repair-v1.pending','archive-repair-v1.terminal-pending'):
            path = self.writer.root / name
            path.write_bytes(b'original recovery')
            try:
                with self.subTest(marker=name), self.assertRaises(Unavailable) as error: remote_unlocked(worker)
                self.assertNotIsInstance(error.exception, RemoteWriterBusy)
                self.assertEqual(path.read_bytes(), b'original recovery')
            finally: path.unlink()

    def test_initial_and_prepare_contention_share_one_budget(self):
        import fcntl, os
        from publication_guard import remote_unlocked, RemoteWriterBusy
        module, worker, maintenance, init = self.selected()
        fd = os.open(self.writer.lock, os.O_RDWR)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        clock = [100.0]
        def pause(seconds):
            clock[0] += seconds
            fcntl.flock(fd, fcntl.LOCK_UN)
        def prepare(*args):
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try: remote_unlocked(worker)
            finally: fcntl.flock(fd, fcntl.LOCK_UN)
        maintenance.prepare.side_effect = prepare
        with (patch('pack_only.time.monotonic', side_effect=lambda: clock[0]),
              patch('pack_only.time.sleep', side_effect=pause) as sleep, self.assertRaises(RemoteWriterBusy)):
            self.execute(module, worker, maintenance, init, admission_wait=1)
        maintenance.prepare.assert_called_once()
        self.assertEqual(sum(c.args[0] for c in sleep.call_args_list), 1)

    def test_typed_dispatch_failure_is_not_admission(self):
        from publication_guard import RemoteWriterBusy
        module, worker, maintenance, init = self.selected()
        with (patch('publication_guard.Authority.__init__', init), patch.object(module, 'Maintenance', return_value=maintenance),
              patch.object(module, 'Packs') as packs, patch('pack_only.time.sleep') as sleep,
              patch('import_recovery.dispatch_prepared', side_effect=RemoteWriterBusy('dispatch refusal')) as dispatch,
              self.assertRaises(RemoteWriterBusy)):
            module.run(worker, 'a' * 64, '1', admission_wait=30)
        maintenance.prepare.assert_called_once(); packs.return_value.cycle.assert_called_once()
        dispatch.assert_called_once(); sleep.assert_not_called(); self.assertFalse(self.writer.fenced())
