"""Native diagnostic refusal uses genuine registry, catalog, Writer and archives."""
from pathlib import Path
from contextlib import contextmanager
import json
import queue
import sys
import types
import stat
import tempfile
import unittest
from unittest.mock import patch, Mock
import zipfile

import publication_archive_diagnostics as diagnostic
import publication_guard as guard
import publication_native as native
import test_publication_api as api_fixture
import test_publication_native as native_fixture


class Controls(unittest.TestCase):
    bootstrap=api_fixture.NativeProtocolTests.bootstrap
    call=api_fixture.NativeProtocolTests.call
    sql=api_fixture.fixtures.NativeObservationTests.sql

    def setUp(self):
        tool=Path(api_fixture.TOOL_ROOT)
        if not (tool/'lib/comics.py').is_file():
            temporary=tempfile.TemporaryDirectory(prefix='native-page-protocol-')
            self.addCleanup(temporary.cleanup);tool=Path(temporary.name)
            (tool/'lib').mkdir()
            (tool/'lib/comics.py').write_text('PAGE_EXTENSIONS='+repr(guard.PAGE_EXTENSIONS))
        patched=patch.object(api_fixture,'TOOL_ROOT',tool);patched.start();self.addCleanup(patched.stop)
        native_fixture.AdmissionTests.setUp(self)
        self.bootstrap()

    def malformed(self):
        with zipfile.ZipFile(self.incoming,'w') as archive:
            entry=zipfile.ZipInfo('Folder');entry.create_system=3
            entry.external_attr=((stat.S_IFDIR|0o755)<<16)|0x10
            archive.writestr(entry,b'');archive.writestr('Folder/page01.jpg',b'one')
            archive.writestr('ComicInfo.xml',b'<ComicInfo/>')

    def require(self):
        with self.writer.hold():return native.require(self.incoming,issueid='123',comicid='456')

    def test_real_inventory_refusal_is_terminal_public_diagnostic(self):
        self.malformed();before=guard.file_hash(self.incoming)
        with self.assertRaises(native.Review) as held:self.require()
        self.assertEqual(held.exception.reason,'archive-verification-refused')
        self.assertEqual(held.exception.archive_diagnostic['status'],'repair-candidate')
        self.assertEqual(guard.file_hash(self.incoming),before)
        self.assertFalse(held.exception.archive_diagnostic['publication_acceptance'])
        self.assertNotIsInstance(held.exception,Exception)

    def test_ordinary_success_never_classifies(self):
        with patch.object(diagnostic,'diagnose') as diagnose:result=self.require()
        diagnose.assert_not_called()
        self.assertEqual(result['decision'],'unknown')
        self.assertEqual(result['owner'],self.owner)

    def test_registry_failure_prevents_classifier(self):
        (self.writer.root/'publication-v1.json').unlink()
        with patch.object(diagnostic,'diagnose') as diagnose,self.assertRaises(native.Review) as held:self.require()
        diagnose.assert_not_called()
        self.assertIsNone(held.exception.archive_diagnostic)

    def test_catalog_owner_failure_after_success_never_classifies(self):
        self.sql('INSERT INTO annuals VALUES (?,?,?,?,?,?)',('123','456','456','shadow.cbz','Downloaded',0))
        with patch.object(diagnostic,'diagnose') as diagnose,self.assertRaises(native.Review) as held:self.require()
        diagnose.assert_not_called()
        self.assertIsNone(held.exception.archive_diagnostic)

    def test_inventory_io_refusal_cannot_admit_verified_diagnostic(self):
        with patch.object(guard,'inventory',side_effect=guard.Unavailable('private I/O details')),self.assertRaises(native.Review) as held:self.require()
        self.assertEqual(held.exception.archive_diagnostic['status'],'verified-no-repair')
        self.assertFalse(held.exception.archive_diagnostic['native_grant'])
        self.assertNotIn('private I/O details',str(held.exception))

    def test_candidate_failure_never_classifies(self):
        self.incoming.unlink()
        with patch.object(diagnostic,'diagnose') as diagnose,self.assertRaises(native.Review):self.require()
        diagnose.assert_not_called()

    def test_failed_diagnostic_cannot_escape_terminal_refusal(self):
        self.malformed()
        with patch.object(diagnostic,'diagnose',side_effect=ImportError('private dependency details')),self.assertRaises(native.Review) as held:
            self.require()
        self.assertIsNone(held.exception.archive_diagnostic)
        self.assertNotIn('private dependency details',str(held.exception))

    def test_actual_retained_observer_pipeline_persists_public_archive_diagnostic(self):
        import processing_guard
        import pp_monitor
        import workflow_store
        self.malformed()
        before=guard.file_hash(self.incoming)
        events=[]
        @contextmanager
        def operation():
            with self.writer.hold():yield self.writer
        self.runtime.operation=operation
        self.mylar.APILOCK=False
        self.mylar.pack_intake=types.SimpleNamespace(capture=lambda _:False)
        self.mylar.logger=Mock()
        workflow=types.SimpleNamespace(store=lambda:self.store,emit=lambda *a,**k:events.append((a,k)))
        obj=types.SimpleNamespace(queue=queue.Queue(),valreturn=[],nzb_name='retained fixture',
                                  nzb_folder=str(self.incoming),issueid='123',comicid='456',ddl=True,
                                  download_info=dict(id='7'))
        @processing_guard.run
        @pp_monitor.observe
        def process(processor):
            processing_guard.publication(processor,self.incoming,issueid='123',comicid='456')
            self.fail('terminal archive review continued processing')
        modules={'mylar.workflow':workflow,'mylar.workflow_store':workflow_store,
                 'mylar.media_writer':types.SimpleNamespace(Busy=RuntimeError)}
        self.mylar.workflow=workflow
        with patch.dict(sys.modules,modules),patch.object(native,'resume_handoff',return_value=None):process(obj)
        rows=obj.queue.get_nowait()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['archive_diagnostic']['status'],'repair-candidate')
        persisted=self.store.get('ddl_processing','7')
        self.assertEqual(persisted['phase'],'review')
        self.assertEqual(persisted['archive_diagnostic'],rows[0]['archive_diagnostic'])
        self.assertIn('[repair-candidate: zip32-one-empty-directory-missing-slash]',persisted['outcome'])
        self.assertEqual(events[-1][0][1],persisted['outcome'])
        self.assertEqual(pp_monitor._RECENT[0]['archive_diagnostic'],persisted['archive_diagnostic'])
        self.assertNotIn(str(self.incoming),json.dumps(persisted['archive_diagnostic']))
        self.assertNotIn(before[1],json.dumps(persisted['archive_diagnostic']))
        self.assertEqual(guard.file_hash(self.incoming),before)

    def test_retained_observer_rejects_forged_or_foreign_diagnostic_summary(self):
        import processing_guard
        import pp_monitor
        good=diagnostic.diagnose(self.incoming,guard,__import__('time').monotonic()+10)
        for change in ({'reason':'/private/archive.cbz'},{'status':'private-label'},
                       {'native_grant':True},{'source':'/private/archive.cbz'}, {'version':True}):
            value=dict(good,**change)
            obj=types.SimpleNamespace(valreturn=[])
            processing_guard.retained(native.Review('archive-verification-refused',archive_diagnostic=value),obj)
            self.assertNotIn('archive_diagnostic',obj.valreturn[0])
            self.assertEqual(pp_monitor.archive_review(obj.valreturn),(None,None))
        obj=types.SimpleNamespace(valreturn=[])
        processing_guard.retained(native.Review('verified-correction',archive_diagnostic=good),obj)
        self.assertNotIn('archive_diagnostic',obj.valreturn[0])

if __name__=='__main__':unittest.main()
