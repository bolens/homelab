"""Converted ownership requires an exact old path and verified output."""
import hashlib
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import converted_catalog as catalog
import library_status
import publication_rescan


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root/'Comic (2024) 014 (2026) (digital).cbz'
        self.path.write_bytes(b'verified archive fixture')
        self.digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.db = sqlite3.connect(':memory:'); self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.executescript('''CREATE TABLE comics(ComicID TEXT,ComicLocation TEXT);
            CREATE TABLE issues(IssueID TEXT,ComicID TEXT,ComicName TEXT,Location TEXT,Status TEXT);
            CREATE TABLE annuals(IssueID TEXT,ComicID TEXT,ComicName TEXT,Location TEXT,Status TEXT,Deleted INTEGER);''')
        self.db.execute('INSERT INTO comics VALUES (?,?)', ('1', str(self.root)))
        self.db.execute('INSERT INTO issues VALUES (?,?,?,?,?)', ('2','1','Comic',self.path.with_suffix('.cbr').name,'Archived'))
        self.database = SimpleNamespace(select=lambda q,a=():self.db.execute(q,a).fetchall(), action=lambda q,a:self.db.execute(q,a))
        self.inspector = Mock(return_value=(self.digest,False))
        self.jobs = []
        self.mylar = SimpleNamespace(library_status=library_status,db=SimpleNamespace(DBConnection=lambda:self.database),
            publication_rescan=publication_rescan,native_writers=SimpleNamespace(publication_mode=lambda:False),
            workflow=SimpleNamespace(store=lambda:SimpleNamespace(active=lambda *a:self.jobs)),
            converted_tagging=SimpleNamespace(inspect_archive=self.inspector,catalog=lambda p:dict(issueid='2',comicid='1')))
        ctx=patch.dict(sys.modules,{'mylar':self.mylar,'mylar.converted_tagging':self.mylar.converted_tagging})
        ctx.start();self.addCleanup(ctx.stop)

    def status(self):
        return tuple(self.db.execute('SELECT Location,Status FROM issues WHERE IssueID="2"').fetchone())

    def test_acknowledged_conversion_repairs_old_extension_without_filename_parsing(self):
        self.assertTrue(catalog.reconcile(self.database,str(self.path),self.digest))
        self.assertEqual(self.status(),(self.path.name,'Downloaded'))
        self.assertEqual(self.path.read_bytes(),b'verified archive fixture')

    def test_annual_owner_and_unnumbered_title_are_supported(self):
        self.db.execute('DELETE FROM issues')
        self.db.execute('INSERT INTO annuals VALUES (?,?,?,?,?,0)',('2','1','Comic',self.path.with_suffix('.cb7').name,'Archived'))
        self.assertTrue(catalog.reconcile(self.database,str(self.path),self.digest))
        self.assertEqual(tuple(self.db.execute('SELECT Location,Status FROM annuals').fetchone()),(self.path.name,'Downloaded'))

    def test_supported_composite_archive_suffixes_keep_exact_stem(self):
        for suffix in catalog.FORMATS:
            with self.subTest(suffix=suffix):
                old=self.path.stem+suffix
                self.db.execute('UPDATE issues SET Location=?,Status="Archived"',[old])
                self.assertTrue(catalog.reconcile(self.database,str(self.path),self.digest))
                self.assertEqual(self.status(),(self.path.name,'Downloaded'))

    def test_changed_output_does_not_change_catalog(self):
        with self.assertRaises(ValueError):catalog.reconcile(self.database,str(self.path),'b'*64)
        self.assertEqual(self.status()[1],'Archived')

    def test_existing_original_and_unowned_file_are_not_reconciled(self):
        self.path.with_suffix('.cbr').write_bytes(b'original')
        self.assertFalse(catalog.reconcile(self.database,str(self.path),self.digest))
        self.path.with_suffix('.cbr').unlink()
        self.db.execute('UPDATE issues SET Location="Another.cbr"')
        self.assertFalse(catalog.reconcile(self.database,str(self.path),self.digest))
        self.inspector.assert_not_called()

    def test_duplicate_deleted_and_conflicting_annual_ownership_fail_closed(self):
        self.db.execute('INSERT INTO annuals VALUES (?,?,?,?,?,0)',('3','1','Comic',self.path.with_suffix('.cbr').name,'Archived'))
        with self.assertRaises(ValueError):catalog.reconcile(self.database,str(self.path),self.digest)
        self.db.execute('DELETE FROM annuals')
        self.db.execute('INSERT INTO annuals VALUES (?,?,?,?,?,1)',('2','1','Comic',None,'Archived'))
        with self.assertRaises(ValueError):catalog.reconcile(self.database,str(self.path),self.digest)
        self.assertEqual(self.status()[1],'Archived')

    def test_symlinks_and_unrelated_status_are_not_repaired(self):
        target=self.root/'other.cbz';self.path.rename(target);self.path.symlink_to(target)
        with self.assertRaises(ValueError):catalog.reconcile(self.database,str(self.path),self.digest)
        self.path.unlink();target.rename(self.path)
        self.db.execute('UPDATE issues SET Status="Wanted"')
        self.assertFalse(catalog.reconcile(self.database,str(self.path),self.digest))

    def test_rescan_preserves_established_conversion_only_if_file_unchanged(self):
        self.db.execute('UPDATE issues SET Location=?,Status="Downloaded"',[self.path.name])
        self.jobs=[dict(path=str(self.path),comicid='1',issueid='2',phase='completed')]
        @catalog.rescan
        def scan(comicid,change=False):
            self.db.execute('UPDATE issues SET Status="Archived"')
            if change:self.path.write_bytes(b'replaced')
            return 'native-result'
        self.assertEqual(scan('1'),'native-result')
        self.assertEqual(self.status()[1],'Downloaded')
        scan('1',change=True);self.assertEqual(self.status()[1],'Archived')

    def test_rescan_does_not_steal_file_from_new_owner(self):
        self.db.execute('UPDATE issues SET Location=?,Status="Downloaded"',[self.path.name])
        self.jobs=[dict(path=str(self.path),comicid='1',issueid='2',phase='completed')]
        @catalog.rescan
        def scan(comicid):
            self.db.execute('UPDATE issues SET Status="Archived"')
            self.db.execute('INSERT INTO issues VALUES (?,?,?,?,?)',('3','1','Comic',self.path.name,'Downloaded'))
        scan('1');self.assertEqual(self.status()[1],'Archived')

    def test_explicit_archival_rescan_is_not_overridden(self):
        self.jobs=[dict(path=str(self.path),comicid='1',issueid='2',phase='completed')]
        @catalog.rescan
        def scan(comicid,archive=None):
            self.db.execute('UPDATE issues SET Status="Archived"')
        scan('1',archive='/archive');self.assertEqual(self.status()[1],'Archived')

    def test_patch_keeps_reconciliation_inside_writer_and_is_idempotent(self):
        from patch_converted_tagging import rescan
        source='@native_writers.guard\ndef forceRescan(ComicID):\n    return ComicID\n'
        patched=rescan(source)
        self.assertIn('@native_writers.guard\n@converted_catalog.rescan',patched)
        self.assertEqual(rescan(patched),patched)


if __name__=='__main__':unittest.main()
