"""Real body FD/full-byte controls. Body observation carries no event rights."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import comic_retained_standalone_parent as p

class BodyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.path=self.root/'initialized-body.json';self.bodies=[]
    def tearDown(self):
        for body in self.bodies:
            seal=p._BODIES.pop(body,None)
            if seal:
                try:os.close(seal[2])
                except OSError:pass
        self.tmp.cleanup()
    def prepare(self,value):
        data=p.encode(value);self.path.write_bytes(data);os.chmod(self.path,0o600)
        ref=dict(path=str(self.path),sha256=hashlib.sha256(data).hexdigest(),signature9=list(p.nine(os.lstat(self.path))))
        frame=(((str(self.path),tuple(ref['signature9'])),),tuple((str(parent),p.five(os.lstat(parent))) for parent in self.path.parents),((str(self.root),tuple(sorted(os.listdir(self.root)))),))
        return ref,frame
    def observe(self,value):
        ref,frame=self.prepare(value);body=p.BodyObservation.read_original(ref,str(self.path),frame);self.bodies.append(body);return body
    def test_full_canonical_body_larger_than_wire_remains_complete(self):
        value={'full_sql':{'schema':[],'rows':{'table':['x'*(p.WIRE_BYTES+100)]}}}
        body=self.observe(value);self.assertEqual(body.decoded(),value);self.assertGreater(len(body.close()),p.WIRE_BYTES)
    def test_public_constructor_and_forged_registry_refused(self):
        with self.assertRaises(ValueError):p.BodyObservation()
        with self.assertRaises(ValueError):object.__new__(p.BodyObservation).close()
    def test_replaced_same_byte_body_refused(self):
        body=self.observe({'full':'original'});old=self.path.read_bytes();self.path.unlink();self.path.write_bytes(old);os.chmod(self.path,0o600)
        with self.assertRaises(ValueError):body.close()
    def test_first_read_mode_drift_refused_without_rebaseline(self):
        ref,frame=self.prepare({'full':'original'});original=os.read;fired=[]
        def changed(fd,size):
            value=original(fd,size)
            if not fired:fired.append(True);os.chmod(self.path,0o640)
            return value
        with patch.object(os,'read',changed),self.assertRaises(ValueError):p.BodyObservation.read_original(ref,str(self.path),frame)
        self.assertTrue(fired)
    def test_decode_callback_original_replacement_refused(self):
        body=self.observe({'full':'original'});original=p.decode_body;fired=[]
        def changed(data):
            value=original(data)
            if not fired:
                fired.append(True);old=self.path.read_bytes();self.path.unlink();self.path.write_bytes(old);os.chmod(self.path,0o600)
            return value
        with patch.object(p,'decode_body',changed),self.assertRaises(ValueError):body.decoded()
        self.assertTrue(fired)
    def test_final_FD_stat_callback_mode_drift_followed_by_path_close(self):
        body=self.observe({'full':'original'});original=os.fstat;fired=[];count=[0]
        def changed(fd):
            z=original(fd);count[0]+=1
            if count[0]==2:fired.append(True);os.chmod(self.path,0o640)
            return z
        with patch.object(os,'fstat',changed),self.assertRaises(ValueError):body.close()
        self.assertTrue(fired)
    def test_unknown_path_and_wrong_original_ref_refused(self):
        ref,frame=self.prepare({'full':'original'})
        with self.assertRaises(ValueError):p.BodyObservation.read_original(ref,str(self.root/'foreign.json'),frame)
        ref['signature9'][4]+=1
        with self.assertRaises(ValueError):p.BodyObservation.read_original(ref,str(self.path),frame)
    def test_foreign_namespace_after_read_refused(self):
        body=self.observe({'full':'original'});(self.root/'foreign').write_text('untouched')
        with self.assertRaises(ValueError):body.close()
    def test_duplicate_or_noncanonical_full_body_refused(self):
        for data in (b'{"full":1,"full":2}',b'{"full": 1}'):
            self.path.write_bytes(data);os.chmod(self.path,0o600)
            ref=dict(path=str(self.path),sha256=hashlib.sha256(data).hexdigest(),signature9=list(p.nine(os.lstat(self.path))))
            frame=(((str(self.path),tuple(ref['signature9'])),),(),())
            with self.assertRaises(ValueError):p.BodyObservation.read_original(ref,str(self.path),frame)
    def test_fixed_body_capacity_refuses_sparse_oversize_before_read(self):
        with self.path.open('wb') as stream:stream.truncate(p.BODY_BYTES+1)
        os.chmod(self.path,0o600);ref=dict(path=str(self.path),sha256='a'*64,signature9=list(p.nine(os.lstat(self.path))))
        frame=(((str(self.path),tuple(ref['signature9'])),),(),())
        with patch.object(os,'read',side_effect=AssertionError('oversize streamed')),self.assertRaises(ValueError):p.BodyObservation.read_original(ref,str(self.path),frame)



    def test_real_24_table_SQL_body_preserves_all_rows_and_types_over_wire(self):
        import sqlite3
        from contextlib import closing
        native=self.root/'mylar.db';workflow=self.root/'workflow.sqlite'
        with closing(sqlite3.connect(native)) as db:
            for number in range(24):
                db.execute('CREATE TABLE table_'+str(number)+' (id INTEGER, text TEXT, value REAL, blob BLOB, empty TEXT)')
                db.executemany('INSERT INTO table_'+str(number)+' VALUES (?,?,?,?,?)',
                    ((index,'x'*96+'é'*8,0.5,b'\x00\xff',None) for index in range(2400)))
            db.commit()
        with closing(sqlite3.connect(workflow)) as db:
            db.execute('CREATE TABLE records (kind TEXT, key TEXT, value TEXT, updated REAL)');db.commit()
        native_original=p.nine(os.lstat(native));workflow_original=p.nine(os.lstat(workflow))
        snapshot=p.sql_snapshot(str(native),native_original)
        self.assertEqual(len(snapshot['rows']),24);self.assertEqual(sum(map(len,snapshot['rows'].values())),57600)
        row=p.json.loads(snapshot['rows']['table_0'][0]);self.assertEqual(row[2],0.5);self.assertEqual(row[3],{'blob':'00ff'});self.assertIsNone(row[4])
        value={'native_sql':snapshot,'workflow_sql':p.sql_snapshot(str(workflow),workflow_original)}
        body=self.observe(value);self.assertGreater(len(body.close()),p.WIRE_BYTES);self.assertEqual(body.decoded(),value)
        self.assertEqual(p.nine(os.lstat(native)),native_original);self.assertEqual(p.nine(os.lstat(workflow)),workflow_original)

if __name__=='__main__':unittest.main()
