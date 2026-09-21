"""Render optional stack contracts without reading live config or using Docker's daemon."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class OptionalStackOverrideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docker = shutil.which("docker")
        if cls.docker is None:
            raise unittest.SkipTest("Docker CLI unavailable; Compose rendering skipped")

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="homelab-override-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def fixture(self, name, override, extra_env=""):
        source = ROOT / "stacks" / name
        target = self.root / "stacks" / name
        target.mkdir(parents=True)
        for filename in ("docker-compose.yml", override):
            shutil.copy2(source / filename, target / filename)
        # Only public examples are copied; no .env or live env_file is read.
        example = (source / "stack.env.example").read_text(encoding="utf-8")
        (target / "stack.env").write_text(example + "\n" + extra_env, encoding="utf-8")
        return target

    def render(self, target, override=None):
        command = [self.docker, "compose", "--env-file", "stack.env",
                   "-f", "docker-compose.yml"]
        if override:
            command.extend(["-f", override])
        command.extend(["config", "--format", "json"])
        result = subprocess.run(
            command, cwd=target,
            env={"PATH": os.environ["PATH"], "HOME": str(self.root)},
            capture_output=True, text=True, check=False, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["services"]

    def test_local_backup_overrides_inherited_repository_and_success_policy(self):
        override = "docker-compose.local-backup.yml"
        target = self.fixture("restic", override, "\n".join([
            "RESTIC_REPOSITORY=s3:https://backup.example.com/old",
            "RESTIC_REPOSITORY_FILE=/old-repository-file",
            "SUCCESS_ON_INCOMPLETE_BACKUP=true",
            "RESTIC_FORGET_ARGS=--prune --keep-last 1",
            f"RESTIC_PATH_DOCKER={self.root}/sources/docker",
            f"RESTIC_PATH_APPDATA={self.root}/sources/appdata",
            f"RESTIC_PATH_MEDIA={self.root}/missing-media",
            f"RESTIC_LOCAL_PATH={self.root}/missing-backup-disk/restic",
        ]) + "\n")
        base = self.render(target)["restic"]["environment"]
        self.assertEqual(base["RESTIC_REPOSITORY_FILE"], "/old-repository-file")
        self.assertEqual(base["SUCCESS_ON_INCOMPLETE_BACKUP"], "true")
        self.assertEqual(base["RESTIC_FORGET_ARGS"], "--prune --keep-last 1")
        service = self.render(target, override)["restic"]
        environment = service["environment"]
        self.assertEqual(environment["RESTIC_REPOSITORY"], "/repository")
        self.assertEqual(environment["RESTIC_REPOSITORY_FILE"], "")
        self.assertEqual(environment["SUCCESS_ON_INCOMPLETE_BACKUP"], "false")
        self.assertEqual(environment["RESTIC_FORGET_ARGS"], "")
        mounts = {mount["target"]: mount for mount in service["volumes"]}
        self.assertNotIn("/data/media", mounts)
        for mount in mounts.values():
            if mount["type"] == "bind":
                self.assertFalse(mount.get("bind", {}).get("create_host_path", False))
        self.assertFalse((self.root / "missing-backup-disk").exists())
        self.assertFalse((self.root / "missing-media").exists())

    def test_mongodb_kernel_workaround_requires_explicit_override(self):
        override = "docker-compose.kernel-workaround.yml"
        target = self.fixture("librechat", override)
        self.assertIsNone(self.render(target)["mongodb"].get("entrypoint"))
        service = self.render(target, override)["mongodb"]
        self.assertEqual(service["entrypoint"], [
            "setarch", "--uname-2.6", "/usr/local/bin/docker-entrypoint.sh",
        ])
        self.assertEqual(service["command"], ["mongod"])


if __name__ == "__main__":
    unittest.main()
