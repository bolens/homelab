"""Worker reports are durable, scoped, content-checked and safe for browser display."""
import base64
import hashlib
import importlib.util
import json
import queue
import sqlite3
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
        self.mylar.db=SimpleNamespace(DBConnection=lambda:SimpleNamespace(select=lambda q,args=():[]))
        for n in range(201):
            self.store.set('pack',str(n),{'id':str(n),'ddl_id':str(n),'source':'/private/d'+str(n),
                'name':'old','phase':'confirmed','ordinary_import_token':'f'*64,'cleanup_complete':True,'inventory_complete':True,'members':[]})
        source=self.root/'existing.zip';source.write_bytes(b'existing')
        existing=self.store.get('pack',self.key)
        existing.update(source=str(source),source_stamp=self.module.source_state(source),source_generation=self.module.source_state(source,content=True))
        self.store.set('pack',self.key,existing)
        self.assertIn(self.key,[r['id'] for r in self.module.work()['packs']])
        for n in range(101):
            source=self.root/('pending'+str(n));source.write_bytes(b'pending')
            self.store.set('pack','pending'+str(n),{'id':'pending'+str(n),'ddl_id':str(n),'source':str(source),
                'source_stamp':self.module.source_state(source),'source_generation':self.module.source_state(source,content=True),
                'name':'new','phase':'discovered','members':[],'inventory_complete':False})
        seen=set()
        for _ in range(13):
            work=self.module.work();self.assertLessEqual(len(work['packs']),8);seen.update(r['id'] for r in work['packs'])
            self.assertEqual(len(work['protected']),103)  #102 roots plus ZIP companion
        self.assertEqual(len(seen),102)
        self.assertEqual(len([r for r in self.module.snapshot() if r['id'].startswith('pending')]),101)

    def test_cleaned_pack_with_stale_identity_returns_for_content_verification(self):
        self.mylar.CONFIG.DDL_LOCATION=str(self.root)
        self.mylar.db=SimpleNamespace(DBConnection=lambda:SimpleNamespace(select=lambda q,args=():[]))
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




class PassiveDiscoveryTest(unittest.TestCase):
    setUp = RecordsTest.setUp

    def prepare(self, count=1):
        self.store.delete('pack', self.key)
        self.mylar.CONFIG.DDL_LOCATION = str(self.root)
        connection = sqlite3.connect(':memory:')
        connection.row_factory = sqlite3.Row
        connection.execute('CREATE TABLE ddl_info (id TEXT,pack INTEGER,filename TEXT,series TEXT,status TEXT,updated_date INTEGER)')
        self.addCleanup(connection.close)
        self.mylar.db = SimpleNamespace(DBConnection=lambda:SimpleNamespace(
            select=lambda sql,args=():connection.execute(sql,args).fetchall(),
            selectone=lambda sql,args=():connection.execute(sql,args)))
        records = []
        for index in range(count):
            source = self.root / ('pack%03d.zip' % index)
            source.write_bytes(('public fixture%d' % index).encode())
            ddl = str(index+22)
            connection.execute('INSERT INTO ddl_info VALUES (?,?,?,?,?,?)',
                               (ddl,1,source.name,'Fixture','Completed',1000-index))
            records.append(self.module.discover(ddl, source, 'Fixture'))
        connection.commit()
        return connection, records

    def changed_device(self, sources):
        real = Path.stat
        targets = set(map(Path,sources))
        class Device:
            def __init__(self, value): self.value = value
            def __getattr__(self, name):
                return self.value.st_dev+17 if name=='st_dev' else getattr(self.value,name)
        return patch.object(Path,'stat',lambda path,*a,**kw:Device(real(path,*a,**kw)) if path in targets else real(path,*a,**kw))

    def test_device_change_never_hashes_or_returns_known_capture(self):
        _, records = self.prepare()
        old = records[0]
        old['members']=[{'id':'b'*64,'kind':'issue','phase':'review','ordinary_import_token':'c'*64}]
        self.store.set('pack',old['id'],old)
        before = self.store.get('pack',old['id'])
        with self.changed_device([old['source']]), patch.object(Path,'open',side_effect=AssertionError('no payload open')):
            for _ in range(3):
                result = self.module.work()
                self.assertEqual(result['packs'],[])
                self.assertEqual(result['discovery_review'],[old['id']])
                self.assertIn(old['source'],result['protected'])
                self.assertIn(str(Path(old['source']).with_suffix('')),result['protected'])
        self.assertEqual(self.store.get('pack',old['id']),before)
        self.assertEqual(len([r for r in self.store.all('pack') if r['ddl_id']=='22']),1)
        observations=self.store.all('pack_observation')
        self.assertEqual(len(observations),1)
        self.assertEqual(observations[0]['phase'],'review')

    def test_payload_change_held_passively_but_actual_delivery_gets_new_capture(self):
        _, records = self.prepare()
        old = records[0]
        old['members']=[{'id':'b'*64,'kind':'issue','phase':'review','ordinary_import_token':'c'*64}]
        self.store.set('pack',old['id'],old)
        source=Path(old['source']);source.write_bytes(b'new actual delivery')
        with patch.object(Path,'open',side_effect=AssertionError('no passive payload read')):
            self.assertEqual(self.module.work()['packs'],[])
        processor=SimpleNamespace(ddl=True,download_info={'id':'22'},nzb_folder=str(source),nzb_name='Fixture',queue=queue.Queue())
        self.assertTrue(self.module.capture(processor))
        records=[r for r in self.store.all('pack') if r['ddl_id']=='22']
        self.assertEqual(len(records),2)
        new=next(r for r in records if r['id']!=old['id'])
        self.assertNotEqual(new['source_generation'],old['source_generation'])
        self.assertEqual(new['members'],[])
        self.assertEqual(self.store.get('pack',old['id']),old)
        self.assertEqual(processor.queue.get_nowait(),[{'mode':'stop'}])

    def test_partial_cleanup_keeps_original_capture_actionable(self):
        _, records=self.prepare()
        old=records[0];source=Path(old['source'])
        companion=source.with_suffix('');companion.mkdir();(companion/'one.cbz').write_bytes(b'fixture')
        old=self.module.discover('22',source,'Fixture')
        old['cleanup_started']=True;self.store.set('pack',old['id'],old)
        source.unlink()
        with patch.object(Path,'open',side_effect=AssertionError('cleanup must not hash')):
            # Current fallback points at companion; old source mapping would be
            # different, so exact maintenance remains the owning cleanup seam.
            selected=self.module.work(old['id'],'22')
        self.assertEqual(selected['packs'],[old])
        with patch.object(Path,'open',side_effect=AssertionError('partial cleanup must not rediscover companion')):
            self.assertEqual(self.module.work()['packs'],[old])
        self.assertEqual(len([r for r in self.store.all('pack') if r['ddl_id']=='22']),2)
        self.assertEqual(self.module.discover('22',source,'Fixture',passive=True),old)

    def test_selected_exact_work_bypasses_global_discovery(self):
        _, records=self.prepare();old=records[0]
        with patch.object(self.module,'discover',side_effect=AssertionError('no discover')),patch.object(Path,'stat',side_effect=AssertionError('no source traversal')):
            self.assertEqual(self.module.work(old['id'],'22')['packs'],[old])

    def test_cursor_limits_work_and_covers_known_sources_without_payload_reads(self):
        _, records=self.prepare(19)
        seen=set();sizes=[]
        with patch.object(Path,'open',side_effect=AssertionError('known source metadata only')):
            for _ in range(3):
                result=self.module.work();sizes.append(len(result['packs']));seen.update(r['id'] for r in result['packs'])
        self.assertTrue(all(size<=16 for size in sizes));self.assertEqual(seen,{r['id'] for r in records})
        self.assertEqual(self.store.get('meta','pack_discovery_cursor'),0)
        self.assertLessEqual(len(self.module.work()['packs']),16)

    def test_one_new_cold_admission_per_poll_then_review_protection(self):
        connection,_=self.prepare(0)
        for index in range(3):
            source=self.root/('new%d.zip'%index);source.write_bytes(b'new public fixture')
            connection.execute('INSERT INTO ddl_info VALUES (?,?,?,?,?,?)',(str(40+index),1,source.name,'New','Completed',90-index))
        connection.commit()
        reads=[];real=Path.open
        def opened(path,*a,**kw):
            if a and a[0]=='rb' and path.suffix=='.zip':reads.append(path.name)
            return real(path,*a,**kw)
        with patch.object(Path,'open',opened): result=self.module.work()
        self.assertEqual(reads,['new0.zip'])
        self.assertEqual(len(result['packs']),1)
        self.assertEqual(len([r for r in self.store.all('pack') if r['ddl_id'] in ('40','41','42')]),1)
        self.assertTrue(all(str(self.root/('new%d.zip'%i)) in result['protected'] for i in range(3)))

    def test_oversize_review_protection_survives_cursor_rotation(self):
        connection,records=self.prepare(9)
        source=self.root/'huge.zip'
        with source.open('wb') as stream:stream.truncate(256*1024**2+1)
        connection.execute('INSERT INTO ddl_info VALUES (?,?,?,?,?,?)',('99',1,source.name,'Huge','Completed',99999));connection.commit()
        with patch.object(Path,'open',side_effect=AssertionError('known or oversized never hash')):
            first=self.module.work();second=self.module.work()
        self.assertIn(str(source),first['protected']);self.assertIn(str(source),second['protected'])
        self.assertIn(str(source.with_suffix('')),second['protected'])

    def test_same_bytes_new_inode_trusted_delivery_has_no_old_ack(self):
        _,records=self.prepare();old=records[0]
        old['members']=[{'id':'b'*64,'kind':'issue','phase':'review','ordinary_import_token':'c'*64}]
        self.store.set('pack',old['id'],old)
        source=Path(old['source']);replacement=self.root/'replacement'
        replacement.write_bytes(source.read_bytes());replacement.replace(source)
        self.assertEqual(self.module.work()['packs'],[])
        processor=SimpleNamespace(ddl=True,download_info={'id':'22'},nzb_folder=str(source),nzb_name='Fixture',queue=queue.Queue())
        self.assertTrue(self.module.capture(processor))
        new=next(r for r in self.store.all('pack') if r['ddl_id']=='22' and r['id']!=old['id'])
        self.assertEqual(new['source_generation'],old['source_generation'])
        self.assertEqual(new['members'],[])
        self.assertEqual(self.store.get('pack',old['id']),old)

    def test_review_under_real_writer_is_stable_and_keeps_originals(self):
        from media_writer import Writer
        _,records=self.prepare();old=records[0]
        writer=Writer(self.root/'writer',create=True)
        source=Path(old['source']);source.write_bytes(b'changed bytes')
        with writer.hold(),patch.object(Path,'open',side_effect=AssertionError('no hash')):
            self.assertEqual(self.module.work()['packs'],[])
            first=self.store.get('pack_observation',hashlib.sha256(('22'+'\0'+str(source)).encode()).hexdigest())
            self.assertEqual(self.module.work()['packs'],[])
        self.assertEqual(self.store.get('pack',old['id']),old)
        self.assertEqual(first,self.store.all('pack_observation')[0])
        self.assertEqual(source.read_bytes(),b'changed bytes')

    def test_cursor_restarts_and_eventually_sees_new_arrival(self):
        connection,records=self.prepare(9)
        self.module.work()
        source=self.root/'arrival.zip';source.write_bytes(b'newly delivered')
        connection.execute('INSERT INTO ddl_info VALUES (?,?,?,?,?,?)',('99',1,source.name,'New','Completed',99999));connection.commit()
        seen=set()
        for _ in range(4):seen.update(r['ddl_id'] for r in self.module.work()['packs'])
        self.assertIn('99',seen)
        self.assertTrue({r['ddl_id'] for r in records}.issubset(seen))

    def test_growing_cold_source_refuses_with_actual_reads_bounded(self):
        source=self.root/'growing.zip';source.write_bytes(b'1234')
        real_open=Path.open;reads=[];requests=[]
        class Counted:
            def __init__(self,stream):self.stream=stream
            def __enter__(self):return self
            def __exit__(self,*args):return self.stream.__exit__(*args)
            def read(self,size):
                requests.append(size)
                data=self.stream.read(size);reads.append(len(data));return data
        def opened(path,*args,**kwargs):
            if path==source and args and args[0]=='rb':
                with real_open(source,'ab') as stream:stream.write(b'abcdefghijkl')
                return Counted(real_open(path,*args,**kwargs))
            return real_open(path,*args,**kwargs)
        with patch.object(Path,'open',opened),self.assertRaisesRegex(ValueError,'Pack source changed'):
            self.module.source_state(source,content=True,max_bytes=8)
        self.assertEqual(sum(reads),4)
        self.assertTrue(all(0<size<=8 for size in requests))
        self.assertLessEqual(sum(reads),8)
        self.assertEqual(source.read_bytes(),b'1234abcdefghijkl')
        self.assertFalse(any(r['ddl_id']=='22' for r in self.store.all('pack')))

    def test_shrinking_cold_source_refuses_on_early_eof(self):
        source=self.root/'shrinking.zip';source.write_bytes(b'12345678')
        real_open=Path.open;reads=[]
        class Counted:
            def __init__(self,stream):self.stream=stream
            def __enter__(self):return self
            def __exit__(self,*args):return self.stream.__exit__(*args)
            def read(self,size):
                data=self.stream.read(size);reads.append(len(data));return data
        def opened(path,*args,**kwargs):
            if path==source and args and args[0]=='rb':
                with real_open(source,'r+b') as stream:stream.truncate(4)
                return Counted(real_open(path,*args,**kwargs))
            return real_open(path,*args,**kwargs)
        with patch.object(Path,'open',opened),self.assertRaisesRegex(ValueError,'Pack source changed'):
            self.module.source_state(source,content=True,max_bytes=8)
        self.assertEqual(reads,[4,0]);self.assertLessEqual(sum(reads),8)

    def test_actual_read_allowance_is_shared_across_all_source_files(self):
        source=self.root/'aggregate';source.mkdir()
        (source/'a.cbz').write_bytes(b'1234');(source/'b.cbz').write_bytes(b'5678')
        real_open=Path.open;reads=[]
        class Counted:
            def __init__(self,stream):self.stream=stream
            def __enter__(self):return self
            def __exit__(self,*args):return self.stream.__exit__(*args)
            def read(self,size):
                data=self.stream.read(size);reads.append(len(data));return data
        def opened(path,*args,**kwargs):
            stream=real_open(path,*args,**kwargs)
            return Counted(stream) if path.parent==source and args and args[0]=='rb' else stream
        with patch.object(Path,'open',opened),self.assertRaisesRegex(ValueError,'exceeds limits'):
            self.module.source_state(source,content=True,max_bytes=7)
        self.assertEqual(reads,[4]);self.assertLessEqual(sum(reads),7)
        reads.clear()
        with patch.object(Path,'open',opened):
            generation=self.module.source_state(source,content=True,max_bytes=8)
        self.assertEqual(reads,[4,4]);self.assertEqual(sum(reads),8)
        self.assertEqual(generation,self.module.source_state(source,content=True))

    def test_failed_cold_hash_consumes_allowance_before_next_candidate(self):
        connection,_=self.prepare(0)
        for index in range(3):
            source=self.root/('unstable%d.zip'%index);source.write_bytes(b'fixture')
            connection.execute('INSERT INTO ddl_info VALUES (?,?,?,?,?,?)',(str(50+index),1,source.name,'Unstable','Completed',90-index))
        connection.commit();real=self.module.source_state;content_calls=[]
        def unstable(source,content=False,**kwargs):
            result=real(source,content=content,**kwargs)
            if content:
                content_calls.append(str(source))
                raise ValueError('actual hash completed but capture unstable')
            return result
        with patch.object(self.module,'source_state',unstable):result=self.module.work()
        self.assertEqual(len(content_calls),1)
        self.assertEqual(result['packs'],[])
        self.assertEqual(len(self.store.all('pack')),0)
        self.assertEqual(len(self.store.all('pack_observation')),3)

    def test_oversize_unknown_refuses_before_payload_read(self):
        connection,_=self.prepare(0);source=self.root/'large.zip'
        with source.open('wb') as stream:stream.truncate(256*1024**2+1)
        connection.execute('INSERT INTO ddl_info VALUES (?,?,?,?,?,?)',('44',1,source.name,'Large','Completed',100))
        connection.commit()
        with patch.object(Path,'open',side_effect=AssertionError('oversize must not hash')):result=self.module.work()
        self.assertEqual(result['packs'],[]);self.assertIn(str(source),result['protected'])
        self.assertFalse(any(r['ddl_id']=='44' for r in self.store.all('pack')))
        self.assertEqual(self.store.all('pack_observation')[0]['phase'],'review')


if __name__=='__main__':unittest.main()
