"""Exercise the complete native filename parser in the candidate image."""

from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

SOURCE = Path(sys.argv.pop(1))
sys.path[:0] = [str(SOURCE.parent), "/app/mylar3", "/app/mylar3/lib"]
import mylar
from mylar import filechecker
from unittest.mock import Mock, patch


class NativeMatchingTest(unittest.TestCase):
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
                    IGNORE_SEARCH_WORDS=[], ANNUALS_ON=True, CUSTOM_ISSUE_EXCEPTIONS=[]
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
