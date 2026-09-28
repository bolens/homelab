"""Exercise checked native caller bodies with actual temporary archive ownership."""
import ast
import importlib.util
from pathlib import Path
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

import tagger_adapter
import archive_monitor
import pp_monitor
import tagger_handoff
from tagger_cli import TagResult
from patch_tagger_handoff import manual, automatic, MARKER

SOURCE = Path(sys.argv.pop(1))


class HandoffTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root/'library'
        self.library.mkdir()
        self.source = self.library/'comic.cbz'
        with zipfile.ZipFile(self.source, 'w') as archive:
            archive.writestr('001.png', b'preserved page')
        self.publisher = tagger_adapter.Publisher(self.root/'state')
        self.token = 'a'*32
        self.mylar = SimpleNamespace(tagger_handoff=tagger_handoff,pp_monitor=pp_monitor,
                                     workflow=SimpleNamespace(emit=Mock()),DATA_DIR=str(self.root))
        self.updater = Mock()
        self.context = patch.dict(sys.modules, {'mylar':self.mylar})
        self.context.start()
        self.addCleanup(self.context.stop)

    def published(self):
        def saved(path, metadata, **kwargs):
            with zipfile.ZipFile(path, 'a') as archive:
                archive.writestr('ComicInfo.xml', '<ComicInfo><Series>Fixture</Series></ComicInfo>')
            return TagResult('saved')
        with patch.object(tagger_adapter, 'save', side_effect=saved):
            self.assertEqual(self.publisher.tag(self.source, {'series':'Fixture'}, token=self.token).state, 'committed')
        return tagger_handoff.capture(self.publisher, self.token)

    def native_manual(self, value, group=False):
        source = manual((SOURCE/'webserve.py').read_text())
        method = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == 'manual_metatag')
        start = next(i for i, n in enumerate(method.body) if isinstance(n, ast.ImportFrom)
                     and any(alias.name == 'tagger_handoff' for alias in n.names))
        body = method.body[start:]
        function = ast.FunctionDef(name='check', args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]), body=body, decorator_list=[])
        namespace = dict(metaresponse=value, filename=str(self.source), group=group,
                         mylar=self.mylar, updater=self.updater, comicid='123', comicname='Fixture',
                         seriesyear='2020', dirName=str(self.library), module='',
                         logger=Mock(), shutil=shutil, os=os)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])), '<native-manual>', 'exec'), namespace)
        return namespace['check']()

    def test_manual_published_source_never_copied_or_deleted(self):
        value = self.published()
        before = self.source.read_bytes()
        with patch.object(shutil, 'copy', side_effect=AssertionError('No duplicate publication')):
            self.native_manual(value)
        self.assertEqual(self.source.read_bytes(), before)
        self.updater.forceRescan.assert_called_once_with('123')
        self.assertEqual(self.mylar.GLOBAL_MESSAGES['status'], 'success')
        self.assertNotIn(str(self.root), repr(value))

    def test_monitor_uses_verified_publication_metadata_outcome(self):
        archive_monitor._ACTIVE.clear()
        archive_monitor._RECENT.clear()
        @archive_monitor.tagging
        def tag(filename=None):
            return self.published()
        result = tag(filename=str(self.source))
        self.assertTrue(result.valid_for(self.source))
        row = archive_monitor.snapshot()['tagging'][0]
        self.assertEqual(row['metadata'], 'Metadata added')
        self.assertEqual(row['conversion'], 'No format change')
        self.assertNotIn(str(self.root), repr(row))

    def test_foreign_module_results_fail_closed_in_native_callers(self):
        name = 'other_tagger_handoff'
        spec = importlib.util.spec_from_file_location(name, Path(tagger_handoff.__file__))
        other = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {name:other}):
            spec.loader.exec_module(other)
            value = self.published()
            foreign = other.Published(**vars(value))
            self.assertTrue(foreign.valid_for(self.source))
            self.assertNotIsInstance(foreign, tagger_handoff.Published)
            with self.assertRaises(RuntimeError):
                tagger_handoff.automatic(foreign)
            self.native_manual(foreign)
        self.assertEqual(self.mylar.GLOBAL_MESSAGES['status'], 'failure')
        self.assertTrue(self.source.exists())
        self.updater.forceRescan.assert_not_called()

    def test_unchanged_and_updated_results_reach_manual_and_monitor(self):
        self.published()
        for token, updates, label in [('b'*32, {'Series':'Updated'}, 'Metadata updated'),
                                     ('c'*32, None, 'Metadata unchanged')]:
            @archive_monitor.tagging
            def tag(filename=None):
                with patch.object(tagger_adapter, 'save', return_value=TagResult('saved')):
                    self.publisher.tag(self.source, {'series':'Fixture'}, token=token, updates=updates)
                return tagger_handoff.capture(self.publisher, token)
            value = tag(filename=str(self.source))
            self.assertEqual(archive_monitor.snapshot()['tagging'][0]['metadata'], label)
            self.native_manual(value)
            self.assertEqual(self.mylar.GLOBAL_MESSAGES['status'], 'success')
            self.assertTrue(self.source.exists())

    def test_manual_group_does_not_rescan_each_item(self):
        self.native_manual(self.published(), group=True)
        self.updater.forceRescan.assert_not_called()
        self.assertTrue(self.source.exists())

    def test_changed_or_wrong_source_fails_without_cleanup(self):
        value = self.published()
        self.source.write_bytes(b'operator modification')
        self.native_manual(value)
        self.assertEqual(self.source.read_bytes(), b'operator modification')
        self.assertEqual(self.mylar.GLOBAL_MESSAGES['status'], 'failure')
        self.updater.forceRescan.assert_not_called()
        self.assertFalse(value.valid_for(self.root/'another.cbz'))

    def test_legacy_temporary_copy_and_cleanup_still_work(self):
        cache = self.root/'cache'
        cache.mkdir()
        staged = cache/'comic.cbz'
        staged.write_bytes(self.source.read_bytes())
        self.native_manual(str(staged))
        self.assertTrue(self.source.exists())
        self.assertFalse(staged.exists())
        self.updater.forceRescan.assert_called_once_with('123')
        self.assertEqual(self.mylar.GLOBAL_MESSAGES['status'], 'success')

    def test_failed_typed_result_never_enters_cleanup(self):
        for state in ('failed', 'timed_out', 'unsupported', 'conflict'):
            self.native_manual(tagger_handoff.Published(state))
            self.assertEqual(self.mylar.GLOBAL_MESSAGES['status'], 'failure')
            self.assertTrue(self.source.exists())

    def test_capture_requires_durable_verified_receipt(self):
        value = self.published()
        self.assertTrue(value.valid_for(self.source))
        self.source.chmod(0o400)
        self.assertEqual(tagger_handoff.capture(self.publisher, self.token).state, 'conflict')
        self.assertFalse(value.valid_for(self.source))

    def test_automatic_callers_reject_in_place_results_preserve_legacy(self):
        source = automatic((SOURCE/'PostProcessor.py').read_text())
        calls = [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                 and n.func.value.id == 'tagger_handoff' and n.func.attr == 'automatic']
        self.assertEqual(len(calls), 4)
        namespace = dict(tagger_handoff=tagger_handoff, cmtagmylar=SimpleNamespace(run=Mock()),
                         self=SimpleNamespace(nzb_folder='incoming'), issueid='1',vol_label='1',
                         ofilename='comic.cbz',readingorder=None,agerating=None, location='incoming',
                         tmp_ppdir='incoming/comic.cbz', odir='incoming', os=os, ml={'ComicLocation':'incoming/comic.cbz'})
        value = self.published()
        for call in calls:
            expression = compile(ast.Expression(call), '<native-automatic>', 'eval')
            namespace['cmtagmylar'].run.return_value = value
            with self.assertRaises(RuntimeError):
                eval(expression, namespace)
            for legacy in ('fail', 'corrupt', '/cache/comic.cbz'):
                namespace['cmtagmylar'].run.return_value = legacy
                self.assertEqual(eval(expression, namespace), legacy)
        self.assertTrue(self.source.exists())

    def test_patches_are_idempotent_and_fail_on_changed_anchors(self):
        for name, transform in (('webserve.py', manual), ('PostProcessor.py', automatic)):
            source = (SOURCE/name).read_text()
            changed = transform(source)
            self.assertEqual(transform(changed), changed)
            self.assertIn(MARKER, changed)
            with self.assertRaises(ValueError):
                transform('class Changed: pass\n')


if __name__ == '__main__':
    unittest.main()
