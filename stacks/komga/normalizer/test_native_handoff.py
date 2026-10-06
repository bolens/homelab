"""Fresh maintenance ownership, uncertain HTTP and native cleanup ordering."""
from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from native_handoff import request,dispatch,guard
from publication_guard import scope,Unavailable
from test_publication_guard import AuthorityFixture


class HandoffTest(AuthorityFixture,unittest.TestCase):
    def setUp(self):
        AuthorityFixture.setUp(self)
        state=self.root/'worker';state.mkdir();jobs=state/'jobs';jobs.mkdir()
        maintenance=state/'maintenance';maintenance.mkdir()
        cache=self.root/'cache';cache.mkdir()
        worker=SimpleNamespace(state=state,jobs=jobs,roots=[self.library],
            config={'writer_state':str(self.writer.root),'mylar':{'config_dir':str(self.config)},
                    'publication_roots':[{'native':str(self.native_root),'worker':str(self.library)}]})
        self.m=SimpleNamespace(worker=worker,state=maintenance,roots=[self.library,cache],
            settings={'ddl_cache':str(cache),'mylar_ddl_cache':'/native-cache'},mylar=Mock())
        self.source=self.archive('unregistered.cbz',[('01.jpg',b'new')])
        self.arguments={'evidence':json.dumps({'series':'Test','number':'1','year':'2024'}),'catalog_attempt':'1'}
        actual=scope
        @contextmanager
        def portable(*args,**kwargs):
            with actual(*args,**kwargs) as authority:
                authority.tool_root=self.tool
                yield authority
        self.portable=portable

    def prepare(self):
        with self.writer.hold(),self.portable(self.m.worker,self.writer):
            self.assertIsNone(request(self.m,'packCatalog',self.arguments,[guard(self.source)]))
        self.m.mylar.assert_not_called()
        return next((self.m.state/'native-handoffs').glob('*.json'))

    def execute(self):
        with patch('native_handoff.scope',self.portable):return dispatch(self.m)

    def api(self,command,**kwargs):
        self.assertFalse(getattr(self.writer.local[1],'depth',0))
        if command=='getHealth':return {'workflow':{'valid':True,'maintenance_handoff':1}}
        self.assertFalse(self.writer.fenced())
        self.assertEqual(command,'packCatalog')
        path=next((self.m.state/'native-handoffs').glob('*.json'))
        self.assertEqual(json.loads(path.read_text())['phase'],'dispatching')
        packet=json.loads(kwargs['maintenance_handoff'])
        self.assertEqual(packet['sources'][0]['path'],str(self.native_root/self.source.name))
        return {'phase':'ready','issueid':'999','comicid':'888'}

    def test_prepare_dispatch_and_fresh_result_consumption_happen_in_separate_lock_phases(self):
        path=self.prepare();self.m.mylar.side_effect=self.api
        self.assertEqual(self.execute(),1);self.assertEqual(self.execute(),0)
        self.assertEqual(json.loads(path.read_text())['phase'],'complete')
        with self.writer.hold(),self.portable(self.m.worker,self.writer):
            self.assertEqual(request(self.m,'packCatalog',self.arguments,[guard(self.source)])['phase'],'ready')

    def test_lost_response_is_retained_and_not_replayed_after_source_or_census_change(self):
        path=self.prepare()
        def timeout(command,**kwargs):
            result=self.api(command,**kwargs)
            if command!='getHealth':raise TimeoutError('unknown native outcome')
            return result
        self.m.mylar.side_effect=timeout
        self.assertEqual(self.execute(),0);self.assertEqual(self.execute(),0)
        self.assertEqual(json.loads(path.read_text())['phase'],'dispatching')
        self.source.write_bytes(self.archive('changed.cbz',[('01.jpg',b'changed')]).read_bytes())
        with self.writer.hold(),self.portable(self.m.worker,self.writer),self.assertRaises(Unavailable):
            request(self.m,'packCatalog',self.arguments,[guard(self.source)])
        self.assertEqual(sum(call.args[0]=='packCatalog' for call in self.m.mylar.call_args_list),1)

    def test_pending_fence_old_protocol_and_changed_source_preserve_prepared_receipt(self):
        path=self.prepare();before=path.read_bytes()
        self.m.mylar.return_value={'workflow':{'valid':True,'maintenance_handoff':True}}
        self.assertEqual(self.execute(),0);self.assertEqual(path.read_bytes(),before)
        self.m.mylar.side_effect=self.api
        with self.writer.hold(allow_pending=True):self.writer.mark_pending()
        self.assertEqual(self.execute(),0);self.assertEqual(path.read_bytes(),before)
        with self.writer.hold(allow_pending=True):self.writer.clear_pending()
        self.source.write_bytes(b'changed')
        self.assertEqual(self.execute(),0);self.assertEqual(path.read_bytes(),before)

    def test_report_binds_private_extraction_and_shared_catalog_without_exposing_private_path(self):
        from native_handoff import report,packet
        import shutil
        self.m.roots=[Path(self.m.settings['ddl_cache'])]
        extracted=self.m.state/'packs'/('b'*64)/'extracted'
        extracted.mkdir(parents=True)
        source=extracted/'member.cbz';shutil.copyfile(self.candidate,source)
        target=self.library/'correct.cbz'
        value={'id':'b'*64,'members':[{'id':'c'*64,'kind':'issue','phase':'confirmed',
            'source':str(source),'destination':str(target),'destination_sha256':__import__('normalize').digest(target),
            'issueid':'123','comicid':'456'}]}
        with self.writer.hold(),self.portable(self.m.worker,self.writer):
            self.assertIsNone(report(self.m,value))
            path=next((self.m.state/'native-handoffs').glob('*.json'))
            record=json.loads(path.read_text());bound=packet(self.m,record,path.stem)
        self.assertEqual(len(record['guards']),1)
        self.assertEqual(bound['sources'][0]['path'],str(self.native_root/target.name))
        self.assertTrue(bound['sources'][0]['confirmation'])
        self.assertNotIn(str(extracted),json.dumps(bound))
        self.m.mylar.assert_not_called()

    def test_pack_destination_translates_native_catalog_path_through_owned_mapping(self):
        from pack_recovery import Packs
        fake=SimpleNamespace(worker=self.m.worker,db=self.catalog)
        with self.writer.hold(),self.portable(self.m.worker,self.writer):
            self.assertEqual(Packs.destination(fake,{'issueid':'123','comicid':'456'}),self.library/'correct.cbz')

    def test_extras_registered_source_is_held_before_destination_or_metadata_changes(self):
        from pack_recovery import Packs
        fake=SimpleNamespace(worker=self.m.worker,m=self.m,parent=Mock())
        before={path.name:path.read_bytes() for path in self.library.iterdir()}
        with self.writer.hold(),self.portable(self.m.worker,self.writer),self.assertRaises(Unavailable):
            Packs.preserve_extra(fake,self.candidate,{}, {},{})
        fake.parent.assert_not_called()
        self.assertEqual(before,{path.name:path.read_bytes() for path in self.library.iterdir()})

    def test_packet_uses_prepared_source_bytes_even_if_path_changes_after_local_check(self):
        from native_handoff import packet
        path=self.prepare();record=json.loads(path.read_text())
        checksum=record['proof']['guards'][0]['sha256']
        self.source.write_bytes(b'changed after observation')
        with self.writer.hold(),self.portable(self.m.worker,self.writer):
            self.assertEqual(packet(self.m,record,path.stem)['sources'][0]['sha256'],checksum)
        self.m.mylar.assert_not_called()

    def test_registered_payload_without_exact_owner_never_prepares_or_calls_native(self):
        with self.writer.hold(),self.portable(self.m.worker,self.writer),self.assertRaises(Unavailable):
            request(self.m,'packCatalog',self.arguments,[guard(self.candidate)])
        self.assertFalse((self.m.state/'native-handoffs').exists());self.m.mylar.assert_not_called()

    def test_relative_and_parent_traversal_sources_cannot_prepare_protocol_state(self):
        for source in (Path('relative.cbz'),self.library/'..'/'library'/self.source.name):
            with self.writer.hold(),self.portable(self.m.worker,self.writer),self.subTest(source=str(source)),self.assertRaises(Unavailable):
                request(self.m,'packCatalog',self.arguments,[guard(source)])
        self.assertFalse((self.m.state/'native-handoffs').exists());self.m.mylar.assert_not_called()

    def test_wrong_worker_or_outside_scope_cannot_prepare_a_request(self):
        with self.assertRaises(Unavailable):request(self.m,'packCatalog',self.arguments,[guard(self.source)])
        self.assertFalse((self.m.state/'native-handoffs').exists())


if __name__=='__main__':unittest.main()
