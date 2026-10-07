"""Actual independent worker admission across cleanup namespace read races."""
from contextlib import closing
import json
import shutil
import sqlite3
import unittest
from unittest.mock import patch

import publication_evidence as evidence
from publication_guard import Unavailable
from test_publication_guard import AuthorityFixture


class AdmissionTests(AuthorityFixture, unittest.TestCase):
    def refused_after_cleanup_read(self, change):
        actual=evidence.cleanup_admission
        before=self.source.read_bytes()
        def changed(database):
            change()
            return actual(database)
        with self.writer.hold(),patch.object(evidence,'cleanup_admission',side_effect=changed),self.assertRaises(Unavailable):
            self.authority.check(self.candidate,self.owner)
        self.assertEqual(self.source.read_bytes(),before)

    def test_privacy_change_between_registry_and_cleanup_cannot_admit(self):
        self.refused_after_cleanup_read(lambda:self.workflow.chmod(0o644))

    def replace(self, path):
        target=path.with_name(path.name+'.replacement')
        shutil.copyfile(path,target);target.chmod(0o600);target.replace(path)

    def test_database_replacement_between_proofs_cannot_admit(self):
        self.refused_after_cleanup_read(lambda:self.replace(self.workflow))

    def test_marker_replacement_between_proofs_cannot_admit(self):
        self.refused_after_cleanup_read(lambda:self.replace(self.writer.root/'publication-v1.json'))

    def test_blob_cleanup_namespace_cannot_hide_an_unresolved_attempt(self):
        with closing(sqlite3.connect(self.workflow)) as db:
            db.execute('INSERT INTO records VALUES (?,?,?,?)',
                (sqlite3.Binary(b'combined_cleanup'),'d'*64,json.dumps({'phase':'attempted'}),1))
            db.commit()
        before=self.workflow.read_bytes()
        with self.writer.hold(),self.assertRaises(Unavailable):
            self.authority.check(self.candidate,self.owner)
        self.assertEqual(self.workflow.read_bytes(),before)


    def test_unfinished_conversion_and_repeat_hold_without_filesystem_intent(self):
        for kind in ('owned_conversion','retained_repeat'):
            with self.subTest(kind=kind):
                with closing(sqlite3.connect(self.workflow)) as db:
                    db.execute('INSERT INTO records VALUES (?,?,?,?)',
                        (kind,'d'*64,json.dumps({'version':1,'token':'d'*64,'phase':'prepared'}),1))
                    db.commit()
                before=self.source.read_bytes()
                with self.writer.hold(),self.assertRaises(Unavailable):
                    self.authority.check(self.candidate,self.owner)
                self.assertEqual(self.source.read_bytes(),before)
                with closing(sqlite3.connect(self.workflow)) as db:
                    db.execute('DELETE FROM records WHERE kind=?',(kind,));db.commit()

    def test_blob_conversion_and_repeat_namespaces_do_not_bypass_hold(self):
        for kind in ('owned_conversion','retained_repeat'):
            with self.subTest(kind=kind):
                with closing(sqlite3.connect(self.workflow)) as db:
                    db.execute('INSERT INTO records VALUES (?,?,?,?)',
                        (sqlite3.Binary(kind.encode()),'d'*64,json.dumps({'phase':'prepared'}),1))
                    db.commit()
                before=self.workflow.read_bytes()
                with self.writer.hold(),self.assertRaises(Unavailable):
                    self.authority.check(self.candidate,self.owner)
                self.assertEqual(self.workflow.read_bytes(),before)
                with closing(sqlite3.connect(self.workflow)) as db:
                    db.execute('DELETE FROM records WHERE CAST(kind AS TEXT)=?',(kind,));db.commit()


if __name__=='__main__':unittest.main()
