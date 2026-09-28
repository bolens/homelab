"""Explicit catalog volumes must survive optional inferred-volume settings."""

from pathlib import Path
import sys
import unittest
from catalog_volume import volume_label
from patch_catalog_volumes import patched

SOURCE = Path(sys.argv.pop(1))


class VolumeTest(unittest.TestCase):
    def test_explicit_volumes_are_independent_of_default(self):
        for default in (False, True):
            for value, expected in [
                ("1", "v1"),
                ("2", "v2"),
                (1, "v1"),
                (" 03 ", "v3"),
            ]:
                self.assertEqual(volume_label(value, default), expected)

    def test_missing_invalid_or_zero_uses_only_configured_default(self):
        for value in (None, "", "None", "unknown", "0", "-1"):
            self.assertIsNone(volume_label(value, False))
            self.assertEqual(volume_label(value, True), "v1")

    def test_native_import_and_edit_adapters_are_idempotent(self):
        for name in ("importer.py", "webserve.py"):
            source = patched(name, (SOURCE / name).read_text())
            self.assertEqual(patched(name, source), source)
            self.assertIn("catalog_volume.volume_label(", source)
            with self.assertRaises(ValueError):
                patched(name, "pass\n")


if __name__ == "__main__":
    unittest.main()
