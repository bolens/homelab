"""Exact retained public native source; no application/runtime substitution."""
import argparse
import ast
import sys
import importlib.util
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('migration',HERE/'patch_publication_processing.py')
migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)


SOURCE=HERE/'test_fixtures/ordinary_import/PostProcessor.py'


def unpatched_source(source):
    """Undo only exact round-trip checked guards in a disposable text value."""
    source=migration.terminal_predecessor(source)
    if migration.IMPORT_MARKER in source:
        if migration._import_source(source)!=source:raise ValueError('Current import patch differs')
        source=source.replace(migration.IMPORT_MARKER+'\n','',1).replace(migration.IMPORT_HOOK,'',1)
        source=source.replace(migration.IMPORT_FILE_COPY,migration.IMPORT_FILE_OP)
        for original in migration.IMPORT_CLEANUPS:
            source=source.replace(original.replace('self.tidyup(',
                'processing_guard.defer_import_cleanup(self, self.tidyup, ',1),original,1)
        if migration._publication_source(source)!=source:raise ValueError('Predecessor reconstruction differs')
    if migration.MARKER in source:
        if migration._publication_source(source)!=source:raise ValueError('Native guard differs')
        tree=ast.parse(source);lines=source.splitlines(keepends=True)
        owned=[n for n in ast.walk(tree) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
            and ast.unparse(n.value.func) in ('processing_guard.publication','processing_guard.placement',
                'processing_guard.displacement','processing_guard.cleanup','processing_guard.cleanup_scope')]
        if len(owned)!=47:raise ValueError('Guard reconstruction coverage differs')
        for n in sorted(owned,key=lambda n:n.lineno,reverse=True):del lines[n.lineno-1:n.end_lineno]
        clean=''.join(lines).replace(migration.MARKER+'\n','',1)
        if migration._publication_source(clean)!=source:raise ValueError('Guard reconstruction round trip differs')
        source=clean
    migration.patched_source(source)  # Unknown/malformed sources still refuse.
    return source


class Migration(unittest.TestCase):
    def setUp(self):self.source=unpatched_source(SOURCE.read_text())
    def test_unpatched_and_existing_v1_roundtrip(self):
        predecessor=migration._publication_source(self.source)
        current=migration.patched_source(self.source)
        self.assertEqual(migration.patched_source(predecessor),current)
        self.assertEqual(migration.patched_source(current),current)
        ast.parse(current,feature_version=(3,10))
    def test_success_only_immediately_after_owning_catalog_upsert(self):
        current=migration.patched_source(self.source)
        self.assertEqual(current.count('processing_guard.import_success('),1)
        self.assertIn('myDB.upsert(updatetable, newVal, ctrlVal)\n'+migration.IMPORT_HOOK,current)
        self.assertEqual(current.count('processing_guard.import_file_ops('),2)
        self.assertEqual(current.count('processing_guard.defer_import_cleanup('),2)
        self.assertEqual(current.count('self.tidyup(odir, True, cacheonly=True)'),self.source.count('self.tidyup(odir, True, cacheonly=True)'))
    def test_moved_hook_unknown_arguments_and_missing_copy_refused(self):
        current=migration.patched_source(self.source)
        for changed in (current.replace(migration.IMPORT_HOOK,'',1),
                        current.replace('issueid=issueid, comicid=comicid)\n','issueid=comicid, comicid=comicid)\n',1),
                        current.replace(migration.IMPORT_FILE_COPY,migration.IMPORT_FILE_OP,1)):
            with self.assertRaises(ValueError):migration.patched_source(changed)

    def test_current_source_reconstructs_exact_unpatched_predecessor(self):
        current=migration.patched_source(self.source)
        self.assertEqual(unpatched_source(current),self.source)
        self.assertEqual(unpatched_source(migration._publication_source(self.source)),self.source)
    def test_unknown_or_partial_current_cannot_be_reconstructed(self):
        current=migration.patched_source(self.source)
        for changed in (current+ migration.IMPORT_MARKER+'\n',
                        current.replace(migration.IMPORT_FILE_COPY,migration.IMPORT_FILE_OP,1),
                        current.replace(migration.IMPORT_HOOK,'',1)):
            with self.assertRaises(ValueError):unpatched_source(changed)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',nargs='?',type=Path)
    options=parser.parse_args()
    if options.source is not None:
        SOURCE=(options.source/'PostProcessor.py' if options.source.is_dir() else options.source)
    unittest.main(argv=[sys.argv[0]])
