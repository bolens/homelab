"""Single-volume recovery requires exact identity and an unambiguous main file."""

from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from file_identity import single_issue_number, single_volume_match


class FileIdentityTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.checker = SimpleNamespace(
            dir=temp.name,
            watchcomic="1984",
            AlternateSearch=None,
            comic_type="GN",
            single_issue_number="1",
        )

    def test_numeric_title_matches_catalog_number_and_preserves_extras(self):
        for name in ("1984 (2020).cbz", "1984 Preview.cbz"):
            (self.folder / name).write_bytes(b"fixture")
        self.assertEqual(
            single_volume_match(self.checker, "1984 (2020).cbz"), ("1", "1984", "GN")
        )
        self.assertIsNone(single_volume_match(self.checker, "1984 Preview.cbz"))
        self.assertEqual(len(list(self.folder.iterdir())), 2)

    def test_wrong_series_variant_ambiguity_and_symlinks_are_rejected(self):
        target = self.folder / "1984.cbz"
        target.write_bytes(b"fixture")
        variant = self.folder / "1984 cover B.cbz"
        variant.write_bytes(b"variant")
        self.assertIsNone(single_volume_match(self.checker, target.name))
        variant.unlink()
        self.checker.watchcomic = "1985"
        self.assertIsNone(single_volume_match(self.checker, target.name))
        self.checker.watchcomic = "1984"
        target.unlink()
        target.symlink_to("/etc/hosts")
        self.assertIsNone(single_volume_match(self.checker, target.name))

    def test_known_issue_number_does_not_assume_one(self):
        self.checker.watchcomic = "Comic"
        self.checker.single_issue_number = "220"
        (self.folder / "Comic 220.cbz").write_bytes(b"fixture")
        self.assertEqual(single_volume_match(self.checker, "Comic 220.cbz")[0], "220")
        self.checker.single_issue_number = "1"
        self.assertIsNone(single_volume_match(self.checker, "Comic 220.cbz"))
        self.checker.comic_type = "issue"
        self.assertIsNone(single_volume_match(self.checker, "Comic 220.cbz"))

    def test_supplemental_and_conflicting_annotations_are_not_discarded(self):
        self.checker.watchcomic = "Comic"
        for name in (
            "Comic [002].cbz",
            "Comic (Annual).cbz",
            "Comic (Variant Cover).cbz",
            "Comic (Special).cbz",
        ):
            file = self.folder / name
            file.write_bytes(b"fixture")
            self.assertIsNone(single_volume_match(self.checker, name))
            file.unlink()

    def test_annual_qualified_alias_cannot_become_regular_issue(self):
        self.checker.watchcomic = "Comic"
        self.checker.AlternateSearch = "Comic Annual!!555"
        name = "Comic Annual 001 (2020).cbz"
        (self.folder / name).write_bytes(b"fixture")
        self.assertIsNone(single_volume_match(self.checker, name))

    def test_actual_catalog_uniqueness_is_required(self):
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.row_factory = sqlite3.Row
        db.executescript(
            "CREATE TABLE issues(ComicID,Issue_Number);INSERT INTO issues VALUES('a','0'),('b','1'),('b','2');"
        )
        database = SimpleNamespace(
            select=lambda sql, args: db.execute(sql, args).fetchall()
        )
        self.assertEqual(single_issue_number(database, "a", 1), "0")
        self.assertIsNone(single_issue_number(database, "b", 1))
        self.assertIsNone(single_issue_number(database, "a", 2))
        self.assertIsNone(single_issue_number(database, "missing", 1))


class RescanIdentityTest(unittest.TestCase):
    def setUp(self):
        import zipfile
        self.zipfile = zipfile
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE comics(ComicID,ComicName,ComicYear,ComicVersion,Type);
            CREATE TABLE issues(IssueID,ComicID,Issue_Number);
            CREATE TABLE annuals(IssueID,ComicID,Issue_Number,ReleaseComicName,ReleaseComicID,Deleted);
            INSERT INTO comics VALUES('10','Comic','2020','v2','Print');
            INSERT INTO issues VALUES('100','10','15'),('101','10','16');
            INSERT INTO annuals VALUES('200','10','1','Comic Annual','20',0);
        ''')
        self.database = SimpleNamespace(select=lambda sql, args: self.db.execute(sql, args).fetchall())
        self.series = dict(ComicID='10', ComicName='Comic', ComicYear='2020', ComicVersion='v2', Type='Print')

    def files(self, name, xml=None, number='15', annual=None):
        path = self.folder/name
        with self.zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('page.jpg', b'fixture')
            if xml is not None:
                archive.writestr('ComicInfo.xml', xml)
        return [dict(comiclist=[dict(ComicFilename=name, ComicLocation=str(self.folder), JusttheDigits=number, AnnualComicID=annual)])]

    def check(self, files):
        from file_identity import validate_rescan
        validate_rescan(self.database, self.series, files)

    def test_conflicting_metadata_cannot_reassign_or_delete_a_file(self):
        files = self.files('Comic 015 (2021).cbz', '<ComicInfo><Series>Comic</Series><Number>16</Number><Web>https://comicvine.gamespot.com/issue/4000-101/</Web></ComicInfo>')
        with self.assertRaises(ValueError):
            self.check(files)
        self.assertEqual(len(list(self.folder.iterdir())), 1)

    def test_other_volume_identity_is_rejected_before_rescan(self):
        files = self.files('Comic 015 (2021).cbz', '<ComicInfo><Series>Comic</Series><Number>15</Number><Web>https://comicvine.gamespot.com/issue/4000-999/</Web></ComicInfo>')
        with self.assertRaises(ValueError):
            self.check(files)

    def test_repeated_fields_and_entities_require_review(self):
        for xml in (
            '<ComicInfo><Number>15</Number><Number>16</Number></ComicInfo>',
            '<!DOCTYPE ComicInfo [<!ENTITY issue "15">]><ComicInfo><Number>&issue;</Number></ComicInfo>',
        ):
            with self.assertRaises(ValueError):
                self.check(self.files('Comic 015.cbz', xml))

    def test_catalog_id_checks_native_number_without_xml_number(self):
        with self.assertRaises(ValueError):
            self.check(self.files('Comic 016.cbz', '<ComicInfo><Web>https://comicvine.gamespot.com/issue/4000-100/</Web></ComicInfo>', number='16'))

    def test_same_number_catalog_rows_require_review_even_with_exact_id(self):
        self.db.execute("UPDATE issues SET Issue_Number='15' WHERE IssueID='101'")
        with self.assertRaises(ValueError):
            self.check(self.files('Comic 015 (2021).cbz', '<ComicInfo><Series>Comic</Series><Number>15</Number><Web>https://comicvine.gamespot.com/issue/4000-100/</Web></ComicInfo>'))

    def test_annual_and_collected_effective_numbers_cannot_disagree(self):
        for parsed in ('Annual 2', '2annual'):
            with self.assertRaises(ValueError):
                self.check(self.files('Comic Annual 002.cbz', '<ComicInfo><Series>Comic Annual</Series><Number>1</Number><Web>https://comicvine.gamespot.com/issue/4000-200/</Web></ComicInfo>', number=parsed, annual='20'))
        self.series['Type'] = 'TPB'
        files = self.files('Comic v16.cbz', '<ComicInfo><Series>Comic</Series><Number>15</Number><Web>https://comicvine.gamespot.com/issue/4000-100/</Web></ComicInfo>')
        files[0]['comiclist'][0]['SeriesVolume'] = 'v16'
        with self.assertRaises(ValueError):
            self.check(files)

    def test_series_and_volume_evidence_is_checked_without_web(self):
        for fields in ('<Series>Other Comic</Series>', '<Series>Comic</Series><Volume>1990</Volume>'):
            with self.assertRaises(ValueError):
                self.check(self.files('Comic 015.cbz', '<ComicInfo>'+fields+'<Number>15</Number></ComicInfo>'))
        self.series['AlternateSearch'] = 'Alias Comic'
        self.check(self.files('Comic 015.cbz', '<ComicInfo><Series>Alias Comic</Series><Number>15</Number><Volume>2020</Volume></ComicInfo>'))
        self.check(self.files('Comic 015.cbz', '<ComicInfo><Series>Alias Comic</Series><Number>15</Number><Web>https://comicvine.gamespot.com/issue/4000-100/</Web></ComicInfo>'))

    def test_multiple_matching_files_and_year_named_annuals_survive(self):
        a = self.files('Comic 015.cbz', '<ComicInfo><Series>Comic</Series><Number>15</Number><Web>https://comicvine.gamespot.com/issue/4000-100/</Web></ComicInfo>')
        b = self.files('Comic 016.cbz', '<ComicInfo><Series>Comic</Series><Number>16</Number><Web>https://comicvine.gamespot.com/issue/4000-101/</Web></ComicInfo>', number='16')
        self.check(a+b)
        self.check(self.files('Comic Annual 2021.cbz', '<ComicInfo><Series>Comic Annual</Series><Number>1</Number><Web>https://comicvine.gamespot.com/issue/4000-200/</Web></ComicInfo>', number='2021annual', annual='20'))

    def test_annual_metadata_must_name_its_parsed_release(self):
        self.db.execute("INSERT INTO annuals VALUES('201','10','1','Other Annual','21',0)")
        with self.assertRaises(ValueError):
            self.check(self.files('Comic Annual 001.cbz', '<ComicInfo><Series>Other Annual</Series><Number>1</Number></ComicInfo>', number='Annual 1', annual='20'))

    def test_non_zip_comic_archives_wait_for_verified_conversion(self):
        path = self.folder/'Comic 015.cbr'
        path.write_bytes(b'opaque rar fixture')
        files = [dict(comiclist=[dict(ComicFilename=path.name, ComicLocation=str(self.folder), JusttheDigits='15')])]
        with self.assertRaises(ValueError):
            self.check(files)

    def test_matching_metadata_and_legacy_unique_series_survive(self):
        self.check(self.files('Comic 015 (2021).cbz', '<ComicInfo><Series>Comic</Series><Number>15</Number><Web>https://comicvine.gamespot.com/issue/4000-100/</Web></ComicInfo>'))
        self.check(self.files('Comic 016 (2021).cbz', number='16'))

    def test_untagged_same_title_year_volumes_require_explicit_version(self):
        self.db.execute("INSERT INTO comics VALUES('11','Comic','2020','v1','Print')")
        with self.assertRaises(ValueError):
            self.check(self.files('Comic 015 (2021).cbz'))
        self.check(self.files('Comic v2 015 (2021).cbz'))

    def test_annual_uses_its_release_identity_and_preserves_parent(self):
        self.check(self.files('Comic Annual 001 (2021).cbz', '<ComicInfo><Series>Comic Annual</Series><Number>1</Number><Web>https://comicvine.gamespot.com/issue/4000-200/</Web></ComicInfo>', number='1 annual', annual='20'))
        with self.assertRaises(ValueError):
            self.check(self.files('Comic Annual 001 (2021).cbz', '<ComicInfo><Series>Comic Annual</Series><Number>1</Number><Web>https://comicvine.gamespot.com/issue/4000-200/</Web></ComicInfo>', number='1 annual', annual='21'))


if __name__ == "__main__":
    unittest.main()
