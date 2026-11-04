"""Check optional Immich storage using public examples and isolated fixtures."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class ImmichStorageTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="immich-storage-contract-")
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.stack = self.root / "stacks" / "immich"
        self.stack.mkdir(parents=True)
        for name in ("docker-compose.yml", "docker-compose.storage.yml",
                     "stack.env.example", "prepare-stack.sh", "caddy_snippet.conf.example"):
            shutil.copy2(ROOT / "stacks" / "immich" / name, self.stack / name)
        (self.stack / "stack.env").write_text((self.stack / "stack.env.example").read_text())
        scripts = self.root / "scripts"
        scripts.mkdir()
        shutil.copy2(ROOT / "scripts" / "prepare-stack-lib.sh", scripts)
        self.environment = {"PATH": os.environ["PATH"], "HOME": str(self.root)}

    def configure(self, value):
        with (self.stack / "stack.env").open("a") as stream:
            stream.write("\nIMMICH_LIBRARY_PATH=" + value + "\n")

    def render(self, override=False):
        docker = shutil.which("docker")
        if not docker:
            self.skipTest("Docker CLI unavailable")
        args = [docker, "compose", "--env-file", "stack.env", "-f", "docker-compose.yml"]
        if override:
            args += ["-f", "docker-compose.storage.yml"]
        return subprocess.run(args + ["config", "--format", "json"],
                              cwd=self.stack, env=self.environment,
                              capture_output=True, text=True, check=False, timeout=30)

    def prepare(self):
        binaries = self.root / "bin"
        binaries.mkdir(exist_ok=True)
        docker = binaries / "docker"
        docker.write_text("#!/bin/sh\nexit 1\n")
        docker.chmod(0o755)
        environment = dict(self.environment, PATH=str(binaries) + ":/usr/bin:/bin")
        return subprocess.run(["bash", "prepare-stack.sh"], cwd=self.stack,
                              env=environment, capture_output=True, text=True,
                              check=False, timeout=30)

    def test_override_only_adds_originals_mount_and_never_creates_source(self):
        path = self.root / "absent-mount" / "photos" / "immich"
        self.configure(str(path))
        base_result, new_result = self.render(), self.render(override=True)
        self.assertEqual(base_result.returncode, 0, base_result.stderr)
        self.assertEqual(new_result.returncode, 0, new_result.stderr)
        base = json.loads(base_result.stdout)
        enabled = json.loads(new_result.stdout)
        mounts = enabled["services"]["immich-server"]["volumes"]
        added = [m for m in mounts if m["target"] == "/data/library"]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["source"], str(path))
        declared = yaml.safe_load((self.stack / "docker-compose.storage.yml").read_text())
        mount = declared["services"]["immich-server"]["volumes"][0]
        self.assertIs(mount["bind"]["create_host_path"], False)
        # A false bool is omitted by some Compose JSON serializers.
        self.assertIs(added[0].get("bind", {}).get("create_host_path", False), False)
        self.assertFalse(added[0].get("read_only", False))
        mounts.remove(added[0])
        self.assertEqual(enabled, base)
        self.assertFalse(path.exists())

    def test_override_requires_nonempty_path_while_base_remains_portable(self):
        self.assertEqual(self.render().returncode, 0)
        for value in (None, ""):
            if value is not None:
                self.configure(value)
            result = self.render(override=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("IMMICH_LIBRARY_PATH", result.stderr)

    def test_preparation_refuses_missing_media_without_creating_parents(self):
        path = self.root / "missing-share" / "photos" / "immich"
        self.configure(str(path))
        before = (self.stack / "stack.env").read_bytes()
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires an existing directory", result.stderr)
        self.assertNotIn(str(path), result.stdout + result.stderr)
        self.assertFalse(path.parent.parent.exists())
        self.assertEqual((self.stack / "stack.env").read_bytes(), before)

    def test_preparation_preserves_settings_and_refreshes_compose_selection(self):
        path = self.root / "mounted-library"
        path.mkdir()
        self.configure(str(path))
        with (self.stack / "stack.env").open("a") as stream:
            stream.write("COMPOSE_FILE=docker-compose.yml:docker-compose.storage.yml\n")
            stream.write("PRESERVATION_SENTINEL=private-fixture-value\n")
        before = (self.stack / "stack.env").read_bytes()
        for _ in range(2):
            result = self.prepare()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((self.stack / "stack.env").read_bytes(), before)
            self.assertEqual((self.stack / ".env").read_bytes(), before)
            self.assertNotIn("private-fixture-value", result.stdout + result.stderr)
        self.assertEqual(list(path.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
