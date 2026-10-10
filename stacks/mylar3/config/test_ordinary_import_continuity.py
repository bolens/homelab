"""Real SQLite/import copy/native guards/Writer; upstream application adapters are fixtures.

These source controls never claim installed daemon or complete PostProcessor proof.
No native.require/confirmation/terminal completion is substituted.
"""
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import media_writer
import ordinary_import_history as history
import ordinary_import_continuity as continuity
import test_publication_rename as fixture
import publication_native as native


class Processor:
    download_info={'provider':'DDL','id':'56'}
    _publication_handoff=None


class Continuity(fixture.RenameTests):
    def setUp(self):
        super().setUp()
        # Same source-module objects in the established host SDK fixture only.
        aliases={'mylar.ordinary_import_history':history,'mylar.ordinary_import_continuity':continuity,
                 'mylar.media_writer':media_writer}
        p=patch.dict(sys.modules,aliases);p.start();self.addCleanup(p.stop)
        for key,value in aliases.items():setattr(self.mylar,key.split('.')[-1],value)
        self.mylar.CONFIG.FILE_OPTS='copy';self.mylar.CONFIG.CHMOD_FILE='0600';self.mylar.CONFIG.CHGROUP=''
        self.processor=Processor()
        self.mylar.processing_guard=SimpleNamespace(_ACTIVE=SimpleNamespace(processor=self.processor))
        self.mylar.db=SimpleNamespace(DBConnection=lambda:self.adapter)
        with self.connection() as db:
            db.execute('CREATE TABLE ddl_info(id TEXT,issueid TEXT,comicid TEXT,status TEXT,pack INTEGER)')
            db.execute('INSERT INTO ddl_info VALUES (?,?,?,?,0)',('56',self.owner['issueid'],self.owner['parentcomicid'],'Completed'))
        continuity.initialize(self.root)
        self.imported=self.library/'Imported.001.(2020).cbz'
        with self.writer.hold():
            proof=native.require(self.source,issueid=self.owner['issueid'],comicid=self.owner['parentcomicid'])
            history.begin(self.processor,proof,self.imported)
            history.file_ops(self.processor,lambda *_:self.fail('legacy copier called'),self.source,self.imported)
            with self.connection() as db:
                db.execute('UPDATE issues SET Location=? WHERE IssueID=?',(self.imported.name,self.owner['issueid']))
            history.complete(self.processor,str(self.imported),issueid=self.owner['issueid'],comicid=self.owner['parentcomicid'])
        self.source=self.imported
        self.request.update(source=str(self.source),target='Renamed.001.(2020).cbz')
        self.target=self.source.with_name(self.request['target'])
        self.info.update(self.request)
        with history._database() as db:self.token=db.execute('SELECT token FROM completions').fetchone()[0]
        with history._database() as db:self.original=tuple(db.execute('SELECT attempt,ack FROM completions').fetchone())

    def test_original_ack_then_real_owned_rename_continuation(self):
        self.assertTrue(history.confirmed_token(self.token,self.owner,str(self.source)))
        result=self.call_rename()
        self.assertEqual(result['phase'],'committed')
        self.assertTrue(history.confirmed_token(self.token,self.owner,str(self.target)))
        self.assertTrue(history.confirmed_ddl('56',self.owner,str(self.target)))
        with history._database() as db:self.assertEqual(tuple(db.execute('SELECT attempt,ack FROM completions').fetchone()),self.original)

    def call_rename(self):
        import release_naming
        return release_naming.rename(self.request)

    def test_created_pending_metadata_cannot_refresh_at_first_fsync(self):
        real=continuity.os.fsync;fired=[]
        def late(fd):
            real(fd)
            target=os.readlink('/proc/self/fd/'+str(fd))
            if target.endswith('.pending.json') and continuity._NAME in target:
                os.fchmod(fd,0o640);fired.append(True)
        with patch.object(continuity.os,'fsync',late):
            with self.assertRaises((ValueError,native.Review)):self.call_rename()
        self.assertTrue(fired);self.assertTrue(self.source.exists());self.assertFalse(self.target.exists())
        self.assertFalse(self.writer.fenced(release=True))

    def test_original_pending_closed_after_done_writer_callback(self):
        real=continuity._write;fired=[]
        def late(h,p,value,**kwargs):
            result=real(h,p,value,**kwargs)
            if p.name.endswith('.done.json'):
                os.chmod(p.with_name(p.name.replace('.done.json','.pending.json')),0o640);fired.append(True)
            return result
        with patch.object(continuity,'_write',late):
            with self.assertRaises((ValueError,native.Review)):self.call_rename()
        self.assertTrue(fired);self.assertTrue(self.target.exists())
        self.assertFalse(history.confirmed_token(self.token,self.owner,str(self.target)))
        with history._database() as db:self.assertEqual(tuple(db.execute('SELECT attempt,ack FROM completions').fetchone()),self.original)

    def test_created_done_original_identity_closed_after_last_helper(self):
        real=history._close;fired=[]
        def late(nodes,files):
            result=real(nodes,files)
            for name,vector in files:
                if name.endswith('.done.json') and not fired:
                    p=Path(name);raw=p.read_bytes();p.unlink();p.write_bytes(raw);p.chmod(0o600);fired.append(True)
            return result
        with patch.object(history,'_close',late):
            with self.assertRaises((ValueError,native.Review)):self.call_rename()
        self.assertTrue(fired);self.assertTrue(self.target.exists())
        self.assertFalse(history.confirmed_token(self.token,self.owner,str(self.target)))

    def test_pending_same_bytes_new_inode_and_missing_receipt_hold_passive(self):
        self.call_rename();p=next((self.root/continuity._NAME).glob('*.pending.json'))
        raw=p.read_bytes();p.unlink();p.write_bytes(raw);p.chmod(0o600)
        self.assertFalse(history.confirmed_token(self.token,self.owner,str(self.target)))
        p.unlink();self.assertFalse(history.confirmed_token(self.token,self.owner,str(self.target)))

    def test_last_observation_callback_cannot_change_pending(self):
        real=continuity._observe;fired=[]
        def late(*args):
            result=real(*args)
            pending=next((self.root/continuity._NAME).glob('*.pending.json'))
            os.chmod(pending,0o640);fired.append(True)
            return result
        with patch.object(continuity,'_observe',late):
            with self.assertRaises((ValueError,native.Review)):self.call_rename()
        self.assertTrue(fired);self.assertFalse(history.confirmed_token(self.token,self.owner,str(self.target)))

    def test_last_observation_callback_cannot_create_catalog_companion(self):
        real=continuity._observe;fired=[]
        def late(*args):
            result=real(*args);(self.root/'mylar.db-wal').write_bytes(b'foreign');fired.append(True)
            return result
        with patch.object(continuity,'_observe',late):
            with self.assertRaises((ValueError,native.Review)):self.call_rename()
        self.assertTrue(fired);self.assertFalse(history.confirmed_token(self.token,self.owner,str(self.target)))

    def test_foreign_source_and_no_ack_are_not_successors(self):
        self.call_rename()
        self.assertFalse(history.confirmed_token('f'*64,self.owner,str(self.target)))
        self.target.write_bytes(b'foreign')
        self.assertFalse(history.confirmed_token(self.token,self.owner,str(self.target)))

    def test_erased_original_ack_refuses_valid_terminal(self):
        self.call_rename()
        with history._database(write=True) as db:db.execute('UPDATE completions SET ack=NULL')
        self.assertFalse(history.confirmed_token(self.token,self.owner,str(self.target)))

    def test_lost_successor_response_keeps_facts_and_never_replays(self):
        actual=continuity._write
        def lost(h,p,v,**kwargs):
            result=actual(h,p,v,**kwargs)
            if p.name.endswith('.done.json'):raise OSError('fixture lost response')
            return result
        with patch.object(continuity,'_write',side_effect=lost):
            with self.assertRaises((OSError,native.Review)):self.call_rename()
        self.assertTrue(self.target.exists());self.assertFalse(self.source.exists())
        self.assertTrue(history.confirmed_token(self.token,self.owner,str(self.target)))

    def test_changed_pending_preimage_refuses_completion(self):
        actual=continuity._write
        def corrupt(h,p,v,**kwargs):
            result=actual(h,p,v,**kwargs)
            if p.name.endswith('.pending.json'):p.write_text('{}')
            return result
        with patch.object(continuity,'_write',side_effect=corrupt):
            with self.assertRaises((ValueError,native.Review)):self.call_rename()
        self.assertFalse(history.confirmed_token(self.token,self.owner,str(self.target)))

    def test_output_parent_replacement_refuses_before_foreign_write(self):
        root=self.root/continuity._NAME;actual=continuity._write
        def swapped(h,p,v,**kwargs):
            if p.name.endswith('.pending.json'):
                root.rename(root.with_name('original-lineage'));root.mkdir(mode=0o700)
            return actual(h,p,v,**kwargs)
        with patch.object(continuity,'_write',side_effect=swapped):
            with self.assertRaises(native.Review):self.call_rename()
        self.assertTrue(self.source.exists());self.assertFalse(self.target.exists())
        self.assertEqual(list(root.iterdir()),[]);self.assertFalse(self.writer.fenced(release=True))

    def test_current_source_without_closed_predecessor_holds_before_fence(self):
        os.chmod(self.source,0o640)
        with self.assertRaises(native.Review):self.call_rename()
        self.assertTrue(self.source.exists());self.assertFalse(self.target.exists())
        self.assertFalse(self.writer.fenced(release=True))

    def test_late_inactive_catalog_claim_alias_refuses(self):
        self.call_rename()
        with self.connection() as db:db.execute('INSERT INTO issues(IssueID,ComicID,Location,Status) VALUES (?,?,?,?)',('777',self.owner['parentcomicid'],'late.cbz','Wanted'))
        actual=continuity._terminal;claim=self.library/'late.cbz';fired=[]
        def late(w,r):
            result=actual(w,r);claim.symlink_to(self.target);fired.append(True);return result
        with patch.object(continuity,'_terminal',side_effect=late):
            self.assertFalse(history.confirmed_token(self.token,self.owner,str(self.target)))
        self.assertTrue(fired);self.assertTrue(claim.is_symlink())

    def test_late_original_history_or_current_file_change_refuses(self):
        self.call_rename();actual=continuity._terminal
        for target in (self.root/history._NAME,self.target):
            mode=target.stat().st_mode&0o777
            def late(w,r):
                result=actual(w,r);os.chmod(target,0o640);return result
            with patch.object(continuity,'_terminal',side_effect=late):
                self.assertFalse(history.confirmed_token(self.token,self.owner,str(self.target)))
            os.chmod(target,mode)

    def test_duplicate_or_linked_record_is_not_confirmation(self):
        self.call_rename();root=self.root/continuity._NAME
        record=next(root.glob('*.done.json'));copy=root/('rename-'+'f'*64+'.done.json')
        copy.write_bytes(record.read_bytes());os.chmod(copy,0o600)
        self.assertFalse(history.confirmed_token(self.token,self.owner,str(self.target)))
        copy.unlink();copy.symlink_to(record)
        self.assertFalse(history.confirmed_token(self.token,self.owner,str(self.target)))

    def test_unclosed_terminal_is_not_confirmation(self):
        self.call_rename()
        (self.writer.root/'release-completed-v1'/(__import__('release_naming').key(self.request)+'.json')).unlink()
        self.assertFalse(history.confirmed_token(self.token,self.owner,str(self.target)))

    def test_last_terminal_callback_catalog_companion_refuses(self):
        self.call_rename();actual=continuity._terminal
        def late(w,r):
            result=actual(w,r)
            (self.root/'mylar.db-wal').write_bytes(b'foreign')
            return result
        with patch.object(continuity,'_terminal',side_effect=late):
            self.assertFalse(history.confirmed_token(self.token,self.owner,str(self.target)))


import test_publication_maintenance as maintenance
import shutil

class Metadata(maintenance.PreservedSupplementTests):
    def setUp(self):
        super().setUp()
        aliases={'mylar.ordinary_import_history':history,'mylar.ordinary_import_continuity':continuity,'mylar.media_writer':media_writer}
        p=patch.dict(sys.modules,aliases);p.start();self.addCleanup(p.stop)
        for key,value in aliases.items():setattr(self.mylar,key.split('.')[-1],value)
        continuity.initialize(self.root)
        self.mylar.CONFIG.FILE_OPTS='copy';self.mylar.CONFIG.CHMOD_FILE='0644';self.mylar.CONFIG.CHGROUP=''
        self.processor=Processor();self.mylar.processing_guard=SimpleNamespace(_ACTIVE=SimpleNamespace(processor=self.processor))
        self.mylar.db=SimpleNamespace(DBConnection=lambda:self.adapter)
        with self.connection() as db:
            db.execute('CREATE TABLE ddl_info(id TEXT,issueid TEXT,comicid TEXT,status TEXT,pack INTEGER)')
            db.execute('INSERT INTO ddl_info VALUES (?,?,?,?,0)',('56',self.owner['issueid'],self.owner['parentcomicid'],'Completed'))
        with self.writer.hold():
            proof=native.require(self.source,issueid=self.owner['issueid'],comicid=self.owner['parentcomicid'])
            incoming=self.root/'ordinary-input.cbz';shutil.copyfile(self.source,incoming)
            # Explicit upstream matched-source fixture; actual exclusive copy, native destination
            # require, catalog join and completion SQLite are exercised unchanged.
            import publication_guard as guard
            proof=dict(proof,path=str(incoming),inventory=dict(proof['inventory'],source_signature=list(guard.signature(incoming.lstat()))))
            self.source.unlink()
            history.begin(self.processor,proof,self.source)
            history.file_ops(self.processor,lambda *_:self.fail('legacy copier'),incoming,self.source)
            os.chmod(self.source,0o644)
            history.complete(self.processor,str(self.source),issueid=self.owner['issueid'],comicid=self.owner['parentcomicid'])
        with history._database() as db:
            self.token=db.execute('SELECT token FROM completions').fetchone()[0]
            self.original_ack=tuple(db.execute('SELECT attempt,ack FROM completions').fetchone())

    def test_real_rename_then_metadata_is_one_original_import_chain(self):
        import release_naming
        self.request.update(source=str(self.source),target='Metadata.Renamed.001.(2020).cbz',sha256=self.before)
        self.info.update(self.request)
        self.proposal_patch.stop()
        p=patch.object(release_naming,'proposal',return_value=self.info);p.start();self.addCleanup(p.stop)
        result=release_naming.rename(self.request)
        self.source=Path(result['destination'])
        self.assertTrue(history.confirmed_token(self.token,self.owner,str(self.source)))
        self.apply()
        self.assertTrue(history.confirmed_token(self.token,self.owner,str(self.source)))
        with history._database() as db:self.assertEqual(tuple(db.execute('SELECT attempt,ack FROM completions').fetchone()),self.original_ack)

    def test_real_preserved_metadata_continuation_retains_original_ack(self):
        self.assertTrue(history.confirmed_token(self.token,self.owner,str(self.source)))
        result=self.apply()
        self.assertNotEqual(result['before'],result['after'])
        self.assertTrue(history.confirmed_token(self.token,self.owner,str(self.source)))
        with history._database() as db:self.assertEqual(tuple(db.execute('SELECT attempt,ack FROM completions').fetchone()),self.original_ack)


import test_release_naming as legacy

class PassiveSnapshot(unittest.TestCase):
    setUp=legacy.NamingTest.setUp

    def test_missing_catalog_with_ack_token_is_review_without_member_mutation(self):
        import pack_intake
        p=patch.object(pack_intake.workflow,'store',return_value=self.store);p.start();self.addCleanup(p.stop)
        info=self.source.stat()
        member=dict(id='d'*64,kind='issue',phase='confirmed',name=self.source.name,issueid='1',comicid='2',
            destination=str(self.source),destination_sha256=self.request['sha256'],ordinary_import_token='f'*64,
            signature=[info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns])
        record=dict(id='a'*64,ddl_id='7',phase='confirmed',members=[member],inventory_complete=True,name='Pack')
        before=json.dumps(record,sort_keys=True)
        result=pack_intake.snapshot([record])
        self.assertFalse(result[0]['complete']);self.assertEqual(result[0]['members'][0]['phase'],'review')
        self.assertEqual(json.dumps(record,sort_keys=True),before)


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(cls(name) for cls in (Continuity,Metadata,PassiveSnapshot) for name in cls.__dict__ if name.startswith('test_'))

if __name__=='__main__':unittest.main()
