"""Identity ambiguity, source preservation, and at-most-once submission fixtures."""
import json
from pathlib import Path
import sqlite3
from contextlib import closing
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

from import_match import match
from import_recovery import submit, previous_attempt
from normalize import digest


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / 'mylar.db'
        with closing(sqlite3.connect(self.db)) as db, db:
            db.executescript('''CREATE TABLE comics (ComicID TEXT,ComicName TEXT,ComicYear TEXT);
            CREATE TABLE issues (IssueID TEXT,ComicID TEXT,Status TEXT,Issue_Number TEXT,IssueDate TEXT,Location TEXT);
            INSERT INTO comics VALUES ('10','Test Comic','2017');
            INSERT INTO issues VALUES ('100','10','Snatched','1','2017-05-01','');''')
        self.source = self.root / 'Test Comic 001 (2017).cbz'
        self.archive()
        self.cache = self.root / 'cache'; self.cache.mkdir()
        self.state = self.root / 'state'; self.state.mkdir()
        self.m = SimpleNamespace(settings={'auto_import':True,'ddl_cache':str(self.cache),
                                         'mylar_ddl_cache':'/config/mylar/cache'},
                                 roots=[self.root, self.cache], state=self.state,
                                 worker=SimpleNamespace(config={'mylar':{'config_dir':str(self.root)}}),
                                 idle=Mock(return_value=True), mylar=Mock(return_value='accepted'))

    def archive(self, metadata=None):
        with zipfile.ZipFile(self.source,'w') as z:
            z.writestr('001.png',b'fixture page')
            if metadata:z.writestr('ComicInfo.xml',metadata)

    def test_native_force_process_plain_text_acknowledgement(self):
        from maintenance import Maintenance
        (self.root/'config.ini').write_text('[API]\napi_key=fixture\n')
        worker=SimpleNamespace(config={'mylar':{'url':'http://fixture','config_dir':str(self.root)}})
        obj=SimpleNamespace(worker=worker)
        with patch('maintenance.request',return_value='Successfully submitted request for post-processing for Comic.cbz') as request:
            self.assertEqual(Maintenance.mylar(obj,'forceProcess',nzb_name='Comic.cbz'),{'submitted':True})
            self.assertTrue(request.call_args.kwargs['text'])
        with patch('maintenance.request',return_value='Unrecognized response'):
            with self.assertRaises(ValueError):Maintenance.mylar(obj,'forceProcess',nzb_name='Comic.cbz')

    def test_exact_filename_and_issue_marker(self):
        self.assertEqual(match(self.source,self.db),{'issueid':'100','comicid':'10'})
        renamed=self.root/'Unhelpful [__100__].cbz';self.source.rename(renamed)
        self.assertEqual(match(renamed,self.db)['issueid'],'100')

    def test_metadata_publication_year_and_number(self):
        self.source=self.root/'opaque.cbz'
        self.archive('<ComicInfo><Series>Test Comic</Series><Number>01</Number><Year>2017</Year></ComicInfo>')
        self.assertEqual(match(self.source,self.db)['issueid'],'100')

    def test_metadata_identifier_and_conflicts(self):
        self.source=self.root/'opaque.cbz'
        self.archive('<ComicInfo><Web>https://comicvine.gamespot.com/a/4000-100/</Web></ComicInfo>')
        self.assertEqual(match(self.source,self.db)['issueid'],'100')
        self.archive('<ComicInfo><Web>https://comicvine.gamespot.com/a/4000-100/</Web><Number>2</Number></ComicInfo>')
        self.assertIsNone(match(self.source,self.db))

    def test_ambiguous_downloaded_unknown_and_wrong_year_are_retained(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("INSERT INTO issues VALUES ('101','10','Downloaded','1','2017-06-01','')")
        self.assertIsNone(match(self.source,self.db))
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("DELETE FROM issues WHERE IssueID='101'")
            db.execute("UPDATE issues SET Status='Downloaded'")
        self.assertIsNone(match(self.source,self.db))
        renamed=self.root/'Test Comic 001 (2018) [__999__].cbz';self.source.rename(renamed)
        self.assertIsNone(match(renamed,self.db))

    def test_malformed_oversized_conflicting_metadata_and_fuzzy_names_rejected(self):
        for text in ['<broken', '<!DOCTYPE a [<!ENTITY x "x">]><ComicInfo/>',
                     '<ComicInfo><Series>Wrong Comic</Series><Number>1</Number><Year>2017</Year></ComicInfo>',
                     '<ComicInfo>'+('x'*262144)+'</ComicInfo>']:
            self.archive(text);self.assertIsNone(match(self.source,self.db))
        self.source=self.root/'Test Comix 001 (2017).cbz';self.archive()
        self.assertIsNone(match(self.source,self.db))

    def test_copy_preserved_and_only_one_submission_after_restart(self):
        original=digest(self.source);identity={'issueid':'100','comicid':'10'}
        self.assertEqual(submit(self.m,self.source,identity),'import_queued')
        self.assertEqual(digest(self.source),original)
        staged=next(self.cache.glob('.mylar-recovery-*/*.cbz'))
        self.assertEqual(digest(staged),original)
        self.m.import_submitted=False
        self.assertEqual(submit(self.m,self.source,identity),'import_queued')
        self.m.mylar.assert_called_once()
        self.assertEqual(self.m.mylar.call_args.kwargs['ddl'],'True')
        self.assertNotIn('workflow_command', self.m.mylar.call_args.kwargs)
        self.assertEqual(self.m.mylar.call_args.kwargs['nzb_folder'],'/config/mylar/cache/'+staged.parent.name)

    def test_lost_response_never_repeated(self):
        self.m.mylar.side_effect=TimeoutError
        self.assertEqual(submit(self.m,self.source,{'issueid':'100','comicid':'10'}),'import_review')
        self.m.import_submitted=False
        self.assertEqual(submit(self.m,self.source,{'issueid':'100','comicid':'10'}),'import_review')
        self.m.mylar.assert_called_once()

    def test_busy_disabled_unsupported_and_symlink(self):
        self.m.idle.return_value=False
        self.assertEqual(submit(self.m,self.source,{}),'ready')
        self.m.settings['auto_import']=False
        self.assertEqual(submit(self.m,self.source,{}),'ready')
        self.m.settings['auto_import']=True
        renamed=self.source.with_suffix('.cb7');self.source.rename(renamed)
        self.assertEqual(submit(self.m,renamed,{}),'import_unsupported')
        link=self.root/'linked.cbz';link.symlink_to(renamed)
        with self.assertRaises(ValueError):submit(self.m,link,{})
        self.m.mylar.assert_not_called()

    def test_completed_attempt_is_not_relabelled_unmatched(self):
        submit(self.m,self.source,{'issueid':'100','comicid':'10'})
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("UPDATE issues SET Status='Downloaded',Location='Test Comic 001.cbz'")
        self.assertIsNone(match(self.source,self.db))
        self.assertEqual(previous_attempt(self.m,self.source)[0],'import_cleanup')

    def test_second_filename_for_same_issue_requires_review(self):
        submit(self.m,self.source,{'issueid':'100','comicid':'10'})
        other=self.root/'Other.cbz';other.write_bytes(self.source.read_bytes())
        self.m.import_submitted=False
        self.assertEqual(submit(self.m,other,{'issueid':'100','comicid':'10'}),'import_review')
        self.m.mylar.assert_called_once()

    def test_stale_attempt_requires_review(self):
        submit(self.m,self.source,{'issueid':'100','comicid':'10'})
        receipt=next((self.state/'imports').glob('*.json'))
        row=json.loads(receipt.read_text());row['submitted_at']=0;receipt.write_text(json.dumps(row))
        self.assertEqual(submit(self.m,self.source,{}),'import_review')
        self.m.mylar.assert_called_once()


if __name__=='__main__':unittest.main()
