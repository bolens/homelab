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
        self.mylar=SimpleNamespace(workflow=self.workflow,CONFIG=SimpleNamespace(DESTINATION_DIR=str(self.library)))
        self.modules=patch.dict(sys.modules,{'mylar':self.mylar,'mylar.workflow_store':sys.modules['workflow_store']})
        self.modules.start();self.addCleanup(self.modules.stop)
        self.module=load('pack_intake')
        self.key='a'*64
        self.store.set('pack',self.key,{'id':self.key,'ddl_id':'1','source':'/private/download','name':'Test pack','phase':'discovered','members':[],'inventory_complete':False})

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

    def report(self,destination):
        member={'id':'b'*64,'name':'Test.cbz','kind':'issue','phase':'confirmed',
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
                'name':'old','phase':'confirmed','cleanup_complete':True,'inventory_complete':True,'members':[]})
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
