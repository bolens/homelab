"""Same-payload native rename controls with genuine authority/catalog/archives."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import publication_rename as owned
import publication_transaction as transaction
import publication_native as native
import publication_guard as guard
import release_naming as naming
import tagger_attributes
import tagger_adapter
import test_publication_native as fixtures


@unittest.skipUnless((Path(fixtures.fixtures.TOOL_ROOT)/'lib/archive_backend.py').is_file(),
                     'offline native archive verifier required')
class RenameTests(unittest.TestCase):
    call = fixtures.AdmissionTests.call
    bootstrap = fixtures.AdmissionTests.bootstrap
    prepare = fixtures.AdmissionTests.prepare
    registered = fixtures.AdmissionTests.registered

    def setUp(self):
        fixtures.AdmissionTests.setUp(self)
        self.mylar.__path__ = [str(Path(__file__).parent)]
        aliases = {'mylar.publication_transaction':transaction,'mylar.publication_rename':owned,
                   'mylar.publication_native':native,'mylar.publication_guard':guard,
                   'mylar.release_naming':naming,'mylar.tagger_adapter':tagger_adapter,
                   'mylar.tagger_attributes':tagger_attributes}
        context=patch.dict(sys.modules,aliases);context.start();self.addCleanup(context.stop)
        for name,value in aliases.items():setattr(self.mylar,name.split('.')[-1],value)
        actual=guard.observe_owners
        def observe(*args,**kwargs):
            kwargs.setdefault('tool_root',fixtures.fixtures.TOOL_ROOT)
            return actual(*args,**kwargs)
        context=patch.object(guard,'observe_owners',side_effect=observe);context.start();self.addCleanup(context.stop)
        @contextmanager
        def operation():
            with self.writer.hold(allow_release_pending=True):
                self.runtime.admission(self.writer)
                yield self.writer
        self.runtime.operation=operation
        original_admission=self.runtime.admission
        def admitted(writer):
            original_admission(writer)
            return guard.registry_snapshot(self.store.path,writer.root/'publication-v1.json')[0]
        self.runtime.admission=admitted
        with self.connection() as db:
            db.execute('ALTER TABLE issues ADD COLUMN ComicSize INTEGER')
            db.execute('ALTER TABLE issues ADD COLUMN ComicName TEXT')
            db.execute('ALTER TABLE annuals ADD COLUMN ComicName TEXT')
        self.bootstrap()
        self.request=dict(version=1,source=str(self.source),target='Publication.001.(2020).cbz',
                          sha256=guard.file_hash(self.source)[1],issueid=self.owner['issueid'],
                          comicid=self.owner['parentcomicid'])
        self.target=self.source.with_name(self.request['target'])
        self.info=dict(self.request,table='issues',status='Downloaded',year='2020')
        def select(sql,args):
            with self.connection() as db:return [dict(row) for row in db.execute(sql,args)]
        def action(sql,args):
            with self.connection() as db:return db.execute(sql,args)
        from types import SimpleNamespace
        self.adapter=SimpleNamespace(select=select,action=action)
        for name,values in (('services',dict(return_value=(self.adapter,self.store))),
                            ('proposal',dict(return_value=self.info)),
                            ('parsed',dict(return_value=({'IssueYear':'2020'},'Print')))):
            context=patch.object(naming,name,**values);context.start();self.addCleanup(context.stop)
            if name=='proposal':self.proposal_patch=context

    @contextmanager
    def connection(self):
        import sqlite3
        db=sqlite3.connect(self.root/'mylar.db');db.row_factory=sqlite3.Row
        try:
            yield db
            db.commit()
        finally:db.close()

    def job(self):
        stamp,attributes=naming.stamp(self.source)
        return dict(request=self.request,key=naming.key(self.request),stamp=stamp,attributes=attributes,
                    phase='prepared',table='issues',status='Downloaded',year='2020')

    def test_unknown_payload_positive_rename_preserves_exact_bytes_and_owner(self):
        checksum=self.request['sha256'];inode=self.source.stat().st_ino
        result=naming.rename(self.request)
        self.assertEqual(result['phase'],'committed');self.assertFalse(self.source.exists())
        self.assertEqual(guard.file_hash(self.target)[1],checksum);self.assertEqual(self.target.stat().st_ino,inode)
        self.assertFalse(self.writer.fenced(release=True));self.assertFalse(owned.current())
        self.assertFalse((self.writer.root/transaction.NAME).exists())
        self.assertEqual(naming.rename(self.request)['key'],result['key'])
        self.assertEqual(naming.status(result['key'])['phase'],'committed')

    def test_actual_proposal_metadata_and_finish_share_current_owner_and_payload(self):
        import zipfile
        import tagger_archive,tagger_metadata
        self.mylar.tagger_archive=tagger_archive;self.mylar.tagger_metadata=tagger_metadata
        with self.connection() as db:
            for field in ('ComicName','ComicYear','ComicVersion','Type'):
                db.execute('ALTER TABLE comics ADD COLUMN '+field+' TEXT')
            for field in ('Issue_Number','IssueDate'):
                db.execute('ALTER TABLE issues ADD COLUMN '+field+' TEXT')
            db.execute("UPDATE comics SET ComicName='Publication',ComicYear='2020',Type='Print'")
            db.execute("UPDATE issues SET Issue_Number='1',IssueDate='2020-01-01'")
        with zipfile.ZipFile(self.source) as archive:
            members={name:archive.read(name) for name in archive.namelist() if name!='ComicInfo.xml'}
        with zipfile.ZipFile(self.source,'w') as archive:
            for name,value in members.items():archive.writestr(name,value)
            archive.writestr('ComicInfo.xml','<ComicInfo><Series>Publication</Series><Number>1</Number><Year>2020</Year><Volume>2020</Volume></ComicInfo>')
        self.request['sha256']=guard.file_hash(self.source)[1]
        self.proposal_patch.stop()
        proposal=naming.get(str(self.source))
        self.assertEqual((proposal['issueid'],proposal['comicid'],proposal['series'],proposal['number']),('123','456','Publication','1'))
        result=naming.rename(self.request)
        self.assertEqual(result['phase'],'committed');self.assertEqual(guard.file_hash(self.target)[1],self.request['sha256'])

    def test_registered_allowed_owner_positive_rename_preserves_correction_history(self):
        prepared=self.prepare(self.call('status')['census']);self.call('register',token=prepared['token'])
        before=self.call('status')['census'];naming.rename(self.request)
        self.assertEqual(self.call('status')['census'],before)
        self.assertEqual(naming.rename(self.request)['phase'],'committed')

    def test_registered_rejected_owner_never_prepares_or_retires_its_source(self):
        import shutil
        prepared=self.prepare(self.call('status')['census']);self.call('register',token=prepared['token'])
        wrong=self.library/'rejected.cbz';shutil.copyfile(self.source,wrong)
        with self.connection() as db:
            db.execute('INSERT INTO comics(ComicID,ComicLocation) VALUES (?,?)',('888',str(self.library)))
            db.execute('INSERT INTO issues(IssueID,ComicID,Location,Status) VALUES (?,?,?,?)',('999','888',wrong.name,'Downloaded'))
        request=dict(self.request,source=str(wrong),issueid='999',comicid='888')
        self.info.update(request)
        before=guard.file_hash(self.source)[1]
        with self.assertRaises(native.Review):naming.rename(request)
        self.assertTrue(wrong.exists());self.assertEqual(guard.file_hash(self.source)[1],before)
        self.assertFalse((self.writer.root/transaction.NAME).exists());self.assertFalse(self.writer.fenced(release=True))

    def test_crash_after_link_retains_both_exact_paths_and_original_phase(self):
        actual=os.link
        def interrupted(*args,**kwargs):
            actual(*args,**kwargs);raise OSError('interrupted link acknowledgement')
        with patch.object(naming.os,'link',side_effect=interrupted),self.assertRaises(native.Review):
            naming.rename(self.request)
        self.assertTrue(self.source.exists());self.assertTrue(self.target.exists())
        self.assertEqual(self.source.stat().st_ino,self.target.stat().st_ino)
        self.assertEqual(self.store.get('release_name',naming.key(self.request))['phase'],'prepared')
        self.assertTrue(self.writer.fenced(release=True))

    def test_crash_after_original_retirement_keeps_target_and_exact_hold(self):
        actual=Path.unlink
        def interrupted(path,*args,**kwargs):
            actual(path,*args,**kwargs)
            if path==self.source:raise OSError('interrupted source retirement')
        with patch.object(Path,'unlink',interrupted),self.assertRaises(native.Review):naming.rename(self.request)
        self.assertFalse(self.source.exists());self.assertTrue(self.target.exists())
        self.assertEqual(self.store.get('release_name',naming.key(self.request))['phase'],'linked')
        self.assertTrue(self.writer.fenced(release=True));self.assertTrue((self.writer.root/transaction.NAME).exists())

    def test_rejected_final_parser_preserves_source_and_closes_only_its_owned_fence(self):
        with (patch.object(naming,'parsed',side_effect=ValueError('parser rejects final title')),
              self.assertRaises(ValueError)):
            naming.rename(self.request)
        self.assertTrue(self.source.exists());self.assertFalse(self.target.exists())
        self.assertEqual(self.store.get('release_name',naming.key(self.request))['phase'],'rejected')
        self.assertFalse(self.writer.fenced(release=True));self.assertFalse((self.writer.root/transaction.NAME).exists())

    def test_owner_drift_after_link_retains_both_paths_before_original_unlink(self):
        actual=os.link
        def drift(*args,**kwargs):
            actual(*args,**kwargs)
            with self.connection() as db:db.execute('UPDATE issues SET Status=?',('Wanted',))
        with patch.object(naming.os,'link',side_effect=drift),self.assertRaises(native.Review):naming.rename(self.request)
        self.assertTrue(self.source.exists());self.assertTrue(self.target.exists())
        self.assertTrue(self.writer.fenced(release=True))

    def test_changed_terminal_archive_is_held_without_clearing_history(self):
        result=naming.rename(self.request)
        witness=self.writer.root/'release-completed-v1'/(result['key']+'.json');before=witness.read_bytes()
        self.target.write_bytes(b'changed archive')
        with self.assertRaises(native.Review):naming.status(result['key'])
        self.assertEqual(witness.read_bytes(),before)

    def test_wrong_current_owner_never_prepares_or_changes_media(self):
        with self.connection() as db:db.execute('UPDATE issues SET Status=?',('Wanted',))
        with self.assertRaises(native.Review):naming.rename(self.request)
        self.assertTrue(self.source.exists());self.assertFalse(self.target.exists())
        self.assertFalse(self.writer.fenced(release=True));self.assertFalse((self.writer.root/transaction.NAME).exists())

    def test_changed_payload_is_held_before_any_link(self):
        self.source.write_bytes(b'foreign invalid bytes')
        with self.assertRaises(native.Review):naming.rename(self.request)
        self.assertFalse(self.target.exists());self.assertFalse(self.writer.fenced(release=True))

    def test_catalog_update_failure_retains_exact_owned_hold_without_automatic_replay(self):
        with patch.object(self.adapter,'action',return_value=None),self.assertRaises(native.Review):
            naming.rename(self.request)
        self.assertFalse(self.source.exists());self.assertTrue(self.target.exists())
        marker=self.writer.root/transaction.NAME;before=marker.read_bytes()
        self.assertTrue(self.writer.fenced(release=True))
        with self.writer.hold(allow_release_pending=True),self.assertRaises(native.Review):naming.recover(self.writer)
        self.assertEqual(marker.read_bytes(),before)

    def test_serialized_capability_cannot_borrow_its_fence(self):
        with self.writer.hold(allow_release_pending=True):
            job=self.job();capability=owned.Rename(self.writer,job);job['publication_binding']=capability.binding
            with capability.owned():
                with self.assertRaises(guard.Unavailable):transaction.admission(json.loads(json.dumps(capability.value)),self.writer)
                capability.checkpoint(job)
        self.assertTrue(self.source.exists());self.assertTrue(self.writer.fenced(release=True))

    def test_fence_replacement_and_lost_marker_leave_source_retained(self):
        with self.writer.hold(allow_release_pending=True):
            job=self.job();capability=owned.Rename(self.writer,job);job['publication_binding']=capability.binding
            with capability.owned():
                self.writer.release_pending.rename(self.writer.root/'old-release-fence')
                self.writer.mark_release_pending()
                with self.assertRaises(native.Review):capability.checkpoint(job)
        self.assertTrue(self.source.exists());self.assertFalse(self.target.exists())

    def test_request_or_retained_intent_drift_cannot_authorize_a_checkpoint(self):
        with self.writer.hold(allow_release_pending=True):
            job=self.job();capability=owned.Rename(self.writer,job);job['publication_binding']=capability.binding
            with capability.owned():
                changed=dict(job,request=dict(job['request'],target='foreign.cbz'))
                with self.assertRaises(native.Review):capability.checkpoint(changed)
                marker=self.writer.root/transaction.NAME;marker.write_text('{}')
                with self.assertRaises(native.Review):capability.checkpoint(job)
        self.assertTrue(self.source.exists())

    def test_foreign_terminal_witness_cannot_confirm_or_remove_anything(self):
        result=naming.rename(self.request)
        witness=self.writer.root/'release-completed-v1'/(result['key']+'.json')
        before=self.target.read_bytes();witness.write_text('{}')
        with self.assertRaises(native.Review):naming.rename(self.request)
        self.assertEqual(self.target.read_bytes(),before)

    def test_terminal_clear_interruption_preserves_hold_without_media_replay(self):
        with (patch.object(self.writer,'clear_release_pending',side_effect=OSError('interrupted clear')),
              self.assertRaises(native.Review)):
            naming.rename(self.request)
        self.assertTrue(self.target.exists());self.assertFalse(self.source.exists())
        self.assertTrue(self.writer.fenced(release=True));self.assertTrue((self.writer.root/transaction.NAME).exists())

    def test_final_intent_directory_sync_failure_restores_exclusive_hold(self):
        real=owned.sync
        def failure(path):
            if Path(path)==self.writer.root and not (self.writer.root/transaction.NAME).exists() and self.target.exists():
                raise OSError('interrupted final intent durability')
            return real(path)
        with patch.object(owned,'sync',side_effect=failure),self.assertRaises(native.Review):naming.rename(self.request)
        self.assertTrue((self.writer.root/transaction.NAME).exists())
        self.assertEqual(len(list((self.writer.root/'release-completed-v1').glob('*.json'))),1)
        with self.writer.hold(allow_release_pending=True),self.assertRaises(native.Review):native.require(self.target,issueid='123',comicid='456')
        self.assertTrue(self.target.exists());self.assertFalse(self.source.exists())

    def test_replaced_caller_archive_and_pack_facts_cannot_change_owned_job(self):
        for field,replacement in [('stamp',[]),('attributes',{'mode':0}),('pack_bindings',{'token':'foreign'})]:
            with self.subTest(field=field):
                job=self.job()
                with self.writer.hold(allow_release_pending=True):
                    capability=owned.Rename(self.writer,job);job['publication_binding']=capability.binding
                    try:
                        with capability.owned():
                            job[field]=replacement
                            with self.assertRaises(native.Review):capability.checkpoint(job)
                    finally:
                        self.writer.clear_release_pending();capability.path.unlink()
                self.assertTrue(self.source.exists());self.assertFalse(self.target.exists())

    def test_rewritten_terminal_observation_cannot_follow_same_inode_catalog_alias(self):
        result=naming.rename(self.request)
        witness_path=self.writer.root/'release-completed-v1'/(result['key']+'.json')
        witness=guard.private_json(witness_path)
        alias=self.target.with_name('Foreign.alias.cbz');os.link(self.target,alias);self.target.unlink()
        with self.connection() as db:db.execute('UPDATE issues SET Location=?',(alias.name,))
        with self.writer.hold():
            witness['observed']=guard.observe_owners(self.root/'mylar.db',self.writer,[self.owner],
                                                     [self.library])['observed']
        witness['archive']=str(alias);witness['signature']=guard.signature(alias.lstat())
        witness_path.write_text(json.dumps(witness))
        with self.assertRaises(native.Review):naming.status(result['key'])
        self.assertTrue(alias.exists());self.assertTrue(witness_path.exists())


if __name__=='__main__':unittest.main()
