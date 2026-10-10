"""Real SQLite/files; synthetic native application and Writer wrappers explicit."""
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('ordinary_import_history',HERE/'ordinary_import_history.py')
history=importlib.util.module_from_spec(spec);spec.loader.exec_module(history)


class Processor:
    def tidyup(self,path):
        self.cleaned+=1;Path(path).unlink()


class History(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.library=self.root/'library';self.library.mkdir()
        self.source=self.root/'source.cbz';self.source.write_bytes(b'actual disposable bytes')
        self.destination=self.library/'issue.cbz'
        self.owner={'table':'issues','issueid':'12','parentcomicid':'34','releasecomicid':'34'}
        self.processor=Processor();self.processor.cleaned=0
        self.processor.download_info={'provider':'DDL','id':'56'}
        self.processor._publication_handoff=None
        self.db=sqlite3.connect(self.root/'mylar.db');self.addCleanup(self.db.close)
        self.db.executescript('CREATE TABLE issues(IssueID TEXT,ComicID TEXT,Status TEXT,Location TEXT);'
            'CREATE TABLE annuals(IssueID TEXT,ComicID TEXT,ReleaseComicID TEXT,Status TEXT,Location TEXT);'
            'CREATE TABLE comics(ComicID TEXT,ComicLocation TEXT);'
            'CREATE TABLE ddl_info(id TEXT,issueid TEXT,comicid TEXT,status TEXT,pack INT);')
        self.db.execute('INSERT INTO issues VALUES (?,?,?,NULL)',('12','34','Snatched'))
        self.db.execute('INSERT INTO comics VALUES (?,?)',('34',str(self.library)))
        self.db.execute('INSERT INTO ddl_info VALUES (?,?,?,?,?)',('56','12','34','Completed',0));self.db.commit()
        def select(query,args):
            self.db.row_factory=sqlite3.Row;return self.db.execute(query,args).fetchall()
        self.native=types.ModuleType('mylar');self.native.__path__=[];self.native.DATA_DIR=str(self.root)
        writer=types.SimpleNamespace(local=(None,types.SimpleNamespace(depth=1)))
        self.native.native_writers=types.SimpleNamespace(publication_mode=lambda:True,active=lambda:True,
                owner=lambda:writer,admission=lambda _:None)
        self.native.CONFIG=types.SimpleNamespace(FILE_OPTS='move',CHMOD_FILE='0600',CHGROUP='')
        self.native.processing_guard=types.SimpleNamespace(_ACTIVE=types.SimpleNamespace(processor=self.processor))
        self.native.db=types.SimpleNamespace(DBConnection=lambda:types.SimpleNamespace(select=select))
        self.native.publication_native=types.SimpleNamespace(require=self.require)
        self.mods=patch.dict(sys.modules,{'mylar':self.native})
        self.mods.start();self.addCleanup(self.mods.stop)
        self.addCleanup(history.forget,self.processor)
    def result(self,path):
        fact,_=history._file(path)
        return {'path':str(path),'owner':dict(self.owner),'inventory':{'payload':'payload-fixture',
               'source_sha256':fact['sha256'],'source_signature':fact['signature']}}
    def require(self,path,**kwargs):return self.result(Path(path))
    def begin(self):history.begin(self.processor,self.result(self.source),self.destination)
    def copy(self):history.file_ops(self.processor,lambda *_:self.fail('native move invoked'),self.source,self.destination)
    def upsert(self):
        self.db.execute("UPDATE issues SET Status='Downloaded',Location=? WHERE IssueID='12'",(self.destination.name,));self.db.commit()
    def complete(self):history.complete(self.processor,str(self.destination),issueid='12',comicid='34')
    def test_actual_catalog_completion_then_durable_ack_then_cleanup(self):
        self.begin();self.copy();self.assertTrue(self.source.exists())
        history.defer_cleanup(self.processor,self.processor.tidyup,self.source)
        self.assertFalse(history.confirmed_ddl('56',self.owner,str(self.destination)))
        self.upsert();self.complete()
        self.assertFalse(self.source.exists());self.assertEqual(self.processor.cleaned,1)
        self.assertTrue(history.confirmed_ddl('56',self.owner,str(self.destination)))
    def test_preexisting_downloaded_archive_is_not_delivery_ack(self):
        shutil.copyfile(self.source,self.destination);self.upsert()
        self.assertFalse(history.confirmed_ddl('56',self.owner,str(self.destination)))
    def test_catalog_failure_retains_source_and_attempt(self):
        self.begin();self.copy();history.defer_cleanup(self.processor,self.processor.tidyup,self.source)
        with self.assertRaises(ValueError):self.complete()
        self.assertTrue(self.source.exists());self.assertEqual(self.processor.cleaned,0)
        with self.assertRaises(ValueError):self.begin()
    def test_lost_ack_before_commit_retained_no_retry(self):
        self.begin();self.copy();self.upsert();history.defer_cleanup(self.processor,self.processor.tidyup,self.source)
        original=history._database
        @contextmanager
        def fail(*,write=False):
            with original(write=write) as database:
                yield database
                if write:raise sqlite3.OperationalError('disposable lost commit')
        with patch.object(history,'_database',fail):
            with self.assertRaises(sqlite3.OperationalError):self.complete()
        self.assertTrue(self.source.exists());self.assertEqual(self.processor.cleaned,0)
        self.assertFalse(history.confirmed_ddl('56',self.owner,str(self.destination)))
        history.forget(self.processor)
        with self.assertRaises(ValueError):self.begin()
    def test_lost_response_after_durable_commit_passive_confirmation(self):
        self.begin();self.copy();self.upsert();history.defer_cleanup(self.processor,self.processor.tidyup,self.source)
        original=history._database
        @contextmanager
        def lost(*,write=False):
            with original(write=write) as database:yield database
            if write:raise sqlite3.OperationalError('disposable lost response')
        with patch.object(history,'_database',lost):
            with self.assertRaises(sqlite3.OperationalError):self.complete()
        self.assertTrue(self.source.exists());self.assertEqual(self.processor.cleaned,0)
        self.assertTrue(history.confirmed_ddl('56',self.owner,str(self.destination)))
    def test_same_bytes_replacement_invalidates_ack(self):
        self.begin();self.copy();self.upsert();self.complete()
        data=self.destination.read_bytes();self.destination.unlink();self.destination.write_bytes(data)
        self.assertFalse(history.confirmed_ddl('56',self.owner,str(self.destination)))
    def test_late_source_change_before_copy_refused(self):
        self.begin();self.source.chmod(0o640)
        with self.assertRaises(ValueError):self.copy()
        self.assertFalse(self.destination.exists())
    def test_foreign_delivery_and_owner_do_not_ack(self):
        self.begin();self.copy();self.upsert();self.complete()
        self.assertFalse(history.confirmed_ddl('57',self.owner,str(self.destination)))
        self.assertFalse(history.confirmed_ddl('56',dict(self.owner,releasecomicid='999'),str(self.destination)))
    def test_pack_unbound_delivery_refused_before_copy(self):
        self.db.execute('UPDATE ddl_info SET pack=1');self.db.commit()
        with self.assertRaises(ValueError):self.begin()
        self.assertTrue(self.source.exists());self.assertFalse(self.destination.exists())
    def test_original_coordinated_token_reused(self):
        proof={'token':'a'*64,'owner':dict(self.owner),'payload':'payload-fixture','census':'original-fixture-census'}
        self.processor._publication_handoff=proof
        self.begin();self.copy();self.upsert();self.complete()
        self.assertTrue(history.confirmed_token('a'*64,self.owner,str(self.destination)))
        self.assertFalse(history.confirmed_token('b'*64,self.owner,str(self.destination)))
    def test_unknown_delivery_preserves_legacy_behavior(self):
        self.processor.download_info={'provider':'NZB'}
        called=[];history.begin(self.processor,None,self.destination)
        history.defer_cleanup(self.processor,lambda:called.append(True))
        self.assertEqual(called,[True])
    def test_annual_release_owner_exact(self):
        self.db.execute('DELETE FROM issues');self.db.execute('INSERT INTO annuals VALUES (?,?,?,?,NULL)',('12','34','78','Snatched'));self.db.commit()
        self.owner.update(table='annuals',releasecomicid='78')
        self.begin();self.copy()
        self.db.execute("UPDATE annuals SET Status='Downloaded',Location=?",(self.destination.name,));self.db.commit()
        self.complete();self.assertTrue(history.confirmed_ddl('56',self.owner,str(self.destination)))
        self.db.execute("UPDATE annuals SET ReleaseComicID='79'");self.db.commit()
        self.assertFalse(history.confirmed_ddl('56',self.owner,str(self.destination)))
    def test_guided_original_link_and_durable_ack_required(self):
        store_spec=importlib.util.spec_from_file_location('workflow_store',HERE/'workflow_store.py')
        store_module=importlib.util.module_from_spec(store_spec);store_spec.loader.exec_module(store_module)
        store=store_module.Store(self.root)
        binding={'id':'b'*32,'source_token':'c'*32,'version':'d'*64,'issueid':'12','comicid':'34'}
        command=dict(binding,phase='queued',dispatched=False)
        fact,_=history._file(self.source)
        proof={'version':1,'token':'a'*64,'source':str(self.source),'source_sha256':fact['sha256'],
               'payload':'payload-fixture','owner':dict(self.owner),'census':{'fixture':True},'inventory_sha256':__import__('hashlib').sha256(json.dumps(self.result(self.source)['inventory'],sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()}
        store.set('command',binding['id'],command);store.set('worker_import_attempt','a'*64,proof)
        guard_spec=importlib.util.spec_from_file_location('publication_guard',HERE/'publication_guard.py')
        guard_module=importlib.util.module_from_spec(guard_spec);guard_spec.loader.exec_module(guard_module)
        self.native.publication_native.guard=guard_module
        modules=patch.dict(sys.modules,{'publication_guard':guard_module})
        modules.start();self.addCleanup(modules.stop)
        store=store_module.Store(self.root,existing_only=True)
        self.native.workflow=types.SimpleNamespace(store=lambda:store)
        self.native.publication_native.owner=lambda *_:dict(self.owner)
        history.queue_guided(proof,binding)
        self.assertFalse(history.confirmed_guided(command))
        self.processor._publication_handoff=proof
        self.begin();self.copy();self.upsert();self.complete()
        self.assertTrue(history.confirmed_guided(command))
        self.assertFalse(history.confirmed_guided(dict(command,source_token='f'*32)))

    def test_last_confirmation_helper_mode_change_cannot_emit_positive(self):
        self.begin();self.copy();self.upsert();self.complete()
        original=history._close;fired=[]
        def late(nodes,files):
            original(nodes,files)
            if any(Path(path)==self.destination for path,_ in files):
                self.destination.chmod(0o640);fired.append(True)
        with patch.object(history,'_close',late):
            self.assertFalse(history.confirmed_ddl('56',self.owner,str(self.destination)))
        self.assertTrue(fired)

    def test_fsync_mode_drift_refuses_copy_retains_source(self):
        self.begin();original=os.fsync
        def late(fd):original(fd);os.fchmod(fd,0o640)
        with patch.object(history.os,'fsync',late):
            with self.assertRaises(ValueError):self.copy()
        self.assertTrue(self.source.exists())



    def test_destination_path_replacement_preserves_actual_exclusive_fd(self):
        self.begin();original=history._file;fired=[]
        def late(path):
            if Path(path)==self.destination and not fired:
                fired.append(True);data=self.destination.read_bytes()
                self.destination.rename(self.library/'retained-owned-copy.cbz')
                self.destination.write_bytes(data);self.destination.chmod(0o600)
            return original(path)
        with patch.object(history,'_file',late):
            with self.assertRaises(ValueError):self.copy()
        self.assertTrue(fired);self.assertTrue(self.source.exists())
        self.assertNotIn(self.processor,history._COPIES)

    def test_history_mode_after_catalog_cannot_confirm(self):
        self.begin();self.copy();self.upsert();self.complete()
        original=history._catalog;fired=[]
        def late(*args):
            result=original(*args);(self.root/'ordinary-import-v1.sqlite').chmod(0o640)
            fired.append(True);return result
        with patch.object(history,'_catalog',late):
            self.assertFalse(history.confirmed_ddl('56',self.owner,str(self.destination)))
        self.assertTrue(fired)

    def test_history_ack_erased_after_catalog_cannot_confirm(self):
        self.begin();self.copy();self.upsert();self.complete()
        original=history._catalog;fired=[]
        def late(*args):
            result=original(*args)
            with sqlite3.connect(self.root/'ordinary-import-v1.sqlite') as database:
                database.execute('UPDATE completions SET ack=NULL')
            fired.append(True);return result
        with patch.object(history,'_catalog',late):
            self.assertFalse(history.confirmed_ddl('56',self.owner,str(self.destination)))
        self.assertTrue(fired)

    def test_catalog_wal_after_last_catalog_callback_cannot_confirm(self):
        self.begin();self.copy();self.upsert();self.complete()
        original=history._catalog;fired=[]
        def late(*args):
            result=original(*args);(self.root/'mylar.db-wal').write_bytes(b'foreign')
            fired.append(True);return result
        with patch.object(history,'_catalog',late):
            self.assertFalse(history.confirmed_ddl('56',self.owner,str(self.destination)))
        self.assertTrue(fired)

    def test_guided_last_confirmation_callback_retains_history_and_absences(self):
        self.test_guided_original_link_and_durable_ack_required()
        command={'id':'b'*32,'source_token':'c'*32,'version':'d'*64,'issueid':'12','comicid':'34'}
        real=history._confirmed;fired=[]
        def late(*args,**kwargs):
            result=real(*args,**kwargs)
            (self.root/'ordinary-import-v1.sqlite').chmod(0o640)
            fired.append(True);return result
        with patch.object(history,'_confirmed',late):
            self.assertFalse(history.confirmed_guided(command))
        self.assertTrue(fired)
        (self.root/'ordinary-import-v1.sqlite').chmod(0o600)
        def companion(*args,**kwargs):
            result=real(*args,**kwargs)
            (self.root/'ordinary-import-v1.sqlite-wal').write_bytes(b'foreign')
            return result
        with patch.object(history,'_confirmed',companion):
            self.assertFalse(history.confirmed_guided(command))

if __name__=='__main__':unittest.main()
