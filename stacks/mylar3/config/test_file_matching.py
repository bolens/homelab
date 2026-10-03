"""Exercise the complete native filename parser in the candidate image."""

from pathlib import Path
import sys
import tempfile
import sqlite3
import zipfile
from types import SimpleNamespace
import unittest

SOURCE = Path(sys.argv.pop(1))
sys.path[:0] = [str(SOURCE.parent), "/app/mylar3", "/app/mylar3/lib"]
import mylar
from mylar import filechecker
from unittest.mock import Mock, patch


class NativeMatchingTest(unittest.TestCase):
    def test_native_year_named_annuals_get_distinct_verified_release_ids(self):
        from mylar import file_identity
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        database = sqlite3.connect(':memory:')
        database.row_factory = sqlite3.Row
        self.addCleanup(database.close)
        database.executescript('''CREATE TABLE comics(ComicID,ComicName,ComicYear,ComicVersion,Type);
            CREATE TABLE issues(IssueID,ComicID,Issue_Number);
            CREATE TABLE annuals(IssueID,ComicID,Issue_Number,ReleaseComicName,ReleaseComicID,Deleted,IssueDate);
            INSERT INTO comics VALUES('10','Grimm Fairy Tales','2016',NULL,'Print');
            INSERT INTO annuals VALUES('100','10','1','Grimm Fairy Tales 2021 Annual','20',0,'2021-01-01'),
                ('200','10','1','Grimm Fairy Tales 2022 Annual','21',0,'2022-01-01');''')
        listing = []
        for year, issueid in [('2021','100'),('2022','200')]:
            name = 'Grimm Fairy Tales '+year+' Annual ('+year+').cbz'
            with zipfile.ZipFile(folder/name,'w') as archive:
                archive.writestr('page.jpg',b'fixture preserved')
                archive.writestr('ComicInfo.xml','<ComicInfo><Series>Grimm Fairy Tales '+year+' Annual</Series><Number>1</Number><Web>https://comicvine.gamespot.com/issue/4000-'+issueid+'/</Web></ComicInfo>')
        with patch.object(filechecker,'logger',Mock()), patch.object(mylar,'CONFIG',SimpleNamespace(IGNORE_SEARCH_WORDS=[],CUSTOM_ISSUE_EXCEPTIONS=[],ANNUALS_ON=True,FOLDER_SCAN_LOG_VERBOSE=False,ENFORCE_PERMS=False,ENABLE_TORRENTS=False,READ2FILENAME=False)):
            checker = filechecker.FileChecker(dir=str(folder),watchcomic='Grimm Fairy Tales',Publisher='Fixture',AlternateSearch='Grimm Fairy Tales 2021 Annual!!20##Grimm Fairy Tales 2022 Annual!!21',comic_type='Print')
            listing = checker.listFiles()['comiclist']
        self.assertEqual(len(listing),2)
        self.assertTrue(all(r['AnnualComicID'] is None for r in listing))
        adapter = Mock()
        adapter.select.side_effect = lambda sql,args:database.execute(sql,args).fetchall()
        series=dict(ComicID='10',ComicName='Grimm Fairy Tales',ComicYear='2016',ComicVersion=None,Type='Print')
        file_identity.validate_rescan(adapter,series,[dict(comiclist=listing)])
        self.assertEqual({r['IssueYear']:r['AnnualComicID'] for r in listing},{'2021':'20','2022':'21'})
        adapter.action.assert_not_called()
        adapter.upsert.assert_not_called()

    def test_native_duplicate_check_uses_annual_owner_and_retains_conflicts(self):
        from mylar import helpers, db
        from patch_postprocessing import duplicate_ownership
        source = (SOURCE / 'helpers.py').read_text()
        self.assertEqual(duplicate_ownership(source), source)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / 'Annual.cbz'
        path.write_bytes(b'original retained')
        database = sqlite3.connect(':memory:')
        database.row_factory = sqlite3.Row
        self.addCleanup(database.close)
        database.executescript('''CREATE TABLE issues(IssueID,ComicID,Status,Location,ComicSize);
            CREATE TABLE annuals(IssueID,ComicID,Status,Location,ComicSize,Deleted);
            CREATE TABLE comics(ComicID,ComicName,ComicLocation);
            INSERT INTO comics VALUES('10','Parent','/parent'),('20','Standalone','/standalone');
            INSERT INTO issues VALUES('100','20','Downloaded','wrong.cbz',100);
            INSERT INTO annuals VALUES('100','10','Wanted',NULL,NULL,0);''')
        adapter = Mock()
        adapter.selectone.side_effect = lambda sql, args: database.execute(sql, args)
        with patch.object(db, 'DBConnection', return_value=adapter), patch.object(helpers, 'logger', Mock()):
            self.assertEqual(helpers.duplicate_filecheck(str(path), ComicID='10', IssueID='100'), {'action': 'write'})
            self.assertEqual(helpers.duplicate_filecheck(str(path), ComicID='20', IssueID='100'), {'action': None})
            database.execute("UPDATE annuals SET Deleted=1")
            self.assertEqual(helpers.duplicate_filecheck(str(path), ComicID='10', IssueID='100'), {'action': None})
            database.execute('DELETE FROM annuals')
            database.execute("UPDATE issues SET Status='Wanted'")
            self.assertEqual(helpers.duplicate_filecheck(str(path), ComicID='20', IssueID='100'), {'action': 'write'})
        adapter.action.assert_not_called()
        adapter.upsert.assert_not_called()
        self.assertEqual(path.read_bytes(), b'original retained')

    def test_native_rescan_rejects_identity_before_any_catalog_action(self):
        from mylar import updater, db
        import inspect
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        name = 'Comic 016 (2021).cbz'
        path = folder/name
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('page.jpg', b'fixture')
            archive.writestr('ComicInfo.xml', '<ComicInfo><Series>Comic</Series><Web>https://comicvine.gamespot.com/issue/4000-100/</Web></ComicInfo>')
        database = sqlite3.connect(':memory:')
        database.row_factory = sqlite3.Row
        self.addCleanup(database.close)
        database.executescript('''CREATE TABLE comics(ComicID,ComicName,ComicYear,ComicVersion,Type);
            CREATE TABLE issues(IssueID,ComicID,Issue_Number,IssueDate);
            CREATE TABLE annuals(IssueID,ComicID,Issue_Number,ReleaseComicName,ReleaseComicID,Deleted);
            INSERT INTO comics VALUES('10','Comic','2020','v2','Print');
            INSERT INTO issues VALUES('100','10','15','2020-01-01'),('101','10','16','2021-01-01');''')
        series = dict(ComicID='10', ComicName='Comic', ComicYear='2020', ComicVersion='v2', Type='Print',
                      AlternateSearch=None, Status='Active', Corrected_Type=None, ComicPublisher='Fixture',
                      Total=2, ComicLocation=str(folder))
        adapter = Mock()
        adapter.select.side_effect = lambda sql, args: database.execute(sql, args).fetchall()
        adapter.selectone.return_value.fetchone.return_value = series
        parsed = self.parse(name, 'Comic')
        listing = dict(comiccount=1, comiclist=[dict(ComicFilename=name, ComicLocation=str(folder),
                                                   JusttheDigits=str(parsed['issue_number']), AnnualComicID=None)])
        with patch.object(db, 'DBConnection', return_value=adapter), \
                patch.object(filechecker.FileChecker, 'listFiles', return_value=listing), \
                patch.object(updater, 'logger', Mock()), \
                patch.object(mylar, 'CONFIG', SimpleNamespace(MULTIPLE_DEST_DIRS=None)):
            with self.assertRaises(ValueError):
                inspect.unwrap(updater.forceRescan)('10')
            database.execute("UPDATE issues SET Issue_Number='15' WHERE IssueID='101'")
            new_name = 'Comic 015 (2021).cbz'
            path = path.rename(folder/new_name)
            parsed = self.parse(new_name, 'Comic')
            listing['comiclist'][0].update(ComicFilename=new_name, JusttheDigits=str(parsed['issue_number']))
            with self.assertRaises(ValueError):
                inspect.unwrap(updater.forceRescan)('10')
        adapter.action.assert_not_called()
        adapter.upsert.assert_not_called()
        self.assertTrue(path.is_file())
        self.assertEqual(database.execute('SELECT IssueID,Issue_Number FROM issues ORDER BY IssueID').fetchall()[0]['Issue_Number'], '15')

    def test_rescan_identity_guard_precedes_duplicate_and_catalog_changes(self):
        source = (SOURCE / "updater.py").read_text()
        from patch_file_matching import patched
        self.assertEqual(patched("updater.py", source), source)
        start = source.index("def forceRescan(")
        end = source.find("\ndef ", start + 1)
        rescan = source[start:end if end != -1 else None]
        guard = rescan.index("file_identity.validate_rescan(myDB, rescan, fca, booktype=booktype)")
        self.assertLess(guard, rescan.index("    fcb = []"))
        self.assertLess(guard, rescan.index("d_issues.append"))

    def parse(self, name, title, kind=None, number=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        (Path(temp.name) / name).write_bytes(b"fixture")
        checker = filechecker.FileChecker(
            dir=temp.name,
            watchcomic=title,
            justparse=True,
            comic_type=kind,
            single_issue_number=number,
        )
        with (
            patch.object(filechecker, "logger", Mock()),
            patch.object(
                mylar,
                "CONFIG",
                SimpleNamespace(
                    IGNORE_SEARCH_WORDS=[], ANNUALS_ON=True, CUSTOM_ISSUE_EXCEPTIONS=[],
                    FOLDER_SCAN_LOG_VERBOSE=False,
                ),
            ),
        ):
            return checker.parseit(temp.name, name)

    def test_title_ending_in_year_survives_regular_issue_parser(self):
        value = self.parse(
            "American Vampire 1976 001 (2020).cbz", "American Vampire 1976"
        )
        self.assertEqual(value["series_name"], "American Vampire 1976")
        self.assertEqual(int(value["issue_number"]), 1)

    def test_unnumbered_numeric_title_uses_unique_catalog_identity(self):
        value = self.parse("1984 (2020).cbz", "1984", "GN", "1")
        self.assertEqual(value["series_name"], "1984")
        self.assertEqual(str(value["issue_number"]), "1")
        self.assertEqual(value["booktype"], "GN")

    def test_ordinary_title_and_issue_unchanged(self):
        value = self.parse("Batman 003 (2020).cbz", "Batman")
        self.assertEqual(value["series_name"], "Batman")
        self.assertEqual(int(value["issue_number"]), 3)


if __name__ == "__main__":
    unittest.main()
