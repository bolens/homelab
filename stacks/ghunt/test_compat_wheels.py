"""Compatibility wheel custody, reproducibility and RECORD integrity controls."""
import base64
import csv
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SPEC = importlib.util.spec_from_file_location("compat_wheels", Path(__file__).with_name("build-compat-wheels.py"))
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class CompatibilityWheelTests(unittest.TestCase):
    def test_build_preserves_code_and_license_and_rebuilds_valid_record(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / "demo-1-py3-none-any.whl"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("demo/__init__.py", "value = 42\n")
                archive.writestr("demo-1.dist-info/LICENSE", "upstream license\n")
                archive.writestr("demo-1.dist-info/METADATA", "Version: 1\nRequires-Dist: dep==1\n")
                archive.writestr("demo-1.dist-info/RECORD", "old record")
            recipe = (hashlib.sha256(source.read_bytes()).hexdigest(), "demo-1", "demo-1+local.1",
                      {"Version: 1": "Version: 1+local.1", "Requires-Dist: dep==1": "Requires-Dist: dep==2"})
            first, second = root / "first", root / "second"
            first.mkdir()
            second.mkdir()
            with patch.dict(builder.RECIPES, {source.name: recipe}):
                a = builder.build(source, first)
                b = builder.build(source, second)
                self.assertEqual(a.read_bytes(), b.read_bytes())
                with self.assertRaises(FileExistsError):
                    builder.build(source, first)
                with zipfile.ZipFile(a) as archive:
                    self.assertEqual(archive.read("demo/__init__.py"), b"value = 42\n")
                    self.assertEqual(archive.read("demo-1+local.1.dist-info/LICENSE"), b"upstream license\n")
                    record = "demo-1+local.1.dist-info/RECORD"
                    rows = list(csv.reader(io.StringIO(archive.read(record).decode())))
                    self.assertEqual({row[0] for row in rows}, set(archive.namelist()))
                    for name, digest, size in rows:
                        if name == record:
                            self.assertEqual((digest, size), ("", ""))
                        else:
                            data = archive.read(name)
                            self.assertEqual(size, str(len(data)))
                            self.assertEqual(digest, "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode())
                source.write_bytes(source.read_bytes() + b"tampered")
                with self.assertRaisesRegex(ValueError, "digest mismatch"):
                    builder.build(source, second)


if __name__ == "__main__":
    unittest.main()
