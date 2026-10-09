"""Real disposable SQLite/Writer/registry/owner observations; ZIP scanner fixture.

Host scanner uses stdlib CRC-checked ZIP, not installed native decoder proof.
"""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import hashlib
import inspect
import os
from pathlib import Path
import shutil
import sqlite3
from contextlib import closing
import sys
import types
import unittest
from unittest.mock import patch
import zipfile
sys.path[:0] = [str(_PORTABLE_ROOT / 'fixtures'), str(_PORTABLE_ROOT)]
import publication_negative_v4 as m
import publication_guard as g
import publication_api as api
import test_publication_api as fixtures

class Controls(unittest.TestCase):
    call = fixtures.NativeProtocolTests.call
    bootstrap = fixtures.NativeProtocolTests.bootstrap

    def setUp(self):
        fixtures.NativeProtocolTests.setUp(self)

        def inventory(path, **kw):
            path = Path(path)
            signature, digest = g.file_hash(path)
            rows = []
            with zipfile.ZipFile(path) as z:
                for info in z.infolist():
                    raw = z.read(info)
                    if info.filename in g.METADATA:
                        g.metadata(info.filename, raw)
                    rows.append(dict(name=info.filename, bytes=len(raw), directory=info.is_dir(), sha256=hashlib.sha256(raw).hexdigest()))
            pages = sorted([x['name'] for x in rows if Path(x['name']).suffix in g.PAGE_EXTENSIONS], key=g.natural_key)
            v = dict(version=1, members=rows, pages=pages, payload=g.token(rows, pages))
            g.validate(v)
            return dict(v, source_signature=signature, source_sha256=digest)
        ctx = patch.object(g, 'inventory', side_effect=inventory)
        ctx.start()
        self.addCleanup(ctx.stop)
        prepared = fixtures.NativeProtocolTests.prepare(self)
        fixtures.NativeProtocolTests.call(self, 'register', token=prepared['token'])
        self.wrong = self.library / 'wrong.cbz'
        shutil.copy2(self.source, self.wrong)
        self.retained = self.root / 'retained.cbz'
        self.restore = self.root / 'restore.cbz'
        for p in (self.retained, self.restore):
            shutil.copy2(self.wrong, p)
        self.runtime = types.SimpleNamespace(owner=lambda: self.writer, active=lambda: True, publication_mode=lambda: True)
        app = types.ModuleType('mylar')
        app.DATA_DIR = str(self.root)
        app.CONFIG = types.SimpleNamespace(DESTINATION_DIR=str(self.library))
        app.native_writers = self.runtime
        ctx = patch.dict(sys.modules, {'mylar': app, 'mylar.publication_api': api})
        ctx.start()
        self.addCleanup(ctx.stop)

    def prepare_negative(self):
        return m.NativeNegativePreparation(self.wrong, self.owner, self.source, self.retained, self.restore)

    def sql(self, s, args=()):
        with closing(sqlite3.connect(self.database)) as db:
            db.execute(s, args)
            db.commit()

    def test_real_native_observation_no_mutation(self):
        before = self.database.read_bytes()
        with self.writer.hold():
            p = self.prepare_negative()
            self.assertTrue(p.binding['native_negative_observation_ready'])
            self.assertFalse(p.binding['mutation_authority'])
            p.revalidate()
        self.assertEqual(before, self.database.read_bytes())

    def test_no_writer(self):
        with self.assertRaises(g.Unavailable):
            self.prepare_negative()

    def test_unowned_wrong_NULL_is_permitted_observation(self):
        self.sql('INSERT INTO comics VALUES (?,?,?)', ('888', str(self.library), 'Active'))
        self.sql('INSERT INTO issues VALUES (?,?,?,?)', ('999', '888', None, 'Snatched'))
        with self.writer.hold():
            self.assertTrue(self.prepare_negative().binding['native_negative_observation_ready'])

    def test_deleted_shadow_source_held(self):
        self.sql('INSERT INTO annuals VALUES (?,?,?,?,?,?)', ('999', '456', '456', 'wrong.cbz', 'Snatched', 1))
        with self.writer.hold(), self.assertRaises(Exception):
            self.prepare_negative()

    def test_orphan_locationless_held(self):
        self.sql('INSERT INTO issues VALUES (?,?,?,?)', ('777', '999', None, 'Wanted'))
        with self.writer.hold(), self.assertRaises(Exception):
            self.prepare_negative()

    def test_correct_original_cannot_be_source(self):
        with self.writer.hold(), self.assertRaises(Exception):
            m.NativeNegativePreparation(self.source, self.owner, self.source, self.retained, self.restore)

    def test_copy_changed(self):
        self.restore.write_bytes(b'foreign')
        with self.writer.hold(), self.assertRaises(g.Unavailable):
            self.prepare_negative()

    def test_mode_changed(self):
        self.restore.chmod(384 if self.restore.stat().st_mode & 511 != 384 else 420)
        with self.writer.hold(), self.assertRaises(g.Unavailable):
            self.prepare_negative()

    def test_reader_boolean_cannot_consume(self):
        with self.writer.hold():
            p = self.prepare_negative()
            with self.assertRaises(g.Unavailable):
                p.consume({'reader_absent': True})

    def test_expired_writer_hold_cannot_revalidate(self):
        with self.writer.hold():
            p = self.prepare_negative()
        with self.assertRaises(g.Unavailable):
            p.revalidate()

    def test_unknown_payload_held(self):
        with zipfile.ZipFile(self.wrong, 'w') as z:
            z.writestr('01.jpg', b'unknown')
        with self.writer.hold(), self.assertRaises(g.Unavailable):
            self.prepare_negative()

    def test_changed_owner_status(self):
        self.sql('UPDATE issues SET Status=? WHERE IssueID=?', ('Wanted', '123'))
        with self.writer.hold(), self.assertRaises(g.Unavailable):
            self.prepare_negative()

    def test_WAL_held(self):
        Path(str(self.database) + '-wal').write_bytes(b'hold')
        with self.writer.hold(), self.assertRaises(Exception):
            self.prepare_negative()

    def test_source_changed_after_prepare(self):
        with self.writer.hold():
            p = self.prepare_negative()
            self.wrong.write_bytes(b'foreign')
            with self.assertRaises(Exception):
                p.revalidate()

    def test_xattrs_changed(self):
        os.setxattr(self.restore, 'user.fixture', b'foreign')
        with self.writer.hold(), self.assertRaises(g.Unavailable):
            self.prepare_negative()

    def test_historical_registered_original_excluded(self):
        new = self.library / 'current.cbz'
        shutil.copy2(self.source, new)
        self.sql('UPDATE issues SET Location=? WHERE IssueID=?', (new.name, '123'))
        for p in (self.retained, self.restore):
            shutil.copy2(self.source, p)
        with self.writer.hold(), self.assertRaisesRegex(g.Unavailable, 'protected registered original'):
            m.NativeNegativePreparation(self.source, self.owner, new, self.retained, self.restore)

    def test_catalog_source_claim_inserted_after_prepare(self):
        with self.writer.hold():
            p = self.prepare_negative()
            self.sql('INSERT INTO issues VALUES (?,?,?,?)', ('777', '456', 'wrong.cbz', 'Wanted'))
            with self.assertRaises(Exception):
                p.revalidate()

    def test_counterpart_wrong_constrained_path(self):
        shutil.copy2(self.source, self.library / 'other.cbz')
        with self.writer.hold(), self.assertRaisesRegex(g.Unavailable, 'counterpart differs'):
            m.NativeNegativePreparation(self.wrong, self.owner, self.library / 'other.cbz', self.retained, self.restore)

    def test_last_custody_xattr_creates_catalog_source_alias_holds(self):
        self.sql('INSERT INTO issues VALUES (?,?,?,?)', ('777', '456', 'late.cbz', 'Wanted'))
        real = m.attrs
        seen = []

        def late(path):
            result = real(path)
            seen.append(path)
            if len(seen) == 5:
                os.symlink(self.wrong, self.library / 'late.cbz')
            return result
        with self.writer.hold(), patch.object(m, 'attrs', side_effect=late), self.assertRaisesRegex(m.catalog.Held, 'owning-terminal-catalog-claim'):
            self.prepare_negative()
        self.assertEqual(len(seen), 8)
        self.assertTrue((self.library / 'late.cbz').is_symlink())

    def test_last_database_signature_creates_WAL_holds(self):
        real = m.catalog.signature
        fired = []

        def late(path):
            result = real(path)
            if Path(path) == self.database and inspect.stack()[1].function == '_prepare' and (not fired):
                Path(str(path) + '-wal').write_bytes(b'foreign')
                fired.append(True)
            return result
        with self.writer.hold(), patch.object(m.catalog, 'signature', new=late), self.assertRaisesRegex(m.catalog.Held, 'owning-terminal-catalog-companion'):
            self.prepare_negative()
        self.assertTrue(fired)

    def test_last_custody_changes_catalog_claim_parent_holds(self):
        directory = self.library / 'claim-parent'
        directory.mkdir()
        self.sql('INSERT INTO issues VALUES (?,?,?,?)', ('777', '456', 'claim-parent/absent.cbz', 'Wanted'))
        real = m.attrs
        seen = []

        def late(path):
            result = real(path)
            seen.append(path)
            if len(seen) == 5:
                directory.rename(self.library / 'retained-parent')
                directory.mkdir()
            return result
        with self.writer.hold(), patch.object(m, 'attrs', side_effect=late), self.assertRaisesRegex(m.catalog.Held, 'owning-terminal-catalog-ancestor'):
            self.prepare_negative()

    def replace_metadata(self, raw):
        with zipfile.ZipFile(self.wrong) as z:
            rows = [(i.filename, z.read(i)) for i in z.infolist() if i.filename != 'ComicInfo.xml']
        with zipfile.ZipFile(self.wrong, 'w') as z:
            for name, value in rows:
                z.writestr(name, value)
            z.writestr('ComicInfo.xml', raw)

    def test_metadata_only_difference_preserves_native_payload(self):
        self.replace_metadata(b'<ComicInfo><Series>Wrong metadata</Series><Number>1</Number></ComicInfo>')
        for p in (self.retained, self.restore):
            shutil.copy2(self.wrong, p)
        with self.writer.hold():
            prepared = self.prepare_negative()
            self.assertTrue(prepared.binding['native_negative_observation_ready'])
            self.assertNotEqual(g.file_hash(self.wrong)[1], g.file_hash(self.source)[1])
            prepared.revalidate()

    def test_nonmetadata_difference_not_metadata_exception(self):
        with zipfile.ZipFile(self.wrong, 'a') as z:
            z.writestr('other.txt', b'not metadata')
        for p in (self.retained, self.restore):
            shutil.copy2(self.wrong, p)
        with self.writer.hold(), self.assertRaises(g.Unavailable):
            self.prepare_negative()

    def test_metadata_source_custody_is_still_complete(self):
        self.replace_metadata(b'<ComicInfo><Series>Wrong</Series></ComicInfo>')
        with self.writer.hold(), self.assertRaisesRegex(g.Unavailable, 'restore differs'):
            self.prepare_negative()

    def test_real_fresh_wrapper_shared_registry_revalidates(self):
        from media_writer import Writer
        self.runtime.owner = lambda: Writer(self.writer.root, create=False)
        with self.writer.hold():
            first = self.runtime.owner()
            second = self.runtime.owner()
            self.assertIsNot(first, second)
            self.assertIs(first.local, second.local)
            prepared = self.prepare_negative()
            self.assertTrue(prepared.revalidate()['native_negative_observation_ready'])

    def existing(self, writer=None, controller=None):
        from media_writer import Writer
        modules = (api, types.SimpleNamespace(Writer=Writer))
        with patch.object(m, '_sdk', return_value=modules):
            obj = m.prepare_existing(controller or api.Controller(self.root, [self.library], tool_root=g.TOOL_ROOT), writer or self.writer, self.wrong, self.owner, self.source, self.retained, self.restore)
            obj.revalidate()
            return obj

    def test_explicit_existing_factory_no_daemon_flags_or_protected_global(self):
        self.runtime.active = lambda: False
        self.runtime.publication_mode = lambda: False
        with self.writer.hold(), patch.object(m.mutation, 'protected_paths', side_effect=AssertionError('daemon globals forbidden')):
            self.assertTrue(self.existing().binding['native_negative_observation_ready'])

    def test_existing_wrong_controller_root_held(self):
        (self.root / 'foreign').mkdir()
        c = api.Controller(self.root / 'foreign', [self.library])
        with self.writer.hold(), self.assertRaises(g.Unavailable):
            self.existing(controller=c)

    def test_existing_nonheld_writer_held(self):
        with self.assertRaises(g.Unavailable):
            self.existing()

    def test_existing_wrong_registry_wrapper_held(self):
        from media_writer import Writer
        writer = Writer(self.writer.root, create=False)
        writer.local = (writer.local[0], types.SimpleNamespace(depth=1))
        with self.writer.hold(), self.assertRaises(Exception):
            self.existing(writer=writer)

    def test_existing_foreign_controller_subclass_held(self):

        class Other(api.Controller):
            pass
        with self.writer.hold(), self.assertRaises(g.Unavailable):
            self.existing(controller=Other(self.root, [self.library]))

    def test_existing_foreign_writer_rejected_before_callbacks(self):

        class Other:

            def __getattribute__(self, name):
                raise AssertionError('foreign Writer callback')
        with self.writer.hold(), self.assertRaisesRegex(g.Unavailable, 'exact SDK types'):
            self.existing(writer=Other())

    def test_existing_native_catalog_0644_allowed(self):
        self.database.chmod(420)
        with self.writer.hold():
            self.assertTrue(self.existing().binding['native_negative_observation_ready'])

    def test_existing_immutable_protected_original_remains_held(self):
        new = self.library / 'current.cbz'
        shutil.copy2(self.source, new)
        self.sql('UPDATE issues SET Location=? WHERE IssueID=?', (new.name, '123'))
        for p in (self.retained, self.restore):
            shutil.copy2(self.source, p)
        from media_writer import Writer
        modules = (api, types.SimpleNamespace(Writer=Writer))
        with self.writer.hold(), patch.object(m, '_sdk', return_value=modules), self.assertRaisesRegex(g.Unavailable, 'protected registered original'):
            m.prepare_existing(api.Controller(self.root, [self.library], tool_root=g.TOOL_ROOT), self.writer, self.source, self.owner, new, self.retained, self.restore)

    def test_existing_factory_without_mylar_package_globals(self):
        with self.writer.hold(), patch.dict(sys.modules, {'mylar': None}):
            self.assertTrue(self.existing().binding['native_negative_observation_ready'])

    def test_existing_protected_reader_matches_native_algorithm(self):
        controller = api.Controller(self.root, [self.library], tool_root=g.TOOL_ROOT)
        with self.writer.hold():
            self.assertEqual(m._protected_paths(controller, self.writer), m.mutation.protected_paths(self.writer))

    def test_existing_recovery_privileges_held(self):
        with self.writer.hold(allow_pending=True), self.assertRaisesRegex(g.Unavailable, 'recovery privileges'):
            self.existing()

    def test_existing_mutable_writer_lock_rejected(self):
        with self.writer.hold():
            original = self.writer.lock
            self.writer.lock = self.root / 'foreign.lock'
            try:
                with self.assertRaises(g.Unavailable):
                    self.existing()
            finally:
                self.writer.lock = original

    def test_actual_native_owner_function_fresh_wrappers(self):
        import ast
        from media_writer import Writer
        source = (Path(api.__file__).parent / 'native_writers.py').read_text()
        node = next((x for x in ast.parse(source).body if isinstance(x, ast.FunctionDef) and x.name == 'owner'))
        namespace = {'Path': Path, 'Writer': Writer}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), 'actual-native-owner', 'exec'), namespace)
        self.runtime.owner = namespace['owner']
        with self.writer.hold():
            left = self.runtime.owner()
            right = self.runtime.owner()
            self.assertIsNot(left, right)
            self.assertIs(left.local, right.local)
            prepared = self.prepare_negative()
            self.assertTrue(prepared.revalidate()['native_negative_observation_ready'])
if __name__ == '__main__':
    unittest.main()
