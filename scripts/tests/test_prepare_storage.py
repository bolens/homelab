"""Preparation must not manufacture a missing media mount's directory tree."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/prepare-stack-lib.sh"


class StoragePreparationTests(unittest.TestCase):
    def run_helper(self, root, destination, mode="require-existing", configured=False):
        stack = root / "fixture"
        stack.mkdir(exist_ok=True)
        if configured:
            (stack / "stack.env").write_text(f'TEST_MEDIA_PATH="{destination}"\n')
        return subprocess.run(
            ["bash", "-euc", 'source "$1"; prepare_stack_begin "$2"; '
             'prepare_stack_ensure_dir_from_env TEST_MEDIA_PATH "$3" "$4"',
             "fixture", str(HELPER), str(stack), str(destination), mode],
            env={"PATH": os.environ["PATH"], "HOME": str(root)},
            capture_output=True, text=True, check=False,
        )

    def test_missing_media_path_fails_without_creating_parents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "absent-mount" / "private-library"
            result = self.run_helper(root, destination, configured=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(destination.parent.exists())
            self.assertIn("TEST_MEDIA_PATH", result.stdout + result.stderr)
            self.assertNotIn(str(destination), result.stdout + result.stderr)

    def test_existing_media_path_is_unchanged_on_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "media with spaces"
            destination.mkdir()
            sentinel = destination / "existing.txt"
            sentinel.write_text("retain me")
            for _ in range(2):
                result = self.run_helper(root, destination)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(sentinel.read_text(), "retain me")

    def test_regular_file_is_not_an_existing_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "file"
            destination.write_text("retain me")
            result = self.run_helper(root, destination)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(destination.read_text(), "retain me")

    def test_local_directory_creation_remains_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "application" / "config"
            result = self.run_helper(root, destination, mode="create")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(destination.is_dir())

    def test_invalid_mode_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "missing"
            result = self.run_helper(root, destination, mode="typo")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(destination.exists())

    def test_media_root_callers_require_existing_paths(self):
        callers = []
        for wrapper in (ROOT / "stacks").glob("*/prepare-stack.sh"):
            for line in wrapper.read_text().splitlines():
                if "prepare_stack_ensure_dir_from_env" in line and "MEDIA_ROOT" in line:
                    callers.append(wrapper)
                    self.assertTrue(line.endswith(" require-existing"), str(wrapper))
        self.assertGreaterEqual(len(callers), 16)


if __name__ == "__main__":
    unittest.main()
