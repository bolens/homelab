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

if __name__=='__main__':unittest.main()
