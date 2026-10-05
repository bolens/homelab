"""Rescan/converted ownership controls use real registry and archive fixtures."""
from pathlib import Path
from contextlib import closing
import sqlite3
import types
import unittest
from unittest.mock import Mock, patch
import zipfile

import test_publication_native as cases
import publication_native as native
import publication_rescan as rescan
import converted_catalog


@unittest.skipUnless((Path(cases.fixtures.TOOL_ROOT)/'lib/archive_backend.py').is_file(),
                     'offline archive verifier required; custom image gate supplies it')
class PublicationRescanTests(unittest.TestCase):
    setUp=cases.AdmissionTests.setUp
    call=cases.AdmissionTests.call
    bootstrap=cases.AdmissionTests.bootstrap
    prepare=cases.AdmissionTests.prepare
    registered=cases.AdmissionTests.registered
    sql=cases.AdmissionTests.sql

    def test_correct_retained_archive_passes_fresh_rescan_admission(self):
        self.registered();before=(self.source.read_bytes(),self.database.read_bytes())
        with self.writer.hold():
            rescan.require_entries([(self.incoming,dict(IssueID='123'))],dict(ComicID='456'))
        self.assertEqual((self.source.read_bytes(),self.database.read_bytes()),before)

    def test_wrong_payload_claim_stops_before_catalog_or_parser_mutation(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Wanted'))
        before=(self.incoming.read_bytes(),self.database.read_bytes())
        with self.writer.hold(),self.assertRaises(native.Review):
            rescan.require_entries([(self.incoming,dict(IssueID='999'))],dict(ComicID='888'))
        self.assertEqual((self.incoming.read_bytes(),self.database.read_bytes()),before)

    def test_missing_correct_archive_cannot_be_an_empty_successful_scan(self):
        self.registered();self.source.unlink();before=self.database.read_bytes()
        with self.writer.hold(),self.assertRaises(native.Review):
            rescan.require_entries([],dict(ComicID='456'))
        self.assertEqual(self.database.read_bytes(),before);self.assertTrue(self.incoming.is_file())

    def test_changed_correct_status_cannot_bypass_empty_scan_protection(self):
        self.registered();self.sql("UPDATE issues SET Status='Wanted' WHERE IssueID='123'")
        before=self.database.read_bytes()
        with self.writer.hold(),self.assertRaises(native.Review):rescan.require_entries([],dict(ComicID='456'))
        self.assertEqual(self.database.read_bytes(),before)

    def test_deleted_annual_shadow_refuses_even_an_empty_scan(self):
        self.registered();self.sql('INSERT INTO annuals VALUES (?,?,?,?,?,?)',('123','999','888',None,'Archived',1))
        before=(self.source.read_bytes(),self.database.read_bytes())
        with self.writer.hold(),self.assertRaises(native.Review):
            rescan.require_entries([],dict(ComicID='456'))
        self.assertEqual((self.source.read_bytes(),self.database.read_bytes()),before)

    def test_rejected_owner_with_different_archive_keeps_existing_eligibility(self):
        self.registered();self.sql('INSERT INTO comics VALUES (?,?,?)',('888',str(self.library),'Paused'))
        different=self.library/'different.cbz'
        with zipfile.ZipFile(different,'w') as archive:archive.writestr('01.jpg',b'genuinely different pages')
        self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',different.name,'Downloaded'))
        before=(different.read_bytes(),self.database.read_bytes())
        with self.writer.hold():rescan.require_entries([],dict(ComicID='888'))
        self.assertEqual((different.read_bytes(),self.database.read_bytes()),before)

    def test_converted_catalog_guard_precedes_row_update(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Wanted'))
        self.mylar.publication_rescan=rescan;action=Mock();database=types.SimpleNamespace(action=action)
        row=dict(table='issues',IssueID='999',ComicID='888',Location='old.cbr',Status='Archived')
        before=self.incoming.read_bytes()
        with self.writer.hold(),self.assertRaises(native.Review):
            converted_catalog.update(database,row,self.incoming)
        action.assert_not_called();self.assertEqual(self.incoming.read_bytes(),before)

    def test_catalog_change_during_preflight_keeps_scan_in_review(self):
        self.registered();original=rescan.require_entry;calls=[]
        def changed(*args):
            value=original(*args)
            if not calls:
                calls.append(True);self.sql("UPDATE comics SET Status='Active' WHERE ComicID='456'")
            return value
        before=self.incoming.read_bytes()
        with self.writer.hold(),patch.object(rescan,'require_entry',side_effect=changed),self.assertRaises(native.Review):
            rescan.require_entries([(self.incoming,dict(IssueID='123'))],dict(ComicID='456'))
        self.assertEqual(self.incoming.read_bytes(),before)

    def test_parser_uncertainty_is_terminal_review_before_any_row_update(self):
        database=types.SimpleNamespace(select=Mock(side_effect=ValueError('ambiguous catalog')),action=Mock())
        with self.writer.hold(),self.assertRaises(native.Review):
            rescan.validate_rescan(database,dict(ComicID='456'),[])
        database.action.assert_not_called()

    def test_complete_native_validator_preserves_current_registered_binding(self):
        self.registered()
        for column in ('ComicName','ComicYear','ComicVersion','Type'):
            self.sql('ALTER TABLE comics ADD COLUMN '+column+' TEXT')
        self.sql("UPDATE comics SET ComicName='Series',ComicYear='2020',ComicVersion='v1',Type='Print'")
        self.sql('ALTER TABLE issues ADD COLUMN Issue_Number TEXT')
        self.sql("UPDATE issues SET Issue_Number='1'")
        def select(query,args):
            with closing(sqlite3.connect(self.database)) as connection:
                connection.row_factory=sqlite3.Row
                return connection.execute(query,args).fetchall()
        database=types.SimpleNamespace(select=select,action=Mock())
        series=dict(ComicID='456',ComicName='Series',ComicYear='2020',ComicVersion='v1',Type='Print')
        files=[dict(comiclist=[dict(ComicFilename=self.source.name,ComicLocation=str(self.library),
                                   JusttheDigits='1',AnnualComicID=None)])]
        before=(self.source.read_bytes(),self.database.read_bytes())
        with self.writer.hold():rescan.validate_rescan(database,series,files)
        database.action.assert_not_called()
        self.assertEqual((self.source.read_bytes(),self.database.read_bytes()),before)


if __name__=='__main__':unittest.main()
