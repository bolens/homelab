"""Genuine worker source/registry controls for diagnostic-only inventory refusal."""
import stat
import unittest
from unittest.mock import patch
import zipfile

import publication_archive_diagnostics as diagnostic
import publication_evidence as evidence
from publication_guard import ArchiveDiagnosticUnavailable, Unavailable
from test_publication_guard import AuthorityFixture


class Controls(AuthorityFixture,unittest.TestCase):
    def malformed(self):
        with zipfile.ZipFile(self.candidate,'w') as archive:
            entry=zipfile.ZipInfo('Folder');entry.create_system=3
            entry.external_attr=((stat.S_IFDIR|0o755)<<16)|0x10
            archive.writestr(entry,b'');archive.writestr('Folder/page01.jpg',b'one')
            archive.writestr('ComicInfo.xml',b'<ComicInfo/>')

    def test_real_inventory_refusal_retains_diagnostic_and_terminal_hold(self):
        self.malformed();before=evidence.file_hash(self.candidate)
        with self.writer.hold(),self.assertRaises(ArchiveDiagnosticUnavailable) as held:
            self.authority.check(self.candidate,self.owner)
        self.assertEqual(held.exception.archive_diagnostic['status'],'repair-candidate')
        self.assertEqual(evidence.file_hash(self.candidate),before)
        self.assertFalse(held.exception.archive_diagnostic['publication_acceptance'])
        self.assertIsInstance(held.exception,Unavailable)

    def test_ordinary_success_does_not_classify(self):
        with patch.object(diagnostic,'diagnose') as diagnose,self.writer.hold():
            result=self.authority.check(self.candidate,self.owner)
        diagnose.assert_not_called()
        self.assertEqual(result['authority']['decision'],'allowed')

    def test_catalog_owner_failure_does_not_classify(self):
        self.sql('INSERT INTO annuals VALUES (?,?,?,?,?,?)',('123','456','456','correct.cbz','Downloaded',0))
        with patch.object(diagnostic,'diagnose') as diagnose,self.writer.hold(),self.assertRaises(Unavailable):
            self.authority.import_check(self.candidate,{'issueid':'123','comicid':'456'})
        diagnose.assert_not_called()

    def test_correction_owner_rejection_does_not_classify(self):
        with patch.object(diagnostic,'diagnose') as diagnose,self.writer.hold(),self.assertRaises(Unavailable):
            self.authority.check(self.candidate,self.rejected)
        diagnose.assert_not_called()

    def test_registry_failure_prevents_classifier(self):
        self.marker.unlink()
        with patch.object(diagnostic,'diagnose') as diagnose,self.writer.hold(),self.assertRaises(Unavailable):
            self.authority.check(self.candidate,self.owner)
        diagnose.assert_not_called()

    def test_inventory_io_failure_never_admits_verified_diagnostic(self):
        with patch.object(evidence,'inventory',side_effect=evidence.Unavailable('private I/O details')), self.writer.hold(),self.assertRaises(ArchiveDiagnosticUnavailable) as held:
            self.authority.check(self.candidate,self.owner)
        self.assertEqual(held.exception.archive_diagnostic['status'],'verified-no-repair')
        self.assertNotIn('private I/O details',str(held.exception))
        self.assertFalse(held.exception.archive_diagnostic['native_grant'])

    def test_failed_diagnostic_cannot_escape_terminal_refusal(self):
        self.malformed()
        with patch.object(diagnostic,'diagnose',side_effect=ImportError('private dependency details')),self.writer.hold(),self.assertRaises(ArchiveDiagnosticUnavailable) as held:
            self.authority.check(self.candidate,self.owner)
        self.assertIsNone(held.exception.archive_diagnostic)
        self.assertNotIn('private dependency details',str(held.exception))

    def test_real_worker_refusal_message_is_operator_observable_without_private_evidence(self):
        self.malformed()
        before=evidence.file_hash(self.candidate)
        with self.writer.hold(),self.assertRaises(ArchiveDiagnosticUnavailable) as held:
            self.authority.check(self.candidate,self.owner)
        text=str(held.exception)
        self.assertIn('[repair-candidate: zip32-one-empty-directory-missing-slash]',text)
        self.assertIn('source retained for review',text)
        self.assertNotIn(str(self.candidate),text)
        self.assertNotIn(before[1],text)
        self.assertEqual(evidence.file_hash(self.candidate),before)

    def test_worker_formatter_rejects_forged_and_extra_summary_fields(self):
        good=diagnostic.diagnose(self.candidate,evidence,__import__('time').monotonic()+10)
        for change in ({'reason':'/private/archive.cbz'},{'source':'/private/archive.cbz'},
                       {'native_grant':True},{'version':True}):
            held=ArchiveDiagnosticUnavailable(dict(good,**change))
            self.assertEqual(str(held),'Current worker publication evidence unavailable')
            self.assertIsNone(held.archive_diagnostic)

if __name__=='__main__':unittest.main()
