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


if __name__ == "__main__":
    unittest.main()
