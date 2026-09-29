"""Disposable output cleanup preserves uncertain or uniquely remaining content."""
import json
from pathlib import Path
import tempfile
import unittest
from tagger_archive import identity
from tagger_adapter import fingerprint
from tagger_staging import Staging


class StagingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('cache', 'receipts'):
            (self.root/name).mkdir(mode=0o700)
        self.owner = Staging(self.root/'cache', self.root/'receipts')
        self.source = self.root/'original.cbz'; self.source.write_bytes(b'original')
        self.token = 'b'*32
        self.target = self.owner.allocate(self.token, self.source, fingerprint(self.source), identity(self.source.stat()))
        self.target.write_bytes(b'original')

    def test_unchanged_copy_can_be_removed_without_import_claim(self):
        self.assertEqual(self.owner.recover(), 0)
        self.assertFalse(self.target.parent.exists()); self.assertEqual(self.source.read_bytes(), b'original')
        self.assertEqual(self.owner.recover(), 0)

    def test_ready_tagged_copy_can_be_removed_only_while_original_survives(self):
        self.target.write_bytes(b'tagged'); self.owner.ready(self.token, self.target)
        self.assertEqual(self.owner.recover(), 0); self.assertTrue(self.source.exists())

    def test_changed_source_or_stage_is_retained(self):
        self.target.write_bytes(b'unrecorded data')
        self.assertEqual(self.owner.recover(), 1); self.assertEqual(self.target.read_bytes(), b'unrecorded data')
        self.assertEqual(self.owner.recover(), 1)

    def test_missing_source_keeps_only_remaining_archive(self):
        self.source.unlink()
        self.assertEqual(self.owner.recover(), 1); self.assertTrue(self.target.exists())

    def test_native_consumed_folder_is_recorded_cleaned(self):
        self.target.unlink(); self.target.parent.rmdir()
        self.assertEqual(self.owner.recover(), 0)
        self.assertEqual(self.owner.read(self.root/'receipts'/(self.token+'.json'))['state'], 'cleaned')

    def test_unknown_output_and_interrupted_receipt_block_admission(self):
        (self.root/'receipts'/'partial.new').write_text('partial')
        with self.assertRaises(ValueError): self.owner.recover()
        self.assertTrue(self.target.exists())
        (self.root/'receipts'/'partial.new').unlink()
        (self.root/'cache'/'unknown').mkdir()
        with self.assertRaises(ValueError): self.owner.recover()
        self.assertTrue((self.root/'cache'/'unknown').exists())

    def test_forged_folder_identity_does_not_delete_contents(self):
        path = self.root/'receipts'/(self.token+'.json')
        record = json.loads(path.read_text()); record['folder_identity'] = [0, 0]
        path.write_text(json.dumps(record))
        with self.assertRaises(ValueError): self.owner.recover()
        self.assertTrue(self.target.exists())


if __name__ == '__main__': unittest.main()
