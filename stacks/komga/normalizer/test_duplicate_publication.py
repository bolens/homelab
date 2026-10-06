"""Actual local catalog/authority controls for cleanup and lost acknowledgement."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from maintenance import Maintenance
from normalize import digest
from publication_guard import Unavailable
from test_publication_guard import AuthorityFixture


class DuplicatePublicationTest(AuthorityFixture,unittest.TestCase):
    def setUp(self):
        AuthorityFixture.setUp(self)
        self.downloads=self.root/'downloads';self.downloads.mkdir()
        state=self.root/'state';state.mkdir()
        self.download=self.downloads/'copy.cbz';shutil.copyfile(self.candidate,self.download)
        config=dict(writer_state=str(self.writer.root),maintenance={'completed':str(self.downloads)})
        self.m=Maintenance(SimpleNamespace(state=state,roots=[self.library],config=config))
        # Archive preservation is covered by the converter-backed owning suite;
        # publication inventory here independently reads the genuine ZIP bytes.
        self.m.info=Mock(return_value=dict(page_count=1,pages=['page'],other_files=[]))
        self.m.idle=Mock(return_value=True)

    @contextmanager
    def owned(self):
        with self.writer.hold(),patch('publication_guard.current',return_value=self.authority):
            yield

    def remove(self):
        with self.owned():return self.m.remove_duplicate(self.download,self.source)

    def receipt(self):
        return next(self.m.receipts.glob('*.json'))

    def interrupted(self):
        actual=self.m.save_duplicate
        def stop(path,row,previous=None):
            if row['phase']=='removed':raise OSError('lost acknowledgement')
            actual(path,row,previous)
        with patch.object(self.m,'save_duplicate',side_effect=stop),self.assertRaises(OSError):self.remove()
        path=self.receipt();return path,json.loads(path.read_text())

    def reconcile(self,path,row):
        with self.owned():return self.m.reconcile_retained_duplicate(path,row)

    def test_allowed_repeat_has_current_owner_and_retained_exact_original(self):
        before=digest(self.download);self.assertTrue(self.remove())
        row=json.loads(self.receipt().read_text())
        self.assertEqual(row['phase'],'removed');self.assertEqual(row['publication']['match'],dict(issueid='123',comicid='456'))
        self.assertEqual(digest(Path(row['retained_original'])),before)
        self.assertFalse(self.download.exists());self.assertTrue(self.source.exists())
        self.assertEqual(self.receipt().stat().st_mode & 0o777,0o600)

    def test_unknown_eligible_repeat_also_requires_actual_catalog_owner(self):
        self.seed(empty=True);self.assertTrue(self.remove())

    def test_same_pages_without_exact_current_catalog_target_are_retained(self):
        self.sql('UPDATE issues SET Location=?',('elsewhere.cbz',))
        with self.assertRaises(Unavailable):self.remove()
        self.assertTrue(self.download.exists());self.assertEqual(list(self.m.receipts.glob('*')),[])

    def test_unknown_payload_with_wanted_target_is_not_cleanup_authority(self):
        self.seed(empty=True);self.sql('UPDATE issues SET Status=?',('Wanted',))
        with self.assertRaises(Unavailable):self.remove()
        self.assertTrue(self.download.exists())

    def test_annual_shadow_cannot_authorize_cleanup(self):
        self.sql('INSERT INTO annuals VALUES (?,?,?,?,?,?)',('123','456','456',None,'Wanted',0))
        with self.assertRaises(Unavailable):self.remove()
        self.assertTrue(self.download.exists())

    def test_physical_alias_of_correct_original_is_never_deleted(self):
        self.download.unlink();os.link(self.source,self.download)
        with self.assertRaises(Unavailable):self.remove()
        self.assertTrue(self.download.exists());self.assertTrue(self.source.exists())

    def test_other_unregistered_catalog_original_physical_alias_is_never_deleted(self):
        self.seed(empty=True)
        other=self.library/'other-owner.cbz';shutil.copyfile(self.source,other)
        self.sql('INSERT INTO issues VALUES (?,?,?,?)',('124','456',other.name,'Downloaded'))
        self.download.unlink();os.link(other,self.download)
        before=other.stat().st_nlink
        with self.assertRaises(Unavailable):self.remove()
        self.assertTrue(self.download.exists());self.assertEqual(other.stat().st_nlink,before)

    def test_source_payload_change_even_without_metadata_change_is_held(self):
        self.download.write_bytes(self.archive('changed.cbz',[('01.jpg',b'changed')]).read_bytes())
        with self.assertRaises(Unavailable):self.remove()
        self.assertTrue(self.download.exists())

    def test_catalog_drift_at_idle_keeps_prepared_receipt_and_source(self):
        def drift():
            self.sql('UPDATE issues SET Status=?',('Wanted',));return True
        self.m.idle.side_effect=drift
        with self.assertRaises(Unavailable):self.remove()
        self.assertTrue(self.download.exists());self.assertEqual(json.loads(self.receipt().read_text())['phase'],'verified')

    def test_source_drift_at_idle_keeps_prepared_receipt(self):
        self.m.idle.side_effect=lambda:(self.download.write_bytes(b'changed') or True)
        with self.assertRaises(RuntimeError):self.remove()
        self.assertEqual(json.loads(self.receipt().read_text())['phase'],'verified')
        self.assertTrue(self.download.exists())

    def test_census_change_at_idle_cannot_refresh_existing_proof(self):
        self.m.idle.side_effect=lambda:(self.seed(empty=True) or True)
        with self.assertRaises(Unavailable):self.remove()
        before=self.receipt().read_bytes();self.m.idle.return_value=True;self.m.idle.side_effect=None
        with self.assertRaises(RuntimeError):self.remove()
        self.assertEqual(self.receipt().read_bytes(),before);self.assertTrue(self.download.exists())

    def test_receipt_replaced_before_unlink_is_preserved_without_deletion(self):
        def drift():self.receipt().write_text('{"foreign":true}');return True
        self.m.idle.side_effect=drift
        with self.assertRaises(Unavailable):self.remove()
        self.assertTrue(self.download.exists());self.assertEqual(json.loads(self.receipt().read_text()),dict(foreign=True))

    def test_lost_unlink_acknowledgement_reconciles_without_repeating_deletion(self):
        path,row=self.interrupted();before=digest(self.source)
        self.assertFalse(self.download.exists());self.assertTrue(self.reconcile(path,row))
        self.assertEqual(json.loads(path.read_text())['phase'],'removed');self.assertEqual(digest(self.source),before)

    def test_lost_acknowledgement_after_owner_change_is_held(self):
        path,row=self.interrupted();before=path.read_bytes()
        self.sql('UPDATE issues SET Status=?',('Wanted',))
        with self.assertRaises(Unavailable):self.reconcile(path,row)
        self.assertEqual(path.read_bytes(),before)

    def test_lost_acknowledgement_after_census_change_is_held(self):
        path,row=self.interrupted();before=path.read_bytes();self.seed(empty=True)
        with self.assertRaises(Unavailable):self.reconcile(path,row)
        self.assertEqual(path.read_bytes(),before)

    def test_changed_retained_original_never_marks_removed(self):
        path,row=self.interrupted();before=path.read_bytes();Path(row['retained_original']).write_bytes(b'changed')
        self.assertFalse(self.reconcile(path,row));self.assertEqual(path.read_bytes(),before)

    def test_legacy_receipt_is_not_promoted_to_owned_cleanup(self):
        key=hashlib.sha256(os.fsencode(self.download)+digest(self.download).encode()).hexdigest()
        path=self.m.receipts/(key+'.json');path.write_text('{}');path.chmod(0o600)
        before=path.read_bytes()
        with self.assertRaises(Unavailable):self.remove()
        self.assertTrue(self.download.exists());self.assertEqual(path.read_bytes(),before)


    def test_completed_cleanup_preserves_configured_download_root(self):
        self.assertTrue(self.remove());self.assertTrue(self.downloads.is_dir())

    def test_corrupt_archive_and_legacy_quarantine_are_held_before_effects(self):
        self.download.write_bytes(b'corrupt')
        from normalize import identity
        with self.owned(),self.assertRaises(Unavailable):
            self.m.quarantine(self.download,identity(self.download))
        with self.owned(),self.assertRaises(Unavailable):
            self.m.finish_quarantine(self.m.receipts/'legacy.json',{})
        self.assertTrue(self.download.exists());self.assertFalse((self.m.state/'quarantine').exists())

    def test_nonprivate_retained_original_cannot_acknowledge_cleanup(self):
        path,row=self.interrupted();before=path.read_bytes();Path(row['retained_original']).chmod(0o644)
        with self.assertRaises(Unavailable):self.reconcile(path,row)
        self.assertEqual(path.read_bytes(),before)

    def test_linked_retained_original_cannot_acknowledge_cleanup(self):
        path,row=self.interrupted();before=path.read_bytes()
        os.link(row['retained_original'],self.root/'retained-alias')
        with self.assertRaises(Unavailable):self.reconcile(path,row)
        self.assertEqual(path.read_bytes(),before)


    def test_maintenance_reader_snapshot_is_immutable_and_read_under_owned_authority(self):
        self.m.worker.reader=SimpleNamespace(books=Mock(return_value={str(self.source):
            {'id':'book','media':{'status':'READY'},'private_extra':'discard'}}))
        self.m.mylar=Mock(return_value={})
        self.m.prepare()
        self.m.worker.reader.books.assert_called_once()
        with self.owned():
            first=self.m.reader_books();first[str(self.source)]['media']['status']='changed'
            self.assertEqual(self.m.reader_books()[str(self.source)]['media']['status'],'READY')
            self.assertNotIn('private_extra',self.m.reader_books()[str(self.source)])
        self.m.worker.reader.books.assert_called_once()

    def test_missing_reader_snapshot_refuses_network_inside_writer(self):
        self.m.worker.reader=SimpleNamespace(books=Mock())
        with self.owned(),self.assertRaises(Unavailable):self.m.reader_books()
        self.m.worker.reader.books.assert_not_called()


class UncatalogedPublicationTest(AuthorityFixture,unittest.TestCase):
    def setUp(self):
        AuthorityFixture.setUp(self);self.seed(empty=True)

    def test_absent_catalog_and_correction_claim_has_bounded_current_proof(self):
        with self.writer.hold():
            proof=self.authority.uncataloged_check(self.candidate)
        self.assertEqual(proof['inventory']['source_sha256'],digest(self.candidate))
        self.assertIn('catalog_signature',proof)

    def test_catalog_original_and_physical_alias_are_held_without_registration(self):
        alias=self.library/'physical-alias.cbz';os.link(self.source,alias)
        for path in (self.source,alias):
            with self.writer.hold(),self.assertRaises(Unavailable):self.authority.uncataloged_check(path)

    def test_deleted_annual_claim_also_prevents_uncataloged_relocation(self):
        self.sql('INSERT INTO annuals VALUES (?,?,?,?,?,?)',('999','456','456',self.candidate.name,'Wanted',1))
        with self.writer.hold(),self.assertRaises(Unavailable):self.authority.uncataloged_check(self.candidate)

    def test_uncataloged_read_drift_is_rejected(self):
        actual=self.authority.unowned_check;calls=0
        def drift(source):
            nonlocal calls
            calls+=1
            if calls==2:self.sql('UPDATE issues SET Location=?',(self.candidate.name,))
            return actual(source)
        with self.writer.hold(),patch.object(self.authority,'unowned_check',side_effect=drift),self.assertRaises(Unavailable):
            self.authority.uncataloged_check(self.candidate)


if __name__=='__main__':unittest.main()
