"""Real binary/source file projection through the owning seven-original retention code.

The factual report and Parent constructor remain the existing declared fixtures.
This checks the wire/file boundary, not a genuine configured observer or NFS grant.
"""
import hashlib
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).parent
READER = Path(os.environ.get('KOMGA_READER_SOURCES', str(HERE.parents[1] / 'mylar3/config/reader_recovery')))
sys.path.insert(0, str(READER))
import test_effective_review_projection as owning


class Tests(unittest.TestCase):
    def setUp(self):
        self.compiled = Path(os.environ['KOMGA_COMPILED_CLASSES'])
        self.original = (self.compiled / 'KomgaEffectiveScope.class').read_bytes()
        self.assertTrue(self.original.startswith(b'\xca\xfe\xba\xbe'))
        self.fixture = owning.EffectiveReviewTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        old_path = f.review['producer']['path']
        path = f.root / 'producer.class'
        path.write_bytes(self.original)
        path.chmod(0o600)
        f.original.pop(old_path)
        f.original[str(path)] = self.original
        f.review['producer'] = dict(path=str(path), sha256=hashlib.sha256(self.original).hexdigest())
        f.doc.write_bytes(owning.p.encode(f.review))
        f.ref['sha256'] = hashlib.sha256(f.doc.read_bytes()).hexdigest()
        f.owner.files[str(f.doc)] = owning.p.nine(f.doc.lstat())

    def test_genuine_compiled_producer_bytes_survive_unchanged_projection(self):
        f = self.fixture
        projected = f.projection()
        derived = projected.effective_review(f.ref)
        review = projected.document_projected(derived)
        path = Path(f.tree.host(review['producer']['path']))
        self.assertEqual(path.read_bytes(), self.original)
        self.assertEqual(review['producer']['sha256'], f.review['producer']['sha256'])
        self.assertEqual(set(review), {'producer', 'parent_source', 'report', 'ack', 'runtime', 'acceptance', 'parent_ack'})
        self.assertNotEqual(review['producer']['path'], f.review['producer']['path'])
        f.tree.check()

    def test_replaced_compiled_original_refuses_before_projection(self):
        f = self.fixture
        producer = Path(f.review['producer']['path'])
        producer.write_bytes(self.original + b'changed')
        with self.assertRaises(owning.p.Held):
            f.retain()


if __name__ == '__main__':
    unittest.main(verbosity=2)
