"""Verified-receipt transaction fixtures; no Docker or operational lifecycle."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time
import unittest


SPEC = importlib.util.spec_from_file_location('calibre_catalog_sync', Path(__file__).parents[1] / 'calibre-catalog-sync.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Planner:
    def __init__(self, candidates):
        self.candidates = candidates

    def plan(self, library):
        return {'candidates': self.candidates, 'counts': {'candidateBooks': len(self.candidates)}}


class Runtime:
    apply_calls = 0
    mode = 'success'

    def __init__(self, container, library, log):
        self.library = library

    def prepare(self, backup, incoming, workspace):
        self.rehearsal = workspace / 'rehearsal'
        shutil.copytree(backup, self.rehearsal, copy_function=shutil.copy2)
        self.incoming = incoming
        return MODULE.inventory(self.rehearsal)

    def import_into(self, library, fail=False):
        connection = sqlite3.connect(library / 'metadata.db')
        try:
            identifier = 2
            for path in sorted(self.incoming.iterdir()):
                relative = f'Author/New Work ({identifier})'
                directory = library / relative
                directory.mkdir(parents=True)
                shutil.copy2(path, directory / 'new.epub')
                (directory / 'metadata.opf').write_text('new metadata')
                connection.execute('INSERT INTO books VALUES(?,?,?,?)', (identifier, 'New Work', relative, 'new-uuid'))
                connection.execute('INSERT INTO data VALUES(?,?,?,?)', (identifier, identifier, 'new', 'EPUB'))
                connection.commit()
                identifier += 1
                if fail:
                    raise MODULE.Refused('fixture_import_failure')
        finally:
            connection.close()

    def rehearse(self, workspace):
        self.import_into(self.rehearsal)
        if self.mode == 'rehearsal_changes_old_media':
            (self.rehearsal / 'Original' / 'old.epub').write_bytes(b'changed')
        if self.mode == 'rehearsal_changes_old_rows':
            with contextlib.closing(sqlite3.connect(self.rehearsal / 'metadata.db')) as connection:
                connection.execute("UPDATE books SET title='Changed' WHERE id=1")
                connection.commit()
        return MODULE.snapshot_database(self.rehearsal / 'metadata.db'), MODULE.inventory(self.rehearsal)

    def apply(self):
        Runtime.apply_calls += 1
        if self.mode == 'live_changes_old_media':
            self.import_into(self.library)
            (self.library / 'Original' / 'old.epub').write_bytes(b'changed')
            raise MODULE.Refused('fixture_import_failure')
        self.import_into(self.library, fail=self.mode == 'partial_live_failure')
        if self.mode == 'unexpected_new_namespace':
            (self.library / 'unrelated-new-file').write_text('requires investigation')

    def close(self):
        pass


class CalibreCatalogSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.library = self.root / 'library'
        self.library.mkdir()
        original = self.library / 'Original'
        original.mkdir()
        (original / 'old.epub').write_bytes(b'original-format')
        (original / 'metadata.opf').write_bytes(b'original-metadata')
        loose = self.library / 'Loose'
        loose.mkdir()
        self.source = loose / 'private-title.epub'
        self.source.write_bytes(b'candidate-format')
        self.sha = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.planner = Planner([{'path': str(self.source), 'sha256': self.sha, 'format': 'EPUB'}])
        database = self.library / 'metadata.db'
        with contextlib.closing(sqlite3.connect(database)) as connection:
            connection.executescript('CREATE TABLE books(id INTEGER PRIMARY KEY,title TEXT,path TEXT,uuid TEXT); '
                                     'CREATE TABLE data(id INTEGER PRIMARY KEY,book INTEGER,name TEXT,format TEXT);')
            connection.execute('INSERT INTO books VALUES(1,?,?,?)', ('Old Work', 'Original', 'preserved-uuid'))
            connection.execute('INSERT INTO data VALUES(1,1,?,?)', ('old', 'EPUB'))
            connection.commit()
        database.chmod(0o664)
        self.private = self.root / 'private'
        self.private.mkdir(mode=0o700)
        self.backup = self.private / 'books'
        shutil.copytree(self.library, self.backup, copy_function=shutil.copy2)
        self.inventory = MODULE.inventory(self.library)
        self.inventory_path = self.private / 'inventory.json'
        self.inventory_path.write_text(json.dumps({'books': self.inventory}))
        self.inventory_path.chmod(0o600)
        self.receipt_path = self.private / 'receipt.json'
        self.receipt = {'version': 1, 'status': 'verified', 'quiesced': True, 'createdAtUnix': time.time(),
                        'libraryPath': str(self.library), 'backupPath': str(self.backup),
                        'baselineDatabasePath': str(self.backup / 'metadata.db'),
                        'inventoryPath': str(self.inventory_path), 'expectedCandidateHashes': [self.sha]}
        self.write_receipt()
        Runtime.mode = 'success'
        Runtime.apply_calls = 0

    def tearDown(self):
        self.temp.cleanup()

    def write_receipt(self):
        self.receipt_path.write_text(json.dumps(self.receipt))
        self.receipt_path.chmod(0o600)

    def sync(self):
        return MODULE.sync_catalog(self.library, self.planner, self.receipt_path, runtime_factory=Runtime)

    def test_success_preserves_old_catalog_rows_and_every_original_media_file(self):
        result = self.sync()
        self.assertEqual(result['status'], 'applied')
        self.assertEqual(result['counts'], {'addedBooks': 1, 'preservedBooks': 1})
        MODULE.originals_preserved(self.inventory, MODULE.inventory(self.library), catalog_changes=True)
        self.assertEqual(Runtime.apply_calls, 1)
        self.assertEqual(MODULE.snapshot_database(self.library / 'metadata.db')['books']['rows'][0],
                         [1, 'Old Work', 'Original', 'preserved-uuid'])

    def test_stale_unverified_unquiesced_or_wrong_candidates_never_apply(self):
        for field, value in (('createdAtUnix', time.time() - 601), ('status', 'copied'),
                             ('quiesced', False), ('expectedCandidateHashes', ['0' * 64])):
            with self.subTest(field=field):
                original = self.receipt[field]
                self.receipt[field] = value
                self.write_receipt()
                with self.assertRaises(MODULE.Refused):
                    self.sync()
                self.receipt[field] = original
                self.assertEqual(Runtime.apply_calls, 0)

    def test_changed_source_or_incomplete_backup_never_apply(self):
        (self.backup / 'Original' / 'old.epub').unlink()
        with self.assertRaises(MODULE.Refused):
            self.sync()
        self.assertEqual(Runtime.apply_calls, 0)

    def test_rehearsal_original_media_or_row_change_prevents_live_apply(self):
        for mode in ('rehearsal_changes_old_media', 'rehearsal_changes_old_rows'):
            Runtime.mode = mode
            with self.assertRaises(MODULE.Refused):
                self.sync()
            self.assertEqual(Runtime.apply_calls, 0)
            MODULE.originals_preserved(self.inventory, MODULE.inventory(self.library))

    def test_partial_import_rolls_back_database_and_only_proven_new_files(self):
        Runtime.mode = 'partial_live_failure'
        result = self.sync()
        self.assertEqual(result['status'], 'rolled_back')
        self.assertEqual(MODULE.inventory(self.library), self.inventory)
        self.assertFalse((self.library / 'Author').exists())

    def test_changed_original_media_is_not_misreported_as_verified_rollback(self):
        Runtime.mode = 'live_changes_old_media'
        with self.assertRaises(MODULE.NeedsRecovery):
            self.sync()
        self.assertEqual((self.library / 'Original' / 'old.epub').read_bytes(), b'changed')
        self.assertTrue((self.backup / 'Original' / 'old.epub').is_file())
        self.assertTrue(list(self.private.glob('catalog-sync.*/native.log')))

    def test_unexpected_new_namespace_requires_recovery_without_deleting_it(self):
        Runtime.mode = 'unexpected_new_namespace'
        with self.assertRaises(MODULE.NeedsRecovery):
            self.sync()
        self.assertTrue((self.library / 'unrelated-new-file').exists())

    def test_faithful_permissive_database_mode_is_allowed_only_inside_private_backup(self):
        (self.library / 'metadata.db').chmod(0o766)
        (self.backup / 'metadata.db').chmod(0o766)
        self.inventory = MODULE.inventory(self.library)
        self.inventory_path.write_text(json.dumps({'books': self.inventory}))
        MODULE.load_receipt(self.receipt_path, self.library)
        self.assertEqual((self.library / 'metadata.db').stat().st_mode & 0o777, 0o766)
        self.assertEqual((self.backup / 'metadata.db').stat().st_mode & 0o777, 0o766)
        self.private.chmod(0o755)
        with self.assertRaises(MODULE.Refused):
            MODULE.load_receipt(self.receipt_path, self.library)

    def test_private_receipt_and_parent_permissions_are_required(self):
        self.receipt_path.chmod(0o644)
        with self.assertRaises(MODULE.Refused):
            self.sync()
        self.receipt_path.chmod(0o600)
        self.private.chmod(0o755)
        with self.assertRaises(MODULE.Refused):
            self.sync()
        self.assertEqual(Runtime.apply_calls, 0)

    def test_backup_database_probe_is_immutable_and_rejects_active_wal(self):
        before = set(self.backup.iterdir())
        MODULE.snapshot_database(self.backup / 'metadata.db')
        self.assertEqual(before, set(self.backup.iterdir()))
        (self.backup / 'metadata.db-wal').write_bytes(b'active')
        with self.assertRaisesRegex(MODULE.Refused, 'active_wal'):
            MODULE.snapshot_database(self.backup / 'metadata.db')

    def test_count_only_cli_plan_and_missing_receipt_never_emit_source_titles(self):
        fake = self.root / 'calibre-catalog-import'
        fake.write_text('def plan(path): return {"counts": {"candidateBooks": 1}}\n')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = MODULE.main([str(self.library), '--planner', str(fake)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue()), {'status': 'planned', 'counts': {'candidateBooks': 1}})
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = MODULE.main([str(self.library), '--planner', str(fake), '--apply'])
        self.assertEqual(code, 1)
        self.assertNotIn('private-title', output.getvalue())

    def test_backup_nfs_acl_exception_requires_verified_roundtrip_and_keeps_other_attrs(self):
        import copy
        original = copy.deepcopy(self.inventory)
        original['metadata.db']['attrs']['system.nfs4_acl'] = 'YWNs'
        MODULE.originals_preserved(original, self.inventory, backup=True, nfs_verified=True)
        with self.assertRaises(MODULE.Refused):
            MODULE.originals_preserved(original, self.inventory, backup=True)
        original['metadata.db']['attrs']['user.example'] = 'dmFsdWU='
        with self.assertRaises(MODULE.Refused):
            MODULE.originals_preserved(original, self.inventory, backup=True, nfs_verified=True)

    def test_source_drift_and_unmanaged_path_collision_prevent_apply(self):
        self.source.write_bytes(b'changed-source')
        with self.assertRaises(MODULE.Refused):
            self.sync()
        self.assertEqual(Runtime.apply_calls, 0)
        original = MODULE.snapshot_database(self.backup / 'metadata.db')
        after = json.loads(json.dumps(original))
        after['books']['rows'].append([2, 'Collision', 'Loose', 'new-uuid'])
        after['data']['rows'].append([2, 2, 'private-title', 'EPUB'])
        with self.assertRaisesRegex(MODULE.Refused, 'path_collision'):
            MODULE.verify_added(original, after, self.inventory, self.inventory, [self.sha])

    def test_native_add_passes_canonical_isbn_per_known_edition_without_automerge(self):
        runtime = MODULE.ContainerRuntime('fixture', self.library, io.BytesIO())
        runtime.remote = '/tmp/calibre-catalog-sync.fixture'
        known = 'a' * 64
        unknown = 'b' * 64
        runtime.inputs = [runtime.remote + '/incoming/' + value + '.epub' for value in (known, unknown)]
        runtime.candidate_isbns = {known: ['9780306406157'], unknown: []}
        commands = []
        runtime.execute = lambda args: commands.append(args)
        runtime.import_into('/books')
        prefix = ['calibre-debug', '-e', runtime.remote + '/calibredb-preserve-trash.py', '--',
                  'add', '--with-library', '/books']
        self.assertEqual(commands, [prefix + ['--isbn', '9780306406157', '--', runtime.inputs[0]],
                                    prefix + ['--', runtime.inputs[1]]])
        self.assertFalse(any('--automerge' in command for command in commands))
        commands.clear()
        runtime.import_into(runtime.remote + '/rehearsal')
        self.assertEqual([command[-1] for command in commands], runtime.inputs)
        self.assertEqual(commands[0][commands[0].index('--isbn') + 1], '9780306406157')

    def test_imported_isbn_matches_source_edition_using_planner_canonicalizer(self):
        planner = MODULE.load_planner(Path(__file__).parents[1] / 'calibre-catalog-import.py')
        before = MODULE.snapshot_database(self.backup / 'metadata.db')
        runtime = Runtime('fixture', self.library, None)
        incoming = self.private / 'incoming'
        incoming.mkdir()
        shutil.copy2(self.source, incoming / (self.sha + '.epub'))
        runtime.incoming = incoming
        runtime.import_into(self.library)
        after = MODULE.snapshot_database(self.library / 'metadata.db')
        current = MODULE.inventory(self.library)
        expected = {self.sha: ['9780306406157']}
        after['identifiers'] = {'columns': ['book', 'type', 'val'], 'rows': [[2, 'isbn', '0306406152']]}
        MODULE.verify_added(before, after, self.inventory, current, [self.sha], expected, planner.isbn)
        for value in ('9780140328721', None):
            after['identifiers']['rows'] = [[2, 'isbn', value]] if value else []
            with self.assertRaisesRegex(MODULE.Refused, 'isbn_not_preserved'):
                MODULE.verify_added(before, after, self.inventory, current, [self.sha], expected, planner.isbn)

    def test_cli_failure_keeps_exception_chain_in_fresh_private_log_only(self):
        planner = self.root / 'calibre-catalog-import'
        planner.write_text('raise RuntimeError("fixture private cause")\n')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = MODULE.main([str(self.library), '--planner', str(planner), '--apply',
                                '--receipt', str(self.receipt_path)])
        self.assertEqual(code, 1)
        self.assertNotIn('fixture private cause', output.getvalue())
        logs = list(self.private.glob('catalog-sync-failure.*/failure.log'))
        self.assertEqual(len(logs), 1)
        self.assertIn('fixture private cause', logs[0].read_text())
        self.assertEqual(logs[0].stat().st_mode & 0o777, 0o600)
        self.assertEqual(logs[0].parent.stat().st_mode & 0o777, 0o700)
        error = ValueError('another private cause')
        self.assertTrue(MODULE.record_private_failure(self.receipt_path, error))
        self.assertEqual(len(list(self.private.glob('catalog-sync-failure.*/failure.log'))), 2)

    def test_private_failure_logging_refuses_untrusted_paths_without_writes(self):
        for change in ('public_parent', 'public_receipt', 'missing_receipt', 'symlink', 'git_parent'):
            with self.subTest(change=change):
                parent = self.root / change
                parent.mkdir(mode=0o700)
                receipt = parent / 'receipt.json'
                receipt.write_text('{}')
                receipt.chmod(0o600)
                if change == 'public_parent':
                    parent.chmod(0o755)
                elif change == 'public_receipt':
                    receipt.chmod(0o644)
                elif change == 'missing_receipt':
                    receipt.unlink()
                elif change == 'symlink':
                    receipt.unlink()
                    receipt.symlink_to(self.receipt_path)
                elif change == 'git_parent':
                    (parent / '.git').touch()
                before = set(parent.iterdir())
                self.assertFalse(MODULE.record_private_failure(receipt, RuntimeError('private')))
                self.assertEqual(set(parent.iterdir()), before)

    def test_backup_transfer_streams_open_archive_without_loading_library_into_memory(self):
        log = tempfile.TemporaryFile()
        self.addCleanup(log.close)
        runtime = MODULE.ContainerRuntime('fixture', self.library, log)
        captured = []
        def run(args, *, data=None, stream=None):
            self.assertIsNone(data)
            self.assertIsNotNone(stream)
            self.assertFalse(stream.closed)
            self.assertGreater(os.fstat(stream.fileno()).st_size, 0)
            captured.append(args)
            while stream.read(65536):
                pass
            return b''
        runtime.run = run
        runtime.transfer(self.backup, '/tmp/fixture', self.private, True)
        self.assertEqual(captured[0][:6], ['docker', 'exec', '--user', '0', '-i', 'fixture'])
        self.assertFalse((self.private / 'transfer.tar').exists())

    def test_native_wrapper_suppresses_trash_for_process_lifetime_without_preferences_write(self):
        self.assertIn('DB.expire_old_trash = lambda', MODULE.WRAPPER)
        self.assertNotIn('expire_old_trash_after', MODULE.WRAPPER)
        self.assertNotIn('--automerge', MODULE.WRAPPER)


if __name__ == '__main__':
    unittest.main()
