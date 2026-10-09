"""Fake SDK five bindings test ONLY pending PREPARE; no native authority proof."""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('negative_batch_fixture', str(_PORTABLE_ROOT / 'publication_negative_batch.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Tests(unittest.TestCase):

    def setUp(self):
        self.t = tempfile.TemporaryDirectory(prefix='negative-batch-prepare-fixture-')
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.root.chmod(448)
        self.wroot = self.root / 'writer'
        self.wroot.mkdir(mode=448)
        self.lib = self.root / 'library'
        self.lib.mkdir(mode=448)
        self.journal = self.root / 'journal'
        self.journal.mkdir(mode=448)

        def make(p):
            p.write_bytes(b'{}')
            p.chmod(384)
            return p
        self.db = make(self.root / 'workflow.sqlite')
        self.native = make(self.root / 'mylar.db')
        self.lock = make(self.wroot / 'writer-v1.lock')
        make(self.wroot / 'publication-v1.json')

        class Controller:
            pass

        class Writer:
            pass

        class NativeNegativePreparation:

            def revalidate(p):
                return copy.deepcopy(p.binding)

        class Reader:
            core = 'a' * 64

            def revalidate_before_native(r, p):
                pass

            def close_native_phase_passive(r, f):
                pass
        self.controller = Controller()
        self.controller.database = self.db
        self.controller.native_database = self.native
        self.controller.roots = [self.lib]
        self.writer = Writer()
        self.writer.root = self.wroot
        self.writer.lock = self.lock
        self.writer.local = [None, types.SimpleNamespace(depth=1)]
        self.reader = Reader()
        self.preps = []
        self.census = dict(version=1, epoch='b' * 64, revision=13, keys=[], digest='c' * 64)
        for i in range(5):
            p = make(self.lib / f'wrong-{i}.cbz')
            prep = NativeNegativePreparation()
            prep._external = True
            prep._controller = self.controller
            prep._writer = self.writer
            prep.binding = dict(source=str(p), owner=dict(issueid=str(i)), census=self.census, file_facts={str(p): dict(signature9=m.sig(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())}, complete_catalog_absence=dict(database=dict(signature9=m.sig(self.native)), passive_claim_files={}, passive_claim_ancestors={}, passive_scope_ancestors={}))
            self.preps.append(prep)
        g = types.SimpleNamespace(writer_identity=lambda w: [1, 2, 3, 4], canonical_digest=lambda v: hashlib.sha256(m.encode(v)).hexdigest(), registry_snapshot=lambda *a: (copy.deepcopy(self.census), {}), same_json=lambda a, b: a == b)
        neg = types.SimpleNamespace(NativeNegativePreparation=NativeNegativePreparation, _projection=lambda c: ('fake fixture',))
        self.mods = (types.SimpleNamespace(Controller=Controller), types.SimpleNamespace(Writer=Writer), g, neg, types.SimpleNamespace(StoppedReaderPhase=Reader))

    def make(self):
        return m.NativeBatchPreparation(m._KEY, self.controller, self.writer, self.preps, self.reader, self.journal, 'd' * 64, self.mods)

    def test_single_marker_binds_five_preparations(self):
        b = self.make()
        b.close_prepared()
        body = json.loads((self.wroot / m.NAME).read_text())
        self.assertEqual(body['binding_sha256'], b.core)
        self.assertEqual(len(b.binding['native']), 5)
        self.assertFalse(b.binding['reader_sql_authority'])

    def test_no_boolean_factory(self):
        with self.assertRaises(m.Held):
            m.NativeBatchPreparation(True, self.controller, self.writer, self.preps, self.reader, self.journal, 'd' * 64, self.mods)

    def test_no_installed_modules_public_entry_holds(self):
        with self.assertRaises(m.Held):
            m.prepare_existing(self.controller, self.writer, self.preps, self.reader, self.journal, 'd' * 64)

    def test_no_sql_or_native_terminal_grant(self):
        b = self.make()
        with self.assertRaisesRegex(m.Held, 'before-SQL'):
            b.commit_reader()
        with self.assertRaisesRegex(m.Held, 'before-SQL'):
            b.stage_all()
        with self.assertRaisesRegex(m.Held, 'fence-retained'):
            b.terminal()
        self.assertTrue((self.wroot / m.NAME).exists())

    def test_duplicate_owner_held_before_marker(self):
        self.preps[1].binding['owner'] = self.preps[0].binding['owner']
        with self.assertRaises(m.Held):
            self.make()
        self.assertFalse((self.wroot / m.NAME).exists())

    def test_catalog_callback_change_held_before_marker(self):
        old = self.mods[2].registry_snapshot

        def changed(*a):
            value = old(*a)
            self.native.write_bytes(b'foreign')
            return value
        self.mods[2].registry_snapshot = changed
        with self.assertRaises(m.Held):
            self.make()
        self.assertFalse((self.wroot / m.NAME).exists())

    def test_last_reader_callback_original_drift_holds(self):
        b = self.make()
        p = Path(self.preps[0].binding['source'])
        self.reader.close_native_phase_passive = lambda f: p.write_bytes(b'foreign')
        with self.assertRaises(m.Held):
            b.close_prepared()
        self.assertTrue((self.wroot / m.NAME).exists())

    def test_last_reader_callback_journal_foreignchild_holds(self):
        b = self.make()
        self.reader.close_native_phase_passive = lambda f: (self.journal / 'foreign').write_bytes(b'foreign')
        with self.assertRaises(m.Held):
            b.close_prepared()

    def test_last_reader_callback_native_sidecar_absence_holds(self):
        for database_name in ('database', 'native_database'):
            with self.subTest(database=database_name):
                b = self.make()
                database = getattr(self.controller, database_name)
                self.reader.close_native_phase_passive = lambda f: Path(str(database) + '-wal').write_bytes(b'late-sidecar')
                with self.assertRaisesRegex(m.Held, 'database-companion'):
                    b.close_prepared()
                Path(str(database) + '-wal').unlink()
                self.reader.close_native_phase_passive = lambda f: None
                (self.wroot / m.NAME).unlink()

    def test_marker_replacement_held(self):
        b = self.make()
        p = self.wroot / m.NAME
        raw = p.read_bytes()
        p.unlink()
        p.write_bytes(raw)
        p.chmod(384)
        with self.assertRaises(m.Held):
            b.close_prepared()

    def test_core_binding_reseal_held(self):
        b = self.make()
        b.bound[0]['owner'] = {'issueid': 'foreign'}
        with self.assertRaises(m.Held):
            b.close_prepared()

    def test_foreign_writer_child_held(self):
        b = self.make()
        (self.wroot / 'foreign').write_bytes(b'foreign')
        with self.assertRaises(m.Held):
            b.close_prepared()

    def test_exact_existing_writer_must_be_held(self):
        self.writer.local[1].depth = 0
        with self.assertRaises(m.Held):
            self.make()

    def test_marker_parent_alias_before_relative_write_no_foreign_write(self):
        real = os.open
        foreign = self.root / 'foreign'
        foreign.mkdir(mode=448)
        fired = False

        def replaced(path, *args, **kw):
            nonlocal fired
            if path == m.NAME and (not fired):
                saved = self.root / 'saved-writer'
                self.wroot.rename(saved)
                self.wroot.symlink_to(foreign, target_is_directory=True)
                try:
                    fd = real(path, *args, **kw)
                finally:
                    self.wroot.unlink()
                    saved.rename(self.wroot)
                fired = True
                return fd
            return real(path, *args, **kw)
        with patch.object(os, 'open', side_effect=replaced):
            b = self.make()
        self.assertTrue(fired)
        self.assertEqual(list(foreign.iterdir()), [])
        b.close_prepared()
if __name__ == '__main__':
    unittest.main()
