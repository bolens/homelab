"""Real files and SQLite prove pack transitions and native publisher recovery."""
import copy
from contextlib import closing
import importlib
import os
from pathlib import Path
import sqlite3
import tempfile
import shutil
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

import pack_bindings as bindings
import tagger_adapter as base
from tagger_pack import Publisher
from workflow_store import Store
from test_tagger_nfs import saved
from media_writer import Writer
import tagger_supplement


class BindingsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root/'comic.cbz'
        with zipfile.ZipFile(self.source, 'w') as archive:
            archive.writestr('001.png', b'original page')
        self.store = Store(self.root)
        self.digest = base.fingerprint(self.source)
        self.catalog_owner = {'issueid': '1', 'comicid': '2'}
        with closing(sqlite3.connect(self.root/'mylar.db')) as db, db:
            db.executescript('CREATE TABLE comics(ComicID, ComicLocation);'
                             'CREATE TABLE issues(IssueID,ComicID,Location,Status,Deleted);'
                             'CREATE TABLE annuals(IssueID,ComicID,Location,Status,Deleted);')
            db.execute('INSERT INTO comics VALUES (?,?)', ('2', str(self.root)))
            db.execute('INSERT INTO issues VALUES (?,?,?,?,?)', ('1', '2', self.source.name, 'Downloaded', 0))
        for key in ('a'*64, 'b'*64, 'c'*64):
            self.store.set('pack', key, dict(id=key, phase='confirmed', inventory_complete=True,
                cleanup_complete=True, members=[dict(id='d'*64, kind='issue', phase='confirmed',
                    issueid='1', comicid='2', destination=str(self.source),
                    destination_sha256=self.digest, signature=bindings.signature(self.source)),
                    dict(id='e'*64, kind='sidecar', phase='preserved', sidecar='private original credits')]))

    def records(self):
        return self.store.active('pack', {'confirmed'})

    def test_supplement_admission_ignores_read_access_time_only(self):
        writer = Writer(self.root/'media-writer', create=True)
        database = self.root/'workflow.sqlite'
        original_stat = Path.stat
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_uid', 'st_gid',
                  'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_atime_ns')
        for changed in fields:
            with self.subTest(changed=changed):
                calls = []
                def observed(path, *args, **kwargs):
                    value = original_stat(path, *args, **kwargs)
                    if path != database or kwargs.get('follow_symlinks') is False:
                        return value
                    calls.append(value)
                    if len(calls) == 1:
                        return value
                    result = {name:getattr(value, name) for name in fields}
                    result[changed] += 1
                    return SimpleNamespace(**result)
                with patch.object(Path, 'stat', observed):
                    # Older pathlib uses stat(follow_symlinks=False) for is_symlink.
                    database.stat(follow_symlinks=False)
                    if changed == 'st_atime_ns':
                        tagger_supplement.publication_review(writer)
                    else:
                        with self.assertRaisesRegex(ValueError, 'authority changed'):
                            tagger_supplement.publication_review(writer)

    def test_same_path_metadata_rewrite_rebinds_three_packs_and_replays(self):
        before = self.records()
        publisher = Publisher(self.root/'journal', self.root)
        with patch.object(base, 'save', side_effect=saved):
            self.assertEqual(publisher.tag(self.source, {'series':'Fixture'}, token='f'*32).state, 'committed')
        digest = base.fingerprint(self.source)
        self.assertNotEqual(digest, self.digest)
        for original, record in zip(before, self.records()):
            self.assertEqual(record['members'][1], original['members'][1])
            self.assertEqual(record['members'][0]['signature'], bindings.signature(self.source))
            self.assertEqual(record['members'][0]['destination_sha256'], digest)
            self.assertTrue(record['inventory_complete'] and record['cleanup_complete'])
        self.assertEqual(publisher.recover('f'*32).state, 'committed')
        self.assertEqual(len(list(self.root.glob('.mylar-tag-*'))), 0)

    def test_standalone_combined_supplement_uses_bound_native_hook_and_clears_fence(self):
        with zipfile.ZipFile(self.source, 'w') as archive:
            archive.writestr('001.png', b'original page')
            archive.writestr('ComicInfo.xml', '<ComicInfo><Series>Fixture</Series><Publisher>DC</Publisher></ComicInfo>')
        self.digest = base.fingerprint(self.source)
        for record in self.records():
            record['members'][0].update(destination_sha256=self.digest, signature=bindings.signature(self.source))
            self.store.set('pack', record['id'], record)
        writer = Writer(self.root/'media-writer', create=True)
        mylar = ModuleType('mylar'); mylar.__path__ = [str(Path(__file__).parent)]
        with patch.dict(sys.modules, {'mylar': mylar}):
            importlib.import_module('mylar.tagger_native').state(writer)
        publisher = tagger_supplement.bound_publisher(writer)
        copies = self.root/'copies'; copies.mkdir(mode=0o700)
        original, restored = copies/'original.cbz', copies/'restored.cbz'
        shutil.copy2(self.source, original); shutil.copy2(original, restored)
        result = tagger_supplement.apply_preserved(self.source, {'LanguageISO':'en'}, writer,
                    publisher, original, restored, self.digest, 'f'*32)
        self.assertEqual(result['state'], 'committed')
        self.assertFalse(writer.fenced(tagger=True))
        self.assertTrue(original.exists() and restored.exists())
        self.assertTrue(all(r['members'][0]['destination_sha256'] == base.fingerprint(self.source) for r in self.records()))

    def test_crash_after_pack_commit_replays_without_refreshing_foreign_members(self):
        publisher = Publisher(self.root/'journal', self.root)
        finalize = bindings.finalize
        def commit_then_interrupt(*args, **kwargs):
            finalize(*args, **kwargs)
            raise SystemExit(71)
        with patch.object(base, 'save', side_effect=saved), patch.object(bindings, 'finalize', side_effect=commit_then_interrupt):
            with self.assertRaises(SystemExit): publisher.tag(self.source, {'series':'Fixture'}, token='f'*32)
        accepted = self.records()
        self.assertEqual(publisher.read('f'*32)['state'], 'publishing')
        self.assertEqual(publisher.recover('f'*32).state, 'committed')
        self.assertEqual(self.records(), accepted)

    def test_missing_catalog_owner_stale_hash_and_hardlink_are_rejected(self):
        with closing(sqlite3.connect(self.root/'mylar.db')) as db, db:
            db.execute("UPDATE issues SET ComicID='9'")
        with self.assertRaises(ValueError): bindings.capture(self.store, self.source, self.source)
        with self.assertRaises(ValueError): bindings.capture(self.store, self.source, self.source, catalog_owner={'issueid':'1','comicid':'9'})
        linked = self.root/'other.cbz'
        os.link(self.source, linked)
        with self.assertRaises(ValueError): bindings.capture(self.store, self.source, self.source, catalog_owner=self.catalog_owner)

    def test_changed_member_blocks_all_pack_updates(self):
        intent = bindings.capture(self.store, self.source, self.source)
        record = self.store.get('pack', 'c'*64)
        record['members'][0]['comicid'] = '99'
        self.store.set('pack', 'c'*64, record)
        before = self.records()
        with self.assertRaises(ValueError): bindings.finalize(self.store, intent, self.digest)
        self.assertEqual(self.records(), before)

    def test_matching_pack_report_added_after_capture_uses_original_exact_proof(self):
        intent=bindings.capture(self.store,self.source,self.source)
        record=copy.deepcopy(self.store.get('pack','a'*64));record['id']='9'*64
        self.store.set('pack',record['id'],record)
        linked=self.root/'temporary.cbz';os.link(self.source,linked);linked.unlink()
        bindings.finalize(self.store,intent,self.digest)
        self.assertEqual(len(self.records()),4)
        self.assertTrue(all(r['members'][0]['signature']==bindings.signature(self.source) for r in self.records()))

    def test_database_failure_rolls_back_every_pack_and_retry_is_idempotent(self):
        intent = bindings.capture(self.store, self.source, self.source)
        linked = self.root/'other.cbz'
        os.link(self.source, linked); linked.unlink()
        before = self.records()
        with self.store.connection() as db:
            db.execute("CREATE TRIGGER reject_binding BEFORE UPDATE ON records WHEN NEW.key='c"+'c'*63+"' BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(sqlite3.IntegrityError): bindings.finalize(self.store, intent, self.digest)
        self.assertEqual(self.records(), before)
        with self.store.connection() as db: db.execute('DROP TRIGGER reject_binding')
        bindings.finalize(self.store, intent, self.digest)
        accepted = self.records()
        bindings.finalize(self.store, intent, self.digest)
        self.assertEqual(self.records(), accepted)

    def test_interrupted_publisher_retains_copies_and_recovers_without_tagger_replay(self):
        publisher = Publisher(self.root/'journal', self.root)
        def interrupt(stage):
            if stage == 'after_exchange': raise SystemExit(71)
        with patch.object(base, 'save', side_effect=saved) as tagger, patch.object(base, '_checkpoint', side_effect=interrupt):
            with self.assertRaises(SystemExit):
                publisher.tag(self.source, {'series':'Fixture'}, token='f'*32)
            self.assertEqual(tagger.call_count, 1)
        record = publisher.read('f'*32)
        self.assertFalse(record['cleaned'])
        self.assertEqual(record['state'], 'publishing')
        with patch.object(base, 'save', side_effect=AssertionError('must not replay')):
            self.assertEqual(publisher.recover('f'*32).state, 'committed')
        self.assertTrue(all(r['members'][0]['destination_sha256'] == base.fingerprint(self.source) for r in self.records()))

    def test_unconfirmed_and_foreign_path_members_are_never_promoted(self):
        record = self.store.get('pack', 'a'*64)
        other = copy.deepcopy(record['members'][0]); other.update(id='9'*64, phase='review')
        record['members'].append(other); self.store.set('pack', 'a'*64, record)
        intent = bindings.capture(self.store, self.source, self.source)
        bindings.finalize(self.store, intent, self.digest)
        self.assertEqual(self.store.get('pack', 'a'*64)['members'][-1], other)

    def test_malformed_intent_and_changed_content_do_not_refresh_evidence(self):
        intent = bindings.capture(self.store, self.source, self.source)
        malformed = copy.deepcopy(intent); malformed['bindings'][0]['before']['phase'] = 'review'
        before = self.records()
        with self.assertRaises(ValueError): bindings.finalize(self.store, malformed, self.digest)
        self.source.write_bytes(b'foreign replacement')
        with self.assertRaises(ValueError): bindings.finalize(self.store, intent, self.digest)
        self.assertEqual(self.records(), before)


if __name__ == '__main__':
    unittest.main()
