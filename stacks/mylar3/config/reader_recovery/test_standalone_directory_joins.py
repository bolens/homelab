"""Real backup/SQLite/filesystem V9 joins; source-event declarations are fixtures,
not production child capabilities, activation or catalog acceptance."""
from contextlib import closing
import copy
import hashlib
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import comic_retained_standalone_parent as p
import comic_retained_standalone_backup as b

class DirectoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.root.chmod(0o700)
        self.data=self.root/'native';self.data.mkdir();self.reader=self.root/'reader';self.reader.mkdir()
        self.cache=self.root/'cache';self.cache.mkdir();self.library=self.root/'library';self.library.mkdir()
        self.source=self.cache/'source.cbz';self.source.write_bytes(b'source')
        self.target=self.library/'target.CBZ';self.target.write_bytes(b'target actual bytes')
        self.native=self.data/'mylar.db';self.workflow=self.data/'workflow.sqlite'
        for path in (self.native,self.reader/'database.sqlite'):
            with closing(sqlite3.connect(path)) as db:db.execute('CREATE TABLE unchanged(id INTEGER PRIMARY KEY,value BLOB)');db.execute('INSERT INTO unchanged VALUES (1,?)',(b'\x00\xff',));db.commit()
        with closing(sqlite3.connect(self.workflow)) as db:db.execute('CREATE TABLE records(kind TEXT,key TEXT,value TEXT,updated REAL,PRIMARY KEY(kind,key))');db.commit()
        self.token='a'*64;self.journal=self.data/'retained-standalone-v1';self.directory=self.journal/self.token
        existing=getattr(self,'existing_journal',False)
        if existing:
            self.mkdir(self.journal);self.mkdir(self.journal/'older-original-token')
            self.write(self.journal/'older-original-token'/'original.json',b'retained old token')
        pre=self.stamp(self.data);pre_names=self.names(self.data)
        journal_before=self.stamp(self.journal) if existing else None
        journal_names=self.names(self.journal) if existing else []
        if not existing:self.mkdir(self.journal)
        jb=None if existing else self.stamp(self.journal)
        self.mkdir(self.directory);birth=self.stamp(self.directory)
        (self.directory/'intent.json').write_bytes(b'original intent');(self.directory/'intent.json').chmod(0o600)
        initialized=self.stamp(self.directory);initialized_names=self.names(self.directory)
        journal=dict(path=str(self.journal),before9=journal_before,before_names=journal_names,journal_birth9=jb,after9=self.stamp(self.journal),after_names=self.names(self.journal),
                     directory=str(self.directory),birth9=birth,initialized9=initialized,initialized_names=initialized_names,preservation=[],accepted=None)
        sql=dict(path=str(self.data),database_roles=['native','workflow'],pre_initialize9=pre,pre_initialize_names=pre_names,
                 initialized9=self.stamp(self.data),initialized_names=self.names(self.data),backup9=None,backup_names=None,native_noop=None,workflow_cas=None)
        self.carrier=self.data/p.CARRIER_NAME;self.artifact=self.carrier/self.token;self.mkdir(self.carrier);self.mkdir(self.artifact)
        self.write(self.artifact/'initialized-body.json',b'full initialized body')
        pubrow=dict(path=str(self.data),signature9=self.stamp(self.data),names=self.names(self.data))
        self.pub1=dict(carrier_baseline='absent',carrier_after9=self.stamp(self.carrier),carrier_after_names=[self.token],
                       directory_after9=self.stamp(self.artifact),sql_parents_after_publication=[pubrow])
        self.initial=dict(token=self.token,target=str(self.target),source=str(self.source),journal=journal,sql_parents=[sql],
                          files={str(path):self.stamp(path) for path in (self.native,self.workflow,self.target,self.source)},
                          hashes={str(path):self.hash(path) for path in (self.native,self.workflow,self.target,self.source)})
        self.initial['sql']=p.sql_snapshot(self.native,self.initial['files'][str(self.native)])
        self.initial['workflow_sql']=p.sql_snapshot(self.workflow,self.initial['files'][str(self.workflow)])
        scopes=[dict(role='native_state',root=str(self.data),databases=['mylar.db','workflow.sqlite']),
                dict(role='reader_state',root=str(self.reader),databases=['database.sqlite']),
                dict(role='retained_source',root=str(self.source),databases=[]),dict(role='existing_target',root=str(self.target),databases=[])]
        self.backup=b.copy_and_verify(scopes,self.root/'copies')
        self.final=copy.deepcopy(self.initial);jf=self.final['journal'];last=initialized;last_names=initialized_names
        for name in ('target-preserved.cbz','target-restored.cbz'):
            path=self.directory/name;self.write(path,self.target.read_bytes());after=self.stamp(self.directory);after_names=self.names(self.directory)
            jf['preservation'].append(dict(name=name,before9=last,after9=after,before_names=last_names,after_names=after_names,file_ref=self.ref(path)))
            last=after;last_names=after_names
        before=self.stamp(self.data)
        with closing(sqlite3.connect(self.native)) as db:db.execute('UPDATE unchanged SET value=value WHERE id=1');db.commit()
        after=self.stamp(self.data)
        row=self.final['sql_parents'][0];row.update(backup9=pubrow['signature9'],backup_names=pubrow['names'],native_noop=dict(before9=before,after9=after,names=pubrow['names']))
        self.write(self.directory/'accepted.json',b'original owning ACK fixture')
        jf['accepted']=dict(name='accepted.json',before9=last,after9=self.stamp(self.directory),before_names=last_names,after_names=self.names(self.directory),file_ref=self.ref(self.directory/'accepted.json'))
        before=self.stamp(self.data)
        with closing(sqlite3.connect(self.workflow)) as db:db.execute('INSERT INTO records VALUES (?,?,?,?)',('retained_standalone',self.token,p.encode(dict(version=1,fixture_only=True)).decode(),0.0));db.commit()
        after=self.stamp(self.data);row['workflow_cas']=dict(before9=before,after9=after,names=pubrow['names'])
        self.pub3=copy.deepcopy(self.pub1);self.pub3.update(directory_before9=self.pub1['directory_after9'])
        self.write(self.artifact/'observed-body.json',b'full observed body')
        self.pub3.update(directory_after9=self.stamp(self.artifact),after_names=self.names(self.artifact),sql_parents_after_publication=[dict(path=str(self.data),signature9=after,names=pubrow['names'])])
        for path in (self.native,self.workflow):
            self.final['files'][str(path)]=self.stamp(path);self.final['hashes'][str(path)]=self.hash(path)
        self.final['sql']=p.sql_snapshot(self.native,self.final['files'][str(self.native)])
        self.final['workflow_sql']=p.sql_snapshot(self.workflow,self.final['files'][str(self.workflow)])
        self.observed_ref=self.ref(self.artifact/'observed-body.json')
        self.mounts=[dict(Type='bind',Source=str(self.root),Destination=str(self.root),RW=True)]
    def tearDown(self):self.tmp.cleanup()
    def stamp(self,path):return list(p.nine(os.lstat(path)))
    def names(self,path):return sorted(os.listdir(path))
    def mkdir(self,path):
        path.mkdir(mode=0o700)
        if os.geteuid()==0:os.chown(path,1000,1000)
    def write(self,path,data):
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            os.write(fd,data)
            if os.geteuid()==0:os.fchown(fd,1000,1000)
        finally:os.close(fd)
    def hash(self,path):return hashlib.sha256(path.read_bytes()).hexdigest()
    def ref(self,path):return dict(path=str(path),signature9=self.stamp(path),sha256=self.hash(path))
    def call(self):return p.join_backup_directory_successors(self.initial,self.final,self.pub1,self.pub3,data_root=str(self.data),mounts=self.mounts,backup=self.backup,observed_body_ref=self.observed_ref)
    def test_actual_backup_noop_sole_record_and_three_insertions(self):
        result=self.call();self.assertIs(result['ordinary_import'],False);self.assertIs(result['cleanup'],False)
        self.assertEqual(dict(result['original_vectors'][0])[str(self.directory)],tuple(self.final['journal']['accepted']['after9']))
    def test_existing_journal_exact_original_plus_token_and_old_entries(self):
        self.tmp.cleanup();self.existing_journal=True;self.setUp()
        result=self.call();self.assertIs(result['resume'],False)
        self.assertEqual((self.journal/'older-original-token'/'original.json').read_bytes(),b'retained old token')
    def test_existing_other_token_mutation_holds(self):
        self.tmp.cleanup();self.existing_journal=True;self.setUp()
        (self.journal/'older-original-token'/'original.json').chmod(0o640)
        with self.assertRaises(ValueError):self.call()
    def test_wrong_original_backup9_holds(self):
        self.final['sql_parents'][0]['backup9'][4]+=1
        with self.assertRaises(ValueError):self.call()
    def test_shared_parent_broken_native_to_workflow_chain_holds(self):
        self.final['sql_parents'][0]['workflow_cas']['before9'][4]+=1
        with self.assertRaises(ValueError):self.call()
    def test_unapproved_SQL_nlink_delta_holds(self):
        self.final['sql_parents'][0]['native_noop']['after9'][8]+=1
        with self.assertRaises(ValueError):self.call()
    def test_initial_birth_nlink_exact_plus_one_holds(self):
        self.initial['sql_parents'][0]['initialized9'][8]+=1
        with self.assertRaises(ValueError):self.call()
    def test_preservation_order_foreign_name_holds(self):
        self.final['journal']['preservation'][0]['name']='foreign.cbz'
        with self.assertRaises(ValueError):self.call()
    def test_preservation_changed_original_bytes_holds(self):
        self.final['journal']['preservation'][0]['file_ref']['sha256']='b'*64
        with self.assertRaises(ValueError):self.call()
    def test_missing_original_journal_birth_holds(self):
        self.initial['journal']['journal_birth9']=None
        with self.assertRaises(ValueError):self.call()
    def test_foreign_alias_after_CAS_holds(self):
        os.symlink(self.target,self.directory/'foreign')
        with self.assertRaises(ValueError):self.call()
    def test_unrelated_original_reader_file_change_holds(self):
        (self.reader/'database.sqlite').chmod(0o640)
        with self.assertRaises(ValueError):self.call()
    def test_late_original_source_full9_change_holds(self):
        original=p.raw;fired=[]
        def changed(frame):
            original(frame)
            if not fired:fired.append(True);self.source.chmod(0o640)
        with patch.object(p,'raw',changed),self.assertRaises(ValueError):self.call()
        self.assertTrue(fired)
    def test_late_mapping_projection_holds(self):
        original=p.raw;fired=[]
        def changed(frame):
            original(frame)
            if not fired:fired.append(True);self.mounts[0]['Source']+='/.'
        with patch.object(p,'raw',changed),self.assertRaises(ValueError):self.call()
        self.assertTrue(fired)
    def test_foreign_native_SQL_with_relabelled_current_leaf_still_holds(self):
        with closing(sqlite3.connect(self.native)) as db:db.execute('UPDATE unchanged SET value=? WHERE id=1',(b'foreign',));db.commit()
        self.final['files'][str(self.native)]=self.stamp(self.native);self.final['hashes'][str(self.native)]=self.hash(self.native)
        with self.assertRaises(ValueError):self.call()
    def test_foreign_workflow_record_with_relabelled_current_leaf_holds(self):
        with closing(sqlite3.connect(self.workflow)) as db:db.execute('INSERT INTO records VALUES (?,?,?,?)',('unrelated','foreign','value',0.0));db.commit()
        self.final['files'][str(self.workflow)]=self.stamp(self.workflow);self.final['hashes'][str(self.workflow)]=self.hash(self.workflow)
        with self.assertRaises(ValueError):self.call()
    def test_late_SQL_callback_mutation_after_snapshot_holds(self):
        original=p.sql_snapshot;fired=[]
        def changed(path,stamp):
            value=original(path,stamp)
            if Path(path)==self.workflow and not fired:
                fired.append(True)
                with closing(sqlite3.connect(self.native)) as db:db.execute('UPDATE unchanged SET value=? WHERE id=1',(b'late',));db.commit()
            return value
        with patch.object(p,'sql_snapshot',changed),self.assertRaises(ValueError):self.call()
        self.assertTrue(fired)
    def test_unmatched_selected_original_hash_holds_before_stream(self):
        self.initial['hashes'][str(self.target)]='f'*64
        self.final['hashes'][str(self.target)]='f'*64
        for record in self.final['journal']['preservation']:record['file_ref']['sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'standalone-selected-original-backup-bytes'):self.call()
    def test_wrong_selected_original_full9_holds(self):
        self.initial['files'][str(self.source)][4]+=1
        self.final['files'][str(self.source)][4]+=1
        with self.assertRaises(ValueError):self.call()
    def test_observed_body_self_reference_is_rejected(self):
        self.final['files'][self.observed_ref['path']]=self.observed_ref['signature9']
        self.final['hashes'][self.observed_ref['path']]=self.observed_ref['sha256']
        with self.assertRaisesRegex(ValueError,'standalone-body-no-self-reference'):self.call()
    def test_original_outer_body_ref_full9_change_holds(self):
        self.observed_ref['signature9'][4]+=1
        with self.assertRaises(ValueError):self.call()
    def test_final_physical_callback_mutates_original_SQL_projection_holds(self):
        original=p.os.lstat;fired=[]
        def changed(path,*args,**kwargs):
            value=original(path,*args,**kwargs)
            if Path(path)==self.target and not fired:
                fired.append(True);self.final['sql_parents'][0]['workflow_cas']['after9'][4]=float(self.final['sql_parents'][0]['workflow_cas']['after9'][4])
            return value
        with patch.object(p.os,'lstat',changed),self.assertRaises(ValueError):self.call()
        self.assertTrue(fired)
    def test_late_actual_FD_read_changes_SQL_parent_full9_holds(self):
        original=p.os.fstat;fired=[]
        def changed(fd):
            value=original(fd)
            if value.st_ino==os.lstat(self.directory/'accepted.json').st_ino and not fired:
                fired.append(True);self.data.chmod(0o750);self.data.chmod(0o755)
            return value
        with patch.object(p.os,'fstat',changed),self.assertRaises(ValueError):self.call()
        self.assertTrue(fired)
    def test_distinct_preservation_receipts_cannot_alias_inode(self):
        rows=self.final['journal']['preservation'];rows[1]['file_ref']['signature9'][:2]=rows[0]['file_ref']['signature9'][:2]
        with self.assertRaisesRegex(ValueError,'standalone-independent-preservation-inodes'):self.call()
    def test_original_readonly_mount_shadow_refuses(self):
        self.mounts.append(dict(Type='tmpfs',Source='',Destination=str(self.directory),RW=False))
        with self.assertRaises(ValueError):self.call()
    def test_late_backup_registry_replacement_holds(self):
        original=p.raw;fired=[]
        def changed(frame):
            original(frame)
            if not fired:fired.append(True);b._OBSERVATIONS[self.backup]=dict(b._OBSERVATIONS[self.backup])
        with patch.object(p,'raw',changed),self.assertRaisesRegex(ValueError,'standalone-successor-final-backup-seal'):self.call()
        self.assertTrue(fired)
    def test_last_raw_original_backup_code_leaf_holds(self):
        original=p.raw;fired=[];path=Path(b.__file__);mode=path.stat().st_mode&0o7777
        def changed(frame):
            original(frame)
            if sys._getframe(1).f_code.co_name=='join_backup_directory_successors' and not fired:
                fired.append(True);path.chmod(0o640)
        try:
            with patch.object(p,'raw',changed),self.assertRaisesRegex(ValueError,'standalone-successor-final-file'):self.call()
            self.assertTrue(fired)
        finally:path.chmod(mode)
    def test_last_raw_original_backup_code_ancestor_holds(self):
        original=p.raw;fired=[];path=Path(b.__file__).parent;mode=path.stat().st_mode&0o7777
        def changed(frame):
            original(frame)
            if sys._getframe(1).f_code.co_name=='join_backup_directory_successors' and not fired:
                fired.append(True);path.chmod(mode^0o020)
        try:
            with patch.object(p,'raw',changed),self.assertRaisesRegex(ValueError,'standalone-successor-final-node'):self.call()
            self.assertTrue(fired)
        finally:path.chmod(mode)
    def test_last_raw_original_source_database_seal_holds(self):
        self._late_database_seal('source_databases')
    def test_last_raw_original_copy_database_seal_holds(self):
        self._late_database_seal('databases')
    def _late_database_seal(self,field):
        original=p.raw;fired=[];state=b._OBSERVATIONS[self.backup];saved=state[field]
        def changed(frame):
            original(frame)
            if sys._getframe(1).f_code.co_name=='join_backup_directory_successors' and not fired:
                fired.append(True);state[field]=tuple((path,dict(value,rows={})) for path,value in saved)
        try:
            with patch.object(p,'raw',changed),self.assertRaisesRegex(ValueError,'standalone-successor-final-backup-SQL-seal'):self.call()
            self.assertTrue(fired)
        finally:state[field]=saved
    def test_saved_backup_shape_cannot_join(self):
        self.backup={}
        with self.assertRaises(ValueError):self.call()

if __name__=='__main__':unittest.main()
