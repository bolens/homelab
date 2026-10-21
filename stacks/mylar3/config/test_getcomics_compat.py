"""Pinned parser behavior and explicit cached-file lifetime regressions."""
import ast
import builtins
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import warnings

from bs4 import BeautifulSoup
import patch_getcomics_compat as adapter

HERE = Path(__file__).parent
FIXTURE = HERE / 'test_fixtures/cache_admission'
ORIGINAL = (FIXTURE / 'getcomics.py.txt').read_text()


def cached_parser_prefix(source):
    """Execute actual method nodes through cached parse and first soup query.

    Later network/download selection is deliberately outside this focused slice.
    No parser/file-access node in the original method is mocked or rewritten.
    """
    tree = ast.parse(source)
    method = copy.deepcopy(next(n for n in ast.walk(tree)
                                if isinstance(n, ast.FunctionDef) and n.name == 'parse_downloadresults'))
    index = next(i for i, n in enumerate(method.body) if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'beeswax' for t in n.targets))
    method.body = method.body[:index + 1] + [ast.Return(value=ast.Name(id='beeswax', ctx=ast.Load()))]
    return ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))


class Compatibility(unittest.TestCase):
    def test_original_fixture_matches_retained_provenance(self):
        provenance = json.loads((FIXTURE / 'PROVENANCE.json').read_text())
        self.assertEqual(hashlib.sha256((FIXTURE / 'getcomics.py.txt').read_bytes()).hexdigest(),
                         provenance['files']['getcomics.py.txt'])
        self.assertEqual(provenance['files']['getcomics.py.txt'],
                         '857dbf95fdbe9e54da7abefab0f60de7262be62f39b93934e713b16cf96d23c7')

    def test_legacy_is_patched_current_is_idempotent_and_python310_parses(self):
        changed = adapter.patched_source(ORIGINAL)
        self.assertNotEqual(changed, ORIGINAL)
        self.assertEqual(adapter.patched_source(changed), changed)
        ast.parse(changed, feature_version=(3, 10))
        tree = ast.parse(changed)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, ('findAll', 'findNext'))
                if node.func.attr in ('find', 'find_all', 'find_next'):
                    self.assertNotIn('text', [kw.arg for kw in node.keywords])

    def test_all_fifteen_active_aliases_preserve_real_bs4_results_without_warnings(self):
        html = '<article><p style="text-align: center;">First <a>next</a></p><ul><li>item</li></ul><h3>TPBs</h3></article>'
        for old, (new, _) in adapter.CALLS.items():
            # Corresponding old/new expressions operate on the same real tree.
            soup = BeautifulSoup(html, 'html.parser')
            env = dict(soup=soup, possible_more=soup, nxt=soup,
                       option_find=soup.article, linkline=soup.a, sb=soup.h3, x=soup.li)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', DeprecationWarning)
                expected = eval(compile(ast.parse(old, mode='eval'), '<legacy-bs4-call>', 'eval'), env)
            with warnings.catch_warnings():
                warnings.simplefilter('error')
                observed = eval(compile(ast.parse(new, mode='eval'), '<current-bs4-call>', 'eval'), env)
            self.assertEqual(observed, expected)

    def parse_cached(self, source, soup=BeautifulSoup):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / 'html_cache').mkdir()
        title = root / 'html_cache/getcomics-test'
        title.touch()  # Preserve the owning method's existing existence test.
        title.with_suffix('.html').write_text('<p style="text-align: center;">A &amp; B</p>', encoding='utf-8')
        handles = []
        def tracked_open(*args, **kwargs):
            handle = builtins.open(*args, **kwargs)
            handles.append(handle)
            return handle
        env = dict(BeautifulSoup=soup, open=tracked_open, os=__import__('os'),
                   mylar=SimpleNamespace(CONFIG=SimpleNamespace(CACHE_DIR=str(root))),
                   db=SimpleNamespace(DBConnection=lambda: None),
                   logger=SimpleNamespace(fdebug=lambda *a: None, info=lambda *a: None))
        exec(compile(cached_parser_prefix(source), '<actual-cached-parser-prefix>', 'exec'), env)
        return env['parse_downloadresults'], handles

    def test_actual_cached_parser_closes_file_and_preserves_text_with_warnings_as_errors(self):
        parse, handles = self.parse_cached(adapter.patched_source(ORIGINAL))
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            result = parse(SimpleNamespace(), 'test', 'unused')
        self.assertEqual([p.get_text() for p in result], ['A & B'])
        self.assertEqual(len(handles), 1)
        self.assertTrue(handles[0].closed)
        self.assertEqual(handles[0].encoding.lower().replace('-', ''), 'utf8')

    def test_actual_cached_parser_closes_file_when_beautifulsoup_raises(self):
        def refused(handle, parser):
            self.assertFalse(handle.closed)
            self.assertEqual(parser, 'html.parser')
            raise RuntimeError('parser-refused')
        parse, handles = self.parse_cached(adapter.patched_source(ORIGINAL), refused)
        with self.assertRaisesRegex(RuntimeError, 'parser-refused'):
            parse(SimpleNamespace(), 'test', 'unused')
        self.assertEqual(len(handles), 1)
        self.assertTrue(handles[0].closed)

    def test_legacy_parser_exception_demonstrates_missing_close(self):
        def refused(handle, parser):
            raise RuntimeError('parser-refused')
        parse, handles = self.parse_cached(ORIGINAL, refused)
        try:
            with self.assertRaisesRegex(RuntimeError, 'parser-refused'):
                parse(SimpleNamespace(), 'test', 'unused')
            self.assertFalse(handles[0].closed)
        finally:
            for handle in handles:
                handle.close()

    def test_only_alias_calls_and_cached_context_change_decision_ast(self):
        changed = adapter.patched_source(ORIGINAL)
        # Reverse the declared alias edits and exact context boundary, then
        # compare the complete original AST, including every decision branch.
        restored = adapter._replace_calls(changed, reverse=True).replace(adapter.CURRENT, adapter.PRIOR, 1)
        self.assertEqual(restored, ORIGINAL)
        self.assertEqual(ast.dump(ast.parse(restored)), ast.dump(ast.parse(ORIGINAL)))
        self.assertIn('# .findNext(text=True)', changed)
        self.assertIn('#site = linkline.findNext(text=True)', changed)
        self.assertIn('page_list.find_all("li")', changed)

    def test_missing_duplicate_or_changed_cached_boundary_refuses(self):
        for source in (ORIGINAL.replace(adapter.PRIOR, ''), ORIGINAL + adapter.PRIOR,
                       ORIGINAL.replace("encoding='utf-8'", "encoding='ascii'")):
            with self.assertRaises(ValueError):
                adapter.patched_source(source)

    def test_missing_extra_or_changed_legacy_alias_refuses(self):
        for source in (ORIGINAL.replace('soup.findAll("article")', 'soup.find_all("article")'),
                       ORIGINAL + '\nextra = soup.findNext(text=True)\n',
                       ORIGINAL.replace('sb.findNext(text=True)', 'sb.findNext(text=False)')):
            with self.assertRaises(ValueError):
                adapter.patched_source(source)

    def test_marker_never_hides_reintroduced_alias_or_text_keyword_or_context_drift(self):
        changed = adapter.patched_source(ORIGINAL)
        for source in (changed.replace('sb.find_next(string=True)', 'sb.findNext(text=True)'),
                       changed + '\nextra = soup.find(text=True)\n',
                       changed.replace('BeautifulSoup(cached_html,', 'BeautifulSoup(cached_html.read(),'),
                       changed + '\n' + adapter.MARKER):
            with self.assertRaises(ValueError):
                adapter.patched_source(source)

    def test_file_entrypoint_is_idempotent_and_refusal_never_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'getcomics.py'
            path.write_text(ORIGINAL)
            adapter.main(temp)
            before = path.stat()
            adapter.main(temp)
            after = path.stat()
            # Reading may update atime; idempotence forbids writes, not reads.
            fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_uid', 'st_gid', 'st_nlink')
            self.assertEqual(tuple(getattr(after, k) for k in fields),
                             tuple(getattr(before, k) for k in fields))
            broken = path.read_text().replace('sb.find_next(string=True)', 'sb.find_next(text=True)')
            path.write_text(broken)
            with self.assertRaises(ValueError):
                adapter.main(temp)
            self.assertEqual(path.read_text(), broken)


if __name__ == '__main__':
    unittest.main()
