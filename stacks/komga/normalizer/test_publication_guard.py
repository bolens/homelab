"""Portable vectors and fresh local authority controls; no live state."""
from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from media_writer import Writer
import publication_evidence as evidence
from publication_guard import Authority, Unavailable


class WorkerEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = self.root / 'config'; self.config.mkdir()
        self.library = self.root / 'library'; self.library.mkdir()
        self.writer = Writer(self.config / 'media-writer', create=True)
        self.tool = Path('/opt/archiving-utils')
        if not (self.tool / 'lib/comics.py').is_file():
            # ZIP/TAR use our streaming verifier. Only the decoder's page
            # protocol constant is needed for these host fixtures.
            self.tool = self.root / 'page-protocol'
            (self.tool / 'lib').mkdir(parents=True)
            (self.tool / 'lib/comics.py').write_text('PAGE_EXTENSIONS=' + repr(evidence.PAGE_EXTENSIONS))
        self.source = self.archive('correct.cbz', [('01.jpg', b'one')])
        self.candidate = self.archive('candidate.cbz', [('01.jpg', b'one')])
        self.owner = dict(table='issues', issueid='123', parentcomicid='456', releasecomicid='456')
        self.rejected = dict(table='issues', issueid='999', parentcomicid='888', releasecomicid='888')
        self.native_root = Path('/native-comics')
        self.authority = Authority(self.config, self.writer,
            [dict(native=str(self.native_root), worker=str(self.library))], tool_root=self.tool)
        self.catalog = self.config / 'mylar.db'
        self.workflow = self.config / 'workflow.sqlite'
        with closing(sqlite3.connect(self.catalog)) as db:
            db.executescript('CREATE TABLE comics(ComicID TEXT,ComicLocation TEXT);'
                'CREATE TABLE issues(IssueID TEXT,ComicID TEXT,Location TEXT,Status TEXT);'
                'CREATE TABLE annuals(IssueID TEXT,ComicID TEXT,ReleaseComicID TEXT,Location TEXT,Status TEXT,Deleted INT);')
            db.execute('INSERT INTO comics VALUES (?,?)', ('456', str(self.native_root)))
            db.execute('INSERT INTO issues VALUES (?,?,?,?)', ('123', '456', self.source.name, 'Downloaded'))
            db.commit()
        with closing(sqlite3.connect(self.workflow)) as db:
            db.executescript('CREATE TABLE events (id INTEGER PRIMARY KEY, value TEXT);'
                'CREATE TABLE records (kind TEXT NOT NULL,key TEXT NOT NULL,value TEXT NOT NULL,'
                'updated REAL NOT NULL,PRIMARY KEY(kind,key));')
        self.workflow.chmod(0o600)
        self.seed()

    def archive(self, name, members):
        target = self.library / name
        with zipfile.ZipFile(target, 'w') as archive:
            for member, raw in members:
                archive.writestr(member, raw)
        return target

    def seed(self, *, empty=False):
        with self.writer.hold():
            census = evidence.empty_census('e' * 64)
            with closing(sqlite3.connect(self.workflow)) as db:
                binding = dict(database_identity=evidence.signature(self.workflow.stat())[:2],
                    writer_identity=evidence.writer_identity(self.writer), schema=evidence.workflow_schema(db),
                    workflow=dict(version=1, count=0, digest=evidence.canonical_digest([])),
                    pending=dict(normalizer=None, tagger=None, release=None))
                plan = dict(version=1, action='bootstrap', epoch=census['epoch'], binding=binding,
                    backup=dict(manifest_sha256='a'*64, restore_sha256='b'*64, description='Fixture restore'), new=census)
                initial = evidence.canonical_digest(plan)
                rows = [('publication_intent', initial, dict(plan=plan, accepted=True, outcome='committed'))]
                if not empty:
                    observed = evidence.observe_owners(self.catalog, self.writer, [self.owner], [self.native_root],
                        tool_root=self.tool, path_mapper=self.authority.mapped)
                    body = dict(version=1, epoch=census['epoch'], prior_revision=0,
                        inventory=observed['inventory'], allowed=[self.owner], rejected=[self.rejected],
                        evidence=dict(sha256='c'*64, description='Reviewed fixture'), observed=observed['observed'], created=1)
                    registration = dict(version=1, action='register', old=census, binding=binding, body=body)
                    token = evidence.canonical_digest(registration)
                    attestation, census = evidence.registration_effect(token, registration)
                    rows += [('publication_intent', token, dict(plan=registration, accepted=True, outcome='committed')),
                             ('publication_attestation', evidence.attestation(attestation), attestation)]
                rows += [('publication_census', 'v1', census)]
                db.execute('DELETE FROM records')
                db.executemany('INSERT INTO records VALUES (?,?,?,0)',
                               [(kind, key, evidence.compact(value).decode()) for kind, key, value in rows])
                db.commit()
            marker = dict(version=1, phase='final', census=census, initialization_intent=initial,
                          database_identity=binding['database_identity'], writer_identity=binding['writer_identity'])
            self.marker = self.writer.root / 'publication-v1.json'
            self.marker.write_bytes(evidence.compact(marker)); self.marker.chmod(0o600)

    def check(self, owner=None, **kwargs):
        with self.writer.hold():
            return self.authority.check(self.candidate, owner or self.owner, **kwargs)

    def sql(self, statement, parameters=()):
        with closing(sqlite3.connect(self.catalog)) as db:
            db.execute(statement, parameters); db.commit()

    def test_correct_copy_is_allowed_with_complete_fresh_facts(self):
        result = self.check()
        self.assertEqual(result['authority']['decision'], 'allowed')
        self.assertEqual(result['authority']['observed'][0]['catalog']['path'], '/native-comics/correct.cbz')
        self.assertEqual(result['inventory']['source_sha256'], hashlib.sha256(self.candidate.read_bytes()).hexdigest())

    def test_known_wrong_owner_retains_all_files_and_authority(self):
        before = [path.read_bytes() for path in (self.source, self.candidate, self.workflow, self.marker)]
        with self.assertRaises(Unavailable): self.check(self.rejected)
        self.assertEqual(before, [path.read_bytes() for path in (self.source, self.candidate, self.workflow, self.marker)])

    def test_genuinely_different_payload_remains_eligible(self):
        self.archive('candidate.cbz', [('01.jpg', b'different')])
        self.assertEqual(self.check(self.rejected)['authority']['decision'], 'unknown')

    def test_empty_initialized_registry_preserves_eligibility(self):
        self.seed(empty=True)
        self.assertEqual(self.check(self.rejected)['authority']['decision'], 'unknown')

    def test_missing_marker_or_attestation_cannot_become_unknown(self):
        for missing in ('marker', 'attestation'):
            self.seed()
            if missing == 'marker': self.marker.unlink()
            else:
                with closing(sqlite3.connect(self.workflow)) as db:
                    db.execute("DELETE FROM records WHERE kind='publication_attestation'"); db.commit()
            before = self.workflow.read_bytes()
            with self.subTest(missing=missing), self.assertRaises(Unavailable): self.check()
            self.assertEqual(self.workflow.read_bytes(), before)

    def test_same_revision_status_path_and_payload_drift_hold(self):
        advisory = self.check()['authority']
        for change in ('status', 'path', 'payload'):
            self.sql('UPDATE issues SET Status=?,Location=?', ('Downloaded', 'correct.cbz'))
            self.archive('correct.cbz', [('01.jpg', b'one')])
            if change == 'status': self.sql("UPDATE issues SET Status='Wanted'")
            elif change == 'path':
                self.archive('moved.cbz', [('01.jpg', b'one')])
                self.sql("UPDATE issues SET Location='moved.cbz'")
            else: self.archive('correct.cbz', [('01.jpg', b'changed')])
            with self.subTest(change=change), self.assertRaises(Unavailable): self.check(advisory=advisory)

    def test_deleted_locationless_annual_shadow_holds(self):
        self.sql('INSERT INTO annuals VALUES (?,?,?,?,?,?)', ('123','456','789',None,'Skipped',1))
        with self.assertRaises(Unavailable): self.check()

    def test_foreign_row_physical_alias_holds(self):
        os.link(self.source, self.library / 'alias.cbz')
        self.sql('INSERT INTO issues VALUES (?,?,?,?)', ('222','456','alias.cbz','Skipped'))
        with self.assertRaises(Unavailable): self.check()

    def test_unclaimed_backup_hardlink_is_not_a_foreign_owner(self):
        os.link(self.source, self.root / 'backup.payload')
        self.assertEqual(self.check()['authority']['decision'], 'allowed')

    def test_exact_advisory_matches_but_protocol_or_census_change_holds(self):
        advisory = self.check()['authority']
        self.assertEqual(self.check(advisory=advisory)['authority'], advisory)
        for key, value in (('version', True), ('decision', 'unknown'), ('census', {})):
            changed = dict(advisory, **{key: value})
            with self.subTest(key=key), self.assertRaises(Unavailable): self.check(advisory=changed)

    def test_source_change_during_observation_holds(self):
        original = evidence.observe_owners
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            self.archive('candidate.cbz', [('01.jpg', b'changed')])
            return result
        with patch.object(evidence, 'observe_owners', side_effect=changed), self.assertRaises(Unavailable): self.check()

    def test_correct_source_or_catalog_change_after_observation_holds(self):
        for change in ('archive', 'catalog'):
            self.archive('correct.cbz', [('01.jpg', b'one')])
            self.sql("DELETE FROM annuals")
            original = self.authority.admission
            calls = []
            def changed():
                value = original(); calls.append(True)
                if len(calls) == 2:
                    if change == 'archive': self.archive('correct.cbz', [('01.jpg', b'changed')])
                    else: self.sql('INSERT INTO annuals VALUES (?,?,?,?,?,?)', ('123','456','789',None,'Skipped',1))
                return value
            with self.subTest(change=change), patch.object(self.authority, 'admission', side_effect=changed), self.assertRaises(Unavailable):
                self.check()

    def test_sidecar_is_retained_without_sqlite_recovery(self):
        sidecar = Path(str(self.workflow) + '-journal'); sidecar.write_bytes(b'retained')
        before = self.workflow.read_bytes()
        with self.assertRaises(Unavailable): self.check()
        self.assertEqual(self.workflow.read_bytes(), before); self.assertEqual(sidecar.read_bytes(), b'retained')

    def test_missing_or_different_writer_mount_holds(self):
        other = Writer(self.root / 'other-writer', create=True)
        authority = Authority(self.config, other,
            [dict(native='/native-comics',worker=str(self.library))], tool_root=self.tool)
        with other.hold(), self.assertRaises(Unavailable): authority.check(self.candidate, self.owner)

    def test_no_check_without_outer_writer(self):
        with self.assertRaises(Unavailable): self.authority.check(self.candidate, self.owner)

    def test_pending_native_intent_holds_even_without_its_fence(self):
        path = self.writer.root / 'tagger-publication-v1.json'; path.write_text('retained')
        with self.assertRaises(Unavailable): self.check()
        self.assertEqual(path.read_text(), 'retained')

    def test_missing_correct_archive_and_catalog_journal_hold(self):
        self.source.unlink()
        with self.assertRaises(Unavailable): self.check()
        self.archive('correct.cbz', [('01.jpg', b'one')])
        journal = Path(str(self.catalog) + '-journal'); journal.write_bytes(b'retained')
        before = self.catalog.read_bytes()
        with self.assertRaises(Unavailable): self.check()
        self.assertEqual(self.catalog.read_bytes(), before); self.assertEqual(journal.read_bytes(), b'retained')

    def test_unreadable_candidate_never_becomes_unknown(self):
        self.candidate.write_bytes(b'unsupported complete inventory')
        with self.assertRaises(Unavailable): self.check(self.rejected)
        self.assertEqual(self.candidate.read_bytes(), b'unsupported complete inventory')

    def test_deep_native_root_maps_without_native_mount_creation(self):
        root = Path('/native-only/deep/media/comics')
        authority = Authority(self.config, self.writer,
            [dict(native=str(root), worker=str(self.library))], tool_root=self.tool)
        self.sql('UPDATE comics SET ComicLocation=?', (str(root),))
        with self.writer.hold():
            result = authority.check(self.candidate, self.owner)
        self.assertEqual(result['authority']['observed'][0]['catalog']['path'], str(root / 'correct.cbz'))

    def test_linked_correct_archive_is_retained(self):
        self.source.rename(self.library / 'original.payload')
        self.source.symlink_to(self.library / 'original.payload')
        with self.assertRaises(Unavailable): self.check()
        self.assertTrue(self.source.is_symlink())

    def test_pending_worker_recovery_requires_owned_recovery_lock(self):
        with self.writer.hold(allow_pending=True):
            self.writer.mark_pending()
            self.assertEqual(self.authority.check(self.candidate, self.owner)['authority']['decision'], 'allowed')
        self.assertTrue(self.writer.fenced())

    def test_missing_native_tables_hold_all_row_observation(self):
        self.sql('DROP TABLE annuals')
        with self.assertRaises(Unavailable): self.check()

    def test_mapping_is_explicit_and_nonoverlapping(self):
        for mappings in ([], [dict(native='/native-comics',worker=str(self.library))]*2,
                         [dict(native='relative',worker=str(self.library))]):
            with self.subTest(mappings=mappings), self.assertRaises(Unavailable):
                Authority(self.config, self.writer, mappings)

    def test_portable_native_payload_vector(self):
        source = self.archive('vector.cbz', [('01.jpg',b'one'), ('10.png',b'ten'),
            ('provenance/ComicInfo.xml',b'private'), ('ComicInfo.xml',b'<ComicInfo/>')])
        result = evidence.inventory(source, tool_root=self.tool)
        self.assertEqual(result['payload'], '82367ae669301a8f9af31fab7e1ff5ce132d8cf212b61d0c414c05a4a88b6d9b')
        before = source.read_bytes()
        self.assertEqual(result['pages'], ['01.jpg', '10.png'])
        self.assertEqual(source.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
