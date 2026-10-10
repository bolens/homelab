"""Real disposable installer leaves; exact owning bytes, no installed SDK claim."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import patch_publication_retained_standalone as p


class Installation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.sources = self.root/'public'; self.sources.mkdir()
        self.target = self.root/'mylar'; self.target.mkdir()
        self.rows = dict(p.SOURCES)
        for _, (name, _) in self.rows.items():
            path = self.sources/name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((p.ROOT/name).read_bytes())
        self.ctx = patch.object(p, 'ROOT', self.sources); self.ctx.start(); self.addCleanup(self.ctx.stop)

    def test_exact_install_and_idempotence(self):
        p.main(self.target)
        original = {x.name:p.full(x.lstat()) for x in self.target.iterdir()}
        p.main(self.target)
        self.assertEqual(original, {x.name:p.full(x.lstat()) for x in self.target.iterdir()})
        self.assertEqual(len(original), 2)
        for name, (source, _) in self.rows.items(): self.assertEqual((self.target/(name+'.py')).read_bytes(), (self.sources/source).read_bytes())

    def test_unknown_installed_source_refused(self):
        (self.target/'publication_retained_standalone.py').write_bytes(b'ENABLED=False\n')
        with self.assertRaisesRegex(ValueError, 'Unknown'): p.main(self.target)

    def test_source_pin_refused_before_install(self):
        path=self.sources/'publication_retained_standalone.py';path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError, 'pin'): p.main(self.target)
        self.assertFalse(list(self.target.iterdir()))

    def test_first_AST_late_later_source_mode_refused(self):
        original=p.ast.parse; fired=[]
        def callback(*args, **kwargs):
            result=original(*args, **kwargs)
            if not fired:
                fired.append(True); os.chmod(self.sources/'reader_recovery/comic_retained_standalone_action.py', 0o640)
            return result
        with patch.object(p.ast, 'parse', callback), self.assertRaisesRegex(ValueError, 'source'): p.main(self.target)
        self.assertTrue(fired);self.assertFalse(list(self.target.iterdir()))

    def test_first_AST_late_destination_mode_refused(self):
        p.main(self.target); original=p.ast.parse; fired=[]
        def callback(*args, **kwargs):
            result=original(*args, **kwargs)
            if not fired:
                fired.append(True);os.chmod(self.target/'publication_retained_standalone.py', 0o640)
            return result
        with patch.object(p.ast, 'parse', callback), self.assertRaisesRegex(ValueError, 'destination'): p.main(self.target)
        self.assertTrue(fired)

    def test_first_AST_ancestor_mode_refused(self):
        original=p.ast.parse;fired=[]
        def callback(*args, **kwargs):
            result=original(*args, **kwargs)
            if not fired:fired.append(True);os.chmod(self.sources, 0o775)
            return result
        with patch.object(p.ast,'parse',callback),self.assertRaisesRegex(ValueError,'ancestor'):p.main(self.target)
        self.assertTrue(fired)

    def test_created_leaf_fsync_mode_refused(self):
        original=p.os.fsync;fired=[]
        def callback(fd):
            original(fd);fired.append(True);os.fchmod(fd,0o640)
        with patch.object(p.os,'fsync',callback),self.assertRaisesRegex(ValueError,'output changed'):p.main(self.target)
        self.assertTrue(fired)


if __name__ == '__main__': unittest.main()
