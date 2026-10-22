"""Read-only catalog planning and private-manifest boundary fixtures."""

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
import zipfile

SPEC = importlib.util.spec_from_file_location("calibre_catalog_import", Path(__file__).parents[1] / "calibre-catalog-import.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def epub(path, title="Fixture Title", author="Fixture Author", identifiers=(), marker="", creator_role=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    role = '' if creator_role is None else f' opf:role="{creator_role}"'
    creators = '' if author is None else f'<dc:creator{role}>{author}</dc:creator>'
    titles = '' if title is None else f'<dc:title>{title}</dc:title>'
    ids = ''.join(f'<dc:identifier opf:scheme="ISBN">{value}</dc:identifier>' for value in identifiers)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("META-INF/container.xml", '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="content/package.opf"/></rootfiles></container>')
        archive.writestr("content/package.opf", f'<package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf"><metadata>{titles}{creators}{ids}</metadata></package>')
        archive.writestr("content/fixture.txt", marker)


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.library = self.root / "library"
        self.library.mkdir()
        self.database = self.library / "metadata.db"
        self.connection = sqlite3.connect(self.database)
        self.connection.executescript('''
            CREATE TABLE books(id INTEGER PRIMARY KEY,title TEXT,path TEXT);
            CREATE TABLE data(id INTEGER PRIMARY KEY,book INTEGER,name TEXT,format TEXT);
            CREATE TABLE identifiers(id INTEGER PRIMARY KEY,book INTEGER,type TEXT,val TEXT);
            CREATE TABLE authors(id INTEGER PRIMARY KEY,name TEXT);
            CREATE TABLE books_authors_link(id INTEGER PRIMARY KEY,book INTEGER,author INTEGER);
        ''')
        self.connection.commit()

    def tearDown(self):
        self.connection.close()
        self.directory.cleanup()

    def registered(self, title="Existing Work", author="Fixture Author", identifier=None):
        path = self.library / "catalog" / "registered.epub"
        epub(path, title, author, [identifier] if identifier else [])
        self.connection.execute("INSERT INTO books VALUES(1,?,?)", (title, "catalog"))
        self.connection.execute("INSERT INTO data VALUES(1,1,'registered','EPUB')")
        self.connection.execute("INSERT INTO authors VALUES(1,?)", (author,))
        self.connection.execute("INSERT INTO books_authors_link VALUES(1,1,1)")
        if identifier:
            self.connection.execute("INSERT INTO identifiers VALUES(1,1,'isbn',?)", (identifier,))
        self.connection.commit()
        return path

    def test_calibre_recycle_bin_and_notes_are_never_candidates(self):
        self.registered()
        epub(self.library / ".caltrash" / "deleted.epub", "Deleted Work")
        epub(self.library / ".calnotes" / "attachment.epub", "Note Attachment")
        result = MODULE.plan(self.library)
        self.assertEqual(result["counts"]["sourceFiles"], 1)
        self.assertEqual(result["counts"]["candidateBooks"], 0)

    def test_isbn_checksums_and_canonical_forms(self):
        for value in ["0-306-40615-2", "urn:isbn:9780306406157", "ISBN-13: 978-0-306-40615-7"]:
            self.assertEqual(MODULE.isbn(value), "9780306406157")
        for value in ["9780306406158", "0306406153", "urn:uuid:fixture", "123"]:
            self.assertIsNone(MODULE.isbn(value))

    def test_new_epub_candidate_and_read_only_database_baseline(self):
        self.registered()
        epub(self.library / "loose" / "new.epub", "New Work", "A. Writer", ["9780306406157"])
        before = hashlib.sha256(self.database.read_bytes()).hexdigest()
        result = MODULE.plan(self.library)
        self.assertEqual(result["counts"]["candidateBooks"], 1)
        self.assertEqual(result["candidates"][0]["isbns"], ["9780306406157"])
        self.assertEqual(result["baseline"]["bookCount"], 1)
        self.assertEqual(before, hashlib.sha256(self.database.read_bytes()).hexdigest())
        self.assertEqual(result["baseline"]["physicalFiles"][0]["sha256"], before)
        self.assertEqual(len(result["baseline"]["logicalSha256"]), 64)
        self.assertEqual(result["operation"], "review-only")

    def test_binary_duplicates_and_unsupported_orphan_formats(self):
        registered = self.registered()
        (self.library / "copy.epub").write_bytes(registered.read_bytes())
        epub(self.library / "new.epub", "New Work")
        (self.library / "new-copy.epub").write_bytes((self.library / "new.epub").read_bytes())
        (self.library / "orphan.azw3").write_bytes(b"unregistered-format")
        result = MODULE.plan(self.library)
        self.assertEqual(result["counts"]["duplicate_registered_content"], 1)
        self.assertEqual(result["counts"]["duplicate_candidate_content"], 1)
        self.assertEqual(result["counts"]["unsupported_orphan_format"], 1)
        self.assertEqual(result["counts"]["candidateBooks"], 1)

    def test_existing_titles_excluded_even_with_different_author_or_edition(self):
        self.registered("Same Title")
        epub(self.library / "same.epub", "Same Title", marker="different bytes")
        epub(self.library / "different-author.epub", "Same Title", "Another Author")
        result = MODULE.plan(self.library)
        self.assertEqual(result["counts"]["candidateBooks"], 0)
        self.assertEqual(result["counts"]["existing_title"], 1)
        self.assertEqual(result["counts"]["ambiguous_existing_title"], 1)

    def test_same_title_new_editions_without_exact_identity_excluded(self):
        epub(self.library / "one.epub", "Same Work", marker="edition one")
        epub(self.library / "two.epub", "Same Work", marker="edition two")
        result = MODULE.plan(self.library)
        self.assertEqual(result["counts"]["candidateBooks"], 0)
        self.assertEqual(result["counts"]["ambiguous_new_title_editions"], 2)

    def test_same_isbn_edition_deduplicated_but_existing_isbn_excluded(self):
        self.registered(identifier="0-306-40615-2")
        epub(self.library / "already.epub", "Variant Metadata", identifiers=["urn:isbn:9780306406157"])
        epub(self.library / "one.epub", "New Same Work", identifiers=["9780131103627"], marker="one")
        epub(self.library / "two.epub", "New Same Work", identifiers=["0131103628"], marker="two")
        result = MODULE.plan(self.library)
        self.assertEqual(result["counts"]["existing_isbn"], 1)
        self.assertEqual(result["counts"]["duplicate_isbn_edition"], 1)
        self.assertEqual(result["counts"]["candidateBooks"], 1)

    def test_isbn_conflicting_titles_or_authors_excluded(self):
        epub(self.library / "one.epub", "First Work", identifiers=["9780306406157"])
        epub(self.library / "two.epub", "Other Work", identifiers=["9780306406157"])
        result = MODULE.plan(self.library)
        self.assertEqual(result["counts"]["candidateBooks"], 0)
        self.assertEqual(result["counts"]["isbn_conflicting_metadata"], 2)

    def test_missing_metadata_conflicting_isbns_and_translator_are_excluded(self):
        epub(self.library / "title.epub", title=None)
        epub(self.library / "author.epub", author=None)
        epub(self.library / "translator.epub", creator_role="trl")
        epub(self.library / "identifiers.epub", identifiers=["9780306406157", "9780131103627"])
        (self.library / "broken.epub").write_bytes(b"not-a-zip")
        result = MODULE.plan(self.library)
        self.assertEqual(result["counts"]["candidateBooks"], 0)
        self.assertEqual(result["counts"]["missing_or_ambiguous_title"], 1)
        self.assertEqual(result["counts"]["missing_author"], 2)
        self.assertEqual(result["counts"]["conflicting_edition_isbns"], 1)
        self.assertEqual(result["counts"]["invalid_epub_metadata"], 1)

    def test_multiple_title_nodes_and_oversized_package_are_excluded(self):
        for filename, title in [("multiple.epub", "First</dc:title><dc:title>Second"),
                                ("oversized.epub", "x" * 2097152)]:
            epub(self.library / filename, title=title)
        result = MODULE.plan(self.library)
        self.assertEqual(result["counts"]["candidateBooks"], 0)
        self.assertEqual(result["counts"]["missing_or_ambiguous_title"], 1)
        self.assertEqual(result["counts"]["epub_metadata_limits"], 1)

    def test_source_symlinks_not_followed_and_catalog_traversal_rejected(self):
        epub(self.root / "outside.epub")
        (self.library / "link.epub").symlink_to(self.root / "outside.epub")
        self.assertEqual(MODULE.plan(self.library)["counts"]["ignoredSymlinks"], 1)
        self.connection.execute("INSERT INTO books VALUES(1,'Invalid','../outside')")
        self.connection.execute("INSERT INTO data VALUES(1,1,'invalid','EPUB')")
        self.connection.commit()
        with self.assertRaises(MODULE.PlanError):
            MODULE.plan(self.library)

    def test_stdout_never_contains_private_metadata_or_paths(self):
        epub(self.library / "private-filename.epub", "Private Work Name", "Private Author")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(MODULE.main([str(self.library)]), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(set(result), {"counts", "manifestWritten"})
        for secret in ["Private", "private-filename", str(self.library)]:
            self.assertNotIn(secret, output.getvalue())

    def private_parent(self):
        parent = self.root / "private"
        parent.mkdir(mode=0o700)
        return parent

    def test_private_manifest_exclusive_0600_and_metadata_present(self):
        epub(self.library / "new.epub", "Private Work")
        document = MODULE.plan(self.library)
        target = self.private_parent() / "review.json"
        MODULE.write_manifest(target, document)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertEqual(json.loads(target.read_text())["candidates"][0]["title"], "Private Work")
        with self.assertRaises(MODULE.PlanError):
            MODULE.write_manifest(target, document)
        self.assertEqual(json.loads(target.read_text()), document)

    def test_manifest_parent_permissions_symlinks_and_git_rejected(self):
        document = MODULE.plan(self.library)
        parent = self.private_parent()
        parent.chmod(0o755)
        with self.assertRaises(MODULE.PlanError):
            MODULE.write_manifest(parent / "review.json", document)
        parent.chmod(0o700)
        link = self.root / "link"
        link.symlink_to(parent, target_is_directory=True)
        with self.assertRaises(MODULE.PlanError):
            MODULE.write_manifest(link / "review.json", document)
        (parent / "review.json").symlink_to(self.root / "outside.json")
        with self.assertRaises(MODULE.PlanError):
            MODULE.write_manifest(parent / "review.json", document)
        self.assertFalse((self.root / "outside.json").exists())
        (parent / ".git").write_text("gitdir: fixture")
        with self.assertRaises(MODULE.PlanError):
            MODULE.write_manifest(parent / "new.json", document)
        with self.assertRaises(MODULE.PlanError):
            MODULE.write_manifest(Path("relative.json"), document)


if __name__ == "__main__":
    unittest.main()
