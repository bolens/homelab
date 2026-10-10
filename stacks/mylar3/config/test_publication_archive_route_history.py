"""Genuine public preparation/status; disposable source/catalog/Writer/history.
Host SDK resolution is explicit fixture plumbing, not installed acceptance.
"""
import json
import os
import sqlite3
from pathlib import Path
import unittest
from unittest.mock import patch
import test_publication_archive_history as fixture
import publication_archive_prepare_routes as route

class Controls(unittest.TestCase):
    def setUp(self):
        self.f=fixture.History('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.c=self.f.c
    def call(self,action='prepare-archive-repair'):
        return self.c.controller.dispatch(self.c.modules[0].request(json.dumps(dict(version=1,action=action,owner=self.c.owner,operation_id=self.c.operation_id))))
    def test_history_on_prepare_status_preserves_source_and_rights(self):
        source=self.c.source.read_bytes();p=self.call();s=self.call('archive-repair-status')
        self.assertEqual(s['token'],p['token']);self.assertEqual(p['outcome'],'prepared')
        self.assertEqual(self.c.source.read_bytes(),source)
        for key in ('executable','native_grant','mutation_authority','adoption_authority','publication_acceptance','reader_preservation_verified'):
            self.assertIs(p[key],False)
    def test_history_off_prepare_status(self):
        self.f.path.rmdir();p=self.call();self.assertEqual(self.call('archive-repair-status')['token'],p['token'])
        self.assertFalse(self.f.path.exists())
    def test_original_record_vectors_wal_callback_is_held(self):
        real=fixture.history.record_vectors;fired=[]
        def late(ref):
            value=real(ref);Path(str(self.c.controller.native_database)+'-wal').write_bytes(b'foreign');fired.append(True);return value
        with patch.object(fixture.history,'record_vectors',late),self.assertRaisesRegex(self.c.modules[2].Unavailable,'requires review'):self.call()
        self.assertTrue(fired)
    def late(self,mutate):
        real=route.terminal;fired=[]
        def callback(*args):
            real(*args);self.actual_writer=args[1];mutate();fired.append(True)
        with patch.object(route,'terminal',callback),self.assertRaisesRegex(self.c.modules[2].Unavailable,'requires review'):self.call()
        self.assertTrue(fired)
    def test_late_pending_is_held(self):self.late(lambda:(self.c.writer.root/'tagger-v2.pending').write_bytes(b'foreign'))
    def test_late_census_is_held(self):self.late(lambda:(self.f.path/'foreign').write_bytes(b'foreign'))
    def test_late_source_is_held(self):self.late(lambda:self.c.source.write_bytes(self.c.source.read_bytes()+b'foreign'))
    def test_late_parent_is_held(self):self.late(lambda:os.chmod(self.c.library,0o700 if self.c.library.stat().st_mode&0o777!=0o700 else 0o750))
    def test_late_writer_binding_is_held(self):self.late(lambda:setattr(self.actual_writer,'pending',self.c.writer.root/'foreign'))
    def test_late_writer_purpose_is_held(self):self.late(lambda:setattr(self.c.writer.local[1],'allow_pending',True))
    def test_callback_cannot_reseal_passed_terminal_files(self):
        real=route.terminal;fired=[]
        def mutate(*args):
            real(*args);self.c.source.write_bytes(self.c.source.read_bytes()+b'foreign')
            fact=args[5][self.c.source];fact['signature9']=fixture.o.signature(self.c.source)
            fired.append(True)
        with patch.object(route,'terminal',mutate),self.assertRaisesRegex(self.c.modules[2].Unavailable,'requires review'):self.call()
        self.assertTrue(fired)
    def test_callback_cannot_reseal_passed_history_reference(self):
        real=fixture.history.record_vectors;fired=[]
        def mutate(ref):
            value=real(ref);path=Path(ref['path']);path.write_bytes(path.read_bytes()+b' ')
            ref['signature9']=fixture.o.signature(path);fired.append(True);return value
        with patch.object(fixture.history,'record_vectors',mutate),self.assertRaisesRegex(self.c.modules[2].Unavailable,'requires review'):self.call()
        self.assertTrue(fired)
    def test_late_controller_binding_is_held(self):self.late(lambda:setattr(self.c.controller,'roots',[self.c.root]))
    def test_late_absent_claim_is_held(self):
        original=fixture.history.record_vectors;absent=[]
        def capture(ref):
            v=original(ref);p=self.c.library/'unclaimed.cbz';v['claims'].append((str(p),None));absent.append(p);return v
        with patch.object(fixture.history,'record_vectors',capture):self.late(lambda:absent[0].write_bytes(b'foreign'))
    def test_returned_history_cannot_reseal_foreign_namespace(self):
        original=fixture.history.record_vectors
        def reseal(ref):
            v=original(ref);(self.f.path/'foreign').write_bytes(b'foreign')
            for path,names in v['namespaces']:
                if path==str(self.f.path):names.append('foreign');names.sort()
            return v
        with patch.object(fixture.history,'record_vectors',reseal),self.assertRaisesRegex(self.c.modules[2].Unavailable,'requires review'):self.call()
    def test_late_native_wal_after_terminal_is_held(self):self.late(lambda:Path(str(self.c.controller.native_database)+'-wal').write_bytes(b'foreign'))
    def test_late_workflow_wal_after_terminal_is_held(self):self.late(lambda:Path(str(self.c.controller.database)+'-wal').write_bytes(b'foreign'))
    def test_late_catalog_foreign_claim_is_held(self):
        def mutate():
            with sqlite3.connect(self.c.controller.native_database) as db:db.execute('INSERT INTO issues (IssueID,ComicID,Location,Status) VALUES (?,?,?,?)',('789','456','foreign.cbz','Downloaded'))
        self.late(mutate)
    def test_conflicting_history_original_cannot_replace_preparation(self):
        original=fixture.history.record_vectors
        def conflict(ref):
            v=original(ref)
            for p,s in v['files9']:
                if p==str(self.c.source):s[2]+=1;break
            return v
        with patch.object(fixture.history,'record_vectors',conflict),self.assertRaisesRegex(self.c.modules[2].Unavailable,'requires review'):self.call()

if __name__=='__main__':unittest.main()
