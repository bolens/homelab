"""Worker reports are durable, scoped, content-checked and safe for browser display."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from workflow_store import Store
import publication_guard
import publication_native


def load(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class RecordsTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.library=self.root/'library';self.library.mkdir()
        self.store=Store(self.root)
        self.workflow=SimpleNamespace(store=lambda:self.store,policy=lambda:{'pack_automation':True},emit=Mock())
        self.mylar=SimpleNamespace(workflow=self.workflow,CONFIG=SimpleNamespace(DESTINATION_DIR=str(self.library)),
                                  worker_handoff=SimpleNamespace(admit=Mock(return_value=None)))
        self.modules=patch.dict(sys.modules,{'mylar':self.mylar,'mylar.workflow_store':sys.modules['workflow_store']})
        self.modules.start();self.addCleanup(self.modules.stop)
        self.module=load('pack_intake')
        self.mylar.DATA_DIR=str(self.root)
        self.mylar.ordinary_import_history=SimpleNamespace(confirmed_token=lambda *_:True)
        self.mylar.publication_guard=publication_guard
        self.mylar.publication_native=SimpleNamespace(Review=publication_native.Review,owner=lambda root,issueid,comicid:{'table':'issues','issueid':issueid,'parentcomicid':comicid,'releasecomicid':comicid})
        self.key='a'*64
        self.store.set('pack',self.key,{'id':self.key,'ddl_id':'1','source':'/private/download','name':'Test pack','phase':'discovered','members':[],'inventory_complete':False})

    def test_review_sidecar_never_counts_as_completed_pack(self):
        payload={'id':self.key,'inventory_complete':True,'members':[
            {'id':'b'*64,'name':'notes.txt','kind':'sidecar','phase':'review','reason':'Retained for review'}]}
        self.module.report(json.dumps(payload))
        row=self.module.snapshot()[0]
        self.assertFalse(row['complete']);self.assertEqual(row['confirmed'],0)
        self.assertFalse(self.module.evidence(['1'])['1'][1])
        self.assertEqual(self.store.get('pack',self.key)['phase'],'review')

    def test_archive_present_without_ordinary_ack_cannot_confirm_pack(self):
        target=self.library/'Test.cbz';target.write_bytes(b'archive fixture')
        self.mylar.ordinary_import_history.confirmed_token=lambda *_:False
        with self.assertRaisesRegex(ValueError,'ordinary import acknowledgement'):
            self.module.report(self.report(target))
        self.assertEqual(self.store.get('pack',self.key)['phase'],'discovered')
        self.assertTrue(target.exists())

    def test_lost_or_changed_ack_retains_completed_pack_generation(self):
        target=self.library/'Test.cbz';target.write_bytes(b'archive fixture')
        self.module.report(self.report(target))
        self.assertTrue(self.module.evidence(['1'])['1'][1])
        self.mylar.ordinary_import_history.confirmed_token=lambda *_:False
        self.assertFalse(self.module.evidence(['1'])['1'][1])
        self.assertTrue(target.exists())

    def test_authoritative_evidence_outlives_bounded_activity_history(self):
        target=self.library/'Test.cbz';target.write_bytes(b'archive fixture')
        self.module.report(self.report(target))
        for n in range(205):
            record=dict(self.store.get('pack',self.key),id=str(n),ddl_id=str(n+2))
            self.store.set('pack',str(n),record)
        self.assertEqual(len(self.module.snapshot()),20)
        self.assertTrue(self.module.evidence(['1'])['1'][1])
        self.assertEqual(set(self.module.evidence(['1'])),{'1'})
        target.unlink()
        self.assertFalse(self.module.evidence(['1'])['1'][1])

    def test_capture_dotted_folder_uses_its_own_zip(self):
        import queue
        folder=self.root/'Pack.v2';folder.mkdir()
        (self.root/'Pack.v2.zip').write_bytes(b'right')
        (self.root/'Pack.zip').write_bytes(b'unrelated')
        db=Mock();db.selectone.return_value.fetchone.return_value={'pack':1}
        self.mylar.db=SimpleNamespace(DBConnection=lambda:db)
        processor=SimpleNamespace(ddl=True,download_info={'id':'22-1'},nzb_folder=str(folder),nzb_name='Pack.v2',queue=queue.Queue())
        self.assertTrue(self.module.capture(processor))
        record=next(r for r in self.store.all('pack',100) if r['ddl_id']=='22-1')
        self.assertEqual(record['source'],str(self.root/'Pack.v2.zip'))

    def test_fallback_discovers_distinct_sources_for_the_same_ddl_id(self):
        self.mylar.CONFIG.DDL_LOCATION=str(self.root)
        old=self.root/'Original.__1127288__.zip';old.write_bytes(b'old content')
        new=self.root/'Original.recovered-2.__1115810__.zip';new.write_bytes(b'new content')
        old_key=hashlib.sha256(('378582\0'+str(old)).encode()).hexdigest()
        old_record={'id':old_key,'ddl_id':'378582','source':str(old),'name':'Old pack',
                    'phase':'confirmed','ordinary_import_token':'f'*64,'members':[],'inventory_complete':True,'cleanup_complete':True}
        self.store.set('pack',old_key,old_record)
        db=Mock();db.select.return_value=[{'id':'378582','pack':1,'filename':new.name,'series':'New pack'}]
        self.mylar.db=SimpleNamespace(DBConnection=lambda:db)
        new_key=hashlib.sha256(('378582\0'+str(new)).encode()).hexdigest()
        self.module.work()
        self.assertEqual(self.store.get('pack',new_key)['source'],str(new))
        self.assertEqual(self.store.get('pack',old_key),old_record)
        initial=self.store.get('pack',new_key)
        self.module.work()
        self.assertEqual(self.store.get('pack',new_key),initial)
        self.assertEqual(len([r for r in self.store.all('pack') if r['ddl_id']=='378582']),2)

    def test_evidence_requires_every_capture_regardless_of_update_order(self):
        raw=b'pack credit'
        complete={'id':self.key,'ddl_id':'1','source':'/private/old','name':'Old',
                  'phase':'confirmed','ordinary_import_token':'f'*64,'inventory_complete':True,'members':[
                      {'id':'b'*64,'name':'credit.txt','kind':'sidecar','phase':'preserved',
                       'sidecar':base64.b64encode(raw).decode(),'sha256':hashlib.sha256(raw).hexdigest()}]}
        incomplete=dict(complete,id='c'*64,source='/private/new',phase='review',
                        inventory_complete=False,members=[{'id':'d'*64,'kind':'review','phase':'review','name':'New'}])
        for first,second in ((complete,incomplete),(incomplete,complete)):
            self.store.set('pack',first['id'],first);self.store.set('pack',second['id'],second)
            self.assertEqual(self.module.evidence(['1']),{'1':('Pack member review (1/2 members)',False)})
        # An empty new capture also prevents a blanket completion claim.
        incomplete['members']=[];self.store.set('pack',incomplete['id'],incomplete)
        self.assertEqual(self.module.evidence(['1']),{'1':('Pack member review (1/1 members)',False)})
        complete['id']=incomplete['id'];self.store.set('pack',complete['id'],complete)
        self.assertEqual(self.module.evidence(['1']),{'1':('Pack in library (2/2 members)',True)})

    def test_reused_path_creates_a_generation_without_overwriting_history(self):
        source=self.root/'pack.zip';source.write_bytes(b'first delivery')
        first=self.module.discover('22',source,'Pack')
        self.assertEqual(self.module.discover('22',source,'Pack'),first)
        source.write_bytes(b'replacement delivery')
        second=self.module.discover('22',source,'Pack')
        self.assertNotEqual(first['id'],second['id'])
        self.assertNotEqual(first['source_generation'],second['source_generation'])
        self.assertEqual(self.store.get('pack',first['id']),first)
        self.assertEqual(self.module.discover('22',source,'Pack'),second)

    def test_companion_changes_and_legacy_sources_do_not_reuse_old_proof(self):
        source=self.root/'pack.zip';source.write_bytes(b'archive')
        first=self.module.discover('22',source,'Pack')
        companion=source.with_suffix('');companion.mkdir()
        (companion/'extra.txt').write_bytes(b'new member')
        second=self.module.discover('22',source,'Pack')
        self.assertNotEqual(first['source_generation'],second['source_generation'])
        self.assertEqual(self.store.get('pack',first['id']),first)
        # Legacy path ownership is retained, never silently promoted to proof
        # of whatever bytes happen to occupy that path after an upgrade.
        legacy=dict(second);legacy.pop('source_stamp');legacy.pop('source_generation')
        self.store.set('pack',legacy['id'],legacy)
        third=self.module.discover('22',source,'Pack')
        self.assertNotEqual(third['id'],legacy['id'])
        self.assertEqual(self.store.get('pack',legacy['id']),legacy)

    def test_partial_cleanup_does_not_create_a_phantom_generation(self):
        source=self.root/'pack';source.mkdir()
        member=source/'one.cbz';member.write_bytes(b'one')
        (source/'two.cbz').write_bytes(b'two')
        original=self.module.discover('22',source,'Pack')
        original['cleanup_started']=True;self.store.set('pack',original['id'],original)
        member.unlink()
        self.assertEqual(self.module.discover('22',source,'Pack'),original)
        self.assertEqual(len([r for r in self.store.all('pack') if r['ddl_id']=='22']),1)

    def test_generation_rejects_linked_sources_and_unstable_capture(self):
        source=self.root/'pack';source.mkdir()
        (source/'linked').symlink_to(self.library)
        with self.assertRaises(ValueError):self.module.discover('22',source,'Pack')
        (source/'linked').unlink()
        with patch.object(self.module,'source_state',side_effect=['before','digest','after']):
            with self.assertRaisesRegex(ValueError,'changed during capture'):
                self.module.discover('22',source,'Pack')
        self.assertFalse(any(r['ddl_id']=='22' for r in self.store.all('pack')))

    def test_empty_retained_directory_is_not_a_new_delivery(self):
        source=self.root/'pack';source.mkdir()
        with self.assertRaisesRegex(ValueError,'no files'):self.module.discover('22',source,'Pack')
        self.assertFalse(any(r['ddl_id']=='22' for r in self.store.all('pack')))

    def test_fallback_and_native_capture_choose_the_same_dotted_source(self):
        source=self.root/'Pack.v2';source.mkdir()
        archive=source.with_name(source.name+'.zip');archive.write_bytes(b'pack')
        first=self.module.discover('22',archive,'Pack')
        self.mylar.CONFIG.DDL_LOCATION=str(self.root)
        db=Mock();db.select.return_value=[{'id':'22','pack':1,'filename':source.name,'series':'Pack'}]
        self.mylar.db=SimpleNamespace(DBConnection=lambda:db)
        self.module.work()
        self.assertEqual([r for r in self.store.all('pack') if r['ddl_id']=='22'],[first])

    def test_generation_manifest_matches_shared_portable_vector(self):
        # Worker tests assert this same literal without importing this stack.
        expected='aa2a03cd127c3fbf56c9a89092535ff441a31c94ce628135619bc74f9c4e2fcd'
        source=self.root/'pack.zip';source.write_bytes(b'archive')
        companion=source.with_suffix('');companion.mkdir();(companion/'extra.txt').write_bytes(b'credit')
        self.assertEqual(self.module.source_state(source,content=True),expected)

    def report(self,destination):
        member={'id':'b'*64,'name':'Test.cbz','kind':'issue','phase':'confirmed','ordinary_import_token':'f'*64,
                'destination':str(destination),'destination_sha256':hashlib.sha256(destination.read_bytes()).hexdigest()}
        return json.dumps({'id':self.key,'inventory_complete':True,'members':[member]})

    def test_reports_verify_content_and_changed_files_invalidate_completion(self):
        target=self.library/'Test.cbz';target.write_bytes(b'archive fixture')
        self.module.report(self.report(target))
        self.assertTrue(self.module.snapshot()[0]['complete'])
        text=json.dumps(self.module.snapshot())
        self.assertNotIn(str(self.root),text);self.assertNotIn('destination_sha256',text)
        target.write_bytes(b'replaced')
        self.assertFalse(self.module.snapshot()[0]['complete'])
        self.assertIn('review',self.module.evidence()['1'][0])

    def test_delayed_reports_cannot_erase_members_or_cleanup_or_verified_destinations(self):
        target=self.library/'Test.cbz';target.write_bytes(b'archive fixture')
        payload=json.loads(self.report(target));payload['cleaned_at']=1
        self.module.report(json.dumps(payload));before=self.store.get('pack',self.key)
        for change in ({'members':[]},{'members':[dict(payload['members'][0],phase='ready')]},
                       {'members':[dict(payload['members'][0],phase='preserved')]},
                       {'members':[dict(payload['members'][0],issueid='999')]},
                       {'members':[dict(payload['members'][0],kind='supplement')]},
                       {'members':[dict(payload['members'][0],destination_sha256='0'*64)]}):
            with self.assertRaises(ValueError):self.module.report(json.dumps(dict(payload,**change)))
            self.assertEqual(self.store.get('pack',self.key),before)
        payload.pop('cleaned_at');payload['inventory_complete']=False
        self.module.report(json.dumps(payload))
        self.assertEqual(self.store.get('pack',self.key)['phase'],'confirmed')
        self.assertTrue(self.store.get('pack',self.key)['cleanup_complete'])

    def test_report_cannot_overwrite_a_concurrent_pack_transition(self):
        target=self.library/'Test.cbz';target.write_bytes(b'archive fixture')
        self.module.report(self.report(target))
        previous=self.store.get('pack',self.key)
        replace=self.store.replace
        def racing_replace(kind,key,expected,value,**options):
            current=dict(previous,transition='new verified binding')
            self.store.set(kind,key,current)
            return replace(kind,key,expected,value,**options)
        with patch.object(self.store,'replace',side_effect=racing_replace):
            with self.assertRaises(ValueError):self.module.report(self.report(target))
        self.assertEqual(self.store.get('pack',self.key)['transition'],'new verified binding')

    def test_delayed_report_rechecks_file_inside_atomic_commit(self):
        target=self.library/'Test.cbz';target.write_bytes(b'archive fixture')
        replace=self.store.replace
        previous=self.store.get('pack',self.key)
        def delayed_replace(*args,**options):
            target.write_bytes(b'foreign replacement after validation')
            return replace(*args,**options)
        with patch.object(self.store,'replace',side_effect=delayed_replace):
            with self.assertRaises(ValueError):self.module.report(self.report(target))
        self.assertEqual(self.store.get('pack',self.key),previous)

    def test_private_sidecar_is_verified_but_never_exposed_to_browser(self):
        data=b'original pack credit'
        member={'id':'c'*64,'name':'credits.txt','kind':'sidecar','phase':'preserved',
                'sidecar':base64.b64encode(data).decode(),'sha256':hashlib.sha256(data).hexdigest()}
        payload={'id':self.key,'inventory_complete':True,'members':[member]}
        self.module.report(json.dumps(payload))
        self.assertTrue(self.module.snapshot()[0]['complete'])
        self.assertNotIn(member['sidecar'],json.dumps(self.module.snapshot()))
        member['sha256']='0'*64
        with self.assertRaises(ValueError):self.module.report(json.dumps(payload))

    def test_outside_symlink_or_wrong_digest_never_confirms(self):
        target=self.root/'outside.cbz';target.write_bytes(b'archive')
        with self.assertRaises(ValueError):self.module.report(self.report(target))
        linked=self.library/'linked.cbz';linked.symlink_to(target)
        with self.assertRaises(ValueError):self.module.report(self.report(linked))
        target=self.library/'ok.cbz';target.write_bytes(b'archive')
        payload=json.loads(self.report(target));payload['members'][0]['destination_sha256']='0'*64
        with self.assertRaises(ValueError):self.module.report(json.dumps(payload))
        self.assertFalse(self.module.snapshot()[0]['complete'])

    def test_pending_work_is_not_hidden_by_completed_history_and_rotates(self):
        self.mylar.CONFIG.DDL_LOCATION=str(self.root)
        self.mylar.db=SimpleNamespace(DBConnection=lambda:SimpleNamespace(select=lambda q:[]))
        for n in range(201):
            self.store.set('pack',str(n),{'id':str(n),'ddl_id':str(n),'source':'/private/d'+str(n),
                'name':'old','phase':'confirmed','ordinary_import_token':'f'*64,'cleanup_complete':True,'inventory_complete':True,'members':[]})
        self.assertIn(self.key,[r['id'] for r in self.module.work()['packs']])
        for n in range(101):
            self.store.set('pack','pending'+str(n),{'id':'pending'+str(n),'ddl_id':str(n),'source':'/private/p'+str(n),
                'name':'new','phase':'discovered','members':[],'inventory_complete':False})
        seen=set()
        for _ in range(3):
            work=self.module.work();seen.update(r['id'] for r in work['packs'])
            self.assertEqual(len(work['protected']),102)
        self.assertEqual(len(seen),102)
        self.assertEqual(len([r for r in self.module.snapshot() if r['id'].startswith('pending')]),101)

    def test_cleaned_pack_with_stale_identity_returns_for_content_verification(self):
        self.mylar.CONFIG.DDL_LOCATION=str(self.root)
        self.mylar.db=SimpleNamespace(DBConnection=lambda:SimpleNamespace(select=lambda q:[]))
        target=self.library/'Test.cbz';target.write_bytes(b'archive fixture')
        payload=json.loads(self.report(target));payload['cleaned_at']=1
        self.module.report(json.dumps(payload))
        self.assertNotIn(self.key,[r['id'] for r in self.module.work()['packs']])
        record=self.store.get('pack',self.key)
        record['members'][0]['signature'][0]-=1  # Mount device changed.
        self.store.set('pack',self.key,record)
        self.assertFalse(self.module.evidence()['1'][1])
        self.assertIn(self.key,[r['id'] for r in self.module.work()['packs']])
        self.assertFalse(self.module.evidence()['1'][1])  # Admission is not proof.
        self.module.report(json.dumps(payload))  # Full destination hash verified.
        self.assertTrue(self.module.evidence()['1'][1])
        self.assertNotIn(self.key,[r['id'] for r in self.module.work()['packs']])
        target.write_bytes(b'changed archive')
        self.assertIn(self.key,[r['id'] for r in self.module.work()['packs']])
        with self.assertRaisesRegex(ValueError,'Library destination changed'):
            self.module.report(json.dumps(payload))
        self.assertFalse(self.module.evidence()['1'][1])


if __name__=='__main__':unittest.main()
