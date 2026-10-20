"""Regression checks for immutable Certipy selection without a NetExec upgrade."""

from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest

import pin_dependencies as pin


class CertipyPinTests(unittest.TestCase):
    def source(self, dependency=pin.ORIGINAL):
        return '[project]\nname = "netexec"\ndependencies = [\n    "requests>=2.27.1",\n    "' + dependency + '",\n]\n'

    def test_build_context_includes_only_dockerfile_and_pin_helper(self):
        stack = Path(pin.__file__).parent
        rules = [line.strip() for line in (stack / ".dockerignore").read_text().splitlines()
                 if line.strip() and not line.startswith("#")]
        self.assertEqual(rules, ["**", "!Dockerfile", "!pin_dependencies.py"])
        self.assertIn("COPY pin_dependencies.py /tmp/pin_dependencies.py", (stack / "Dockerfile").read_text())
        for name in ("Dockerfile", "pin_dependencies.py"):
            self.assertTrue((stack / name).is_file())

    def test_only_expected_dependency_bytes_change(self):
        original = self.source()
        result = pin.pin_certipy(original)
        self.assertEqual(result, original.replace(pin.ORIGINAL, pin.PINNED))
        self.assertEqual(tomllib.loads(result)["project"]["dependencies"], ["requests>=2.27.1", pin.PINNED])
        self.assertRegex(pin.CERTIPY_COMMIT, r"^[0-9a-f]{40}$")

    def test_missing_renamed_or_already_pinned_requirement_refuses(self):
        for dependency in ("certipy-nxc>=5.1.0.post1", "certipy-ad>=5.1.0", pin.PINNED):
            with self.subTest(dependency=dependency), self.assertRaises(ValueError):
                pin.pin_certipy(self.source(dependency))

    def test_duplicate_or_extra_source_occurrence_refuses(self):
        source = self.source()
        for text in (source.replace('"requests>=2.27.1"', '"' + pin.ORIGINAL + '"'), source + "# " + pin.ORIGINAL):
            with self.subTest(text=text), self.assertRaises(ValueError):
                pin.pin_certipy(text)

    def test_command_writes_only_after_successful_validation(self):
        helper = Path(pin.__file__)
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "pyproject.toml"
            target.write_text(self.source())
            subprocess.run([sys.executable, str(helper), str(target)], check=True)
            self.assertEqual(target.read_text(), self.source(pin.PINNED))
            before = target.read_bytes()
            result = subprocess.run([sys.executable, str(helper), str(target)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
