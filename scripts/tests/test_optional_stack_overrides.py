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

    def test_comic_normalizer_is_opt_in_and_runs_without_privileges(self):
        override = "docker-compose.normalizer.yml"
        target = self.fixture("komga", override)
        base = self.render(target)
        self.assertNotIn("comic-normalizer", base)
        self.assertTrue(all(mount.get("read_only") for mount in base["komga"]["volumes"]
                            if mount["target"].startswith("/data/")))
        services = self.render(target, override)
        worker = services["comic-normalizer"]
        self.assertEqual(worker["user"], "1000:1000")
        self.assertTrue(worker["read_only"])
        self.assertEqual(worker["cap_drop"], ["ALL"])
        self.assertFalse(worker.get("ports"))
        self.assertEqual(worker["image"], "ghcr.io/bolens/homelab-comic-normalizer:latest")
        self.assertNotIn("/app", [m["target"] for m in worker["volumes"]])
        for service in services.values():
            for mount in service["volumes"]:
                if mount["type"] == "bind":
                    self.assertFalse(mount.get("bind", {}).get("create_host_path", False))
        mounts = {mount["target"]: mount for mount in services["komga"]["volumes"]}
        self.assertFalse(mounts["/data/comics"].get("read_only", False))
        self.assertTrue(mounts["/normalizer-state"]["read_only"])

    def test_maintenance_mount_is_explicit_and_does_not_create_storage(self):
        override = "docker-compose.normalizer.yml"
        target = self.fixture("komga", override, f"MYLAR_DDL_CACHE_PATH={self.root}/ddl-cache\n")
        extra = "docker-compose.maintenance.yml"
        shutil.copy2(ROOT / "stacks/komga" / extra, target)
        # Compose permits multiple override flags. Keep the fixture free of live env.
        result = subprocess.run(
            [self.docker, "compose", "--env-file", "stack.env", "-f", "docker-compose.yml",
             "-f", override, "-f", extra, "config", "--format", "json"], cwd=target,
            env={"PATH": os.environ["PATH"], "HOME": str(self.root)},
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        services = json.loads(result.stdout)["services"]
        mounts = {m["target"]: m for m in services["comic-normalizer"]["volumes"]}
        self.assertFalse(mounts["/completed-comics"].get("read_only", False))
        self.assertFalse(mounts["/completed-comics"].get("bind", {}).get("create_host_path", False))
        self.assertFalse(mounts["/ddl-cache"].get("read_only", False))
        self.assertFalse(mounts["/ddl-cache"].get("bind", {}).get("create_host_path", False))
        self.assertTrue(mounts["/mylar"]["read_only"])
        self.assertNotIn("/completed-comics", [m["target"] for m in services["komga"]["volumes"]])

    def test_maintenance_preparation_requires_existing_download_directory(self):
        target = self.fixture("komga", "docker-compose.maintenance.yml")
        scripts = self.root / "scripts"
        scripts.mkdir()
        shutil.copy2(ROOT / "scripts/prepare-stack-lib.sh", scripts)
        shutil.copy2(ROOT / "stacks/komga/prepare-maintenance.sh", target)
        completed = self.root / "missing-media" / "completed"
        (target / "stack.env").write_text(f"MYLAR_COMPLETED_PATH={completed}\nMYLAR_DDL_CACHE_PATH={completed.parent}/ddl-cache\n")
        def prepare():
            return subprocess.run(["bash", "prepare-maintenance.sh"], cwd=target,
                                  env={"PATH": os.environ["PATH"]}, capture_output=True, text=True)
        self.assertNotEqual(prepare().returncode, 0)
        self.assertFalse(completed.parent.exists())
        completed.mkdir(parents=True)
        (completed.parent / "ddl-cache").mkdir()
        original = (target / "stack.env").read_bytes()
        self.assertEqual(prepare().returncode, 0)
        self.assertEqual(prepare().returncode, 0)
        self.assertEqual((target / "stack.env").read_bytes(), original)

    def test_normalizer_preparation_preserves_config_and_requires_storage(self):
        target = self.fixture("komga", "docker-compose.normalizer.yml")
        scripts = self.root / "scripts"
        scripts.mkdir()
        shutil.copy2(ROOT / "scripts/prepare-stack-lib.sh", scripts)
        source = ROOT / "stacks/komga"
        shutil.copy2(source / "prepare-normalizer.sh", target)
        (target / "normalizer").mkdir()
        shutil.copy2(source / "normalizer/normalizer.json.example", target / "normalizer")
        media = self.root / "media"
        state = self.root / "state"
        state.mkdir()
        (target / "stack.env").write_text(
            f"KOMGA_COMICS_PATH={media}/comics\nKOMGA_MANGA_PATH={media}/manga\n"
            f"NORMALIZER_STATE_PATH={state}\n", encoding="utf-8")
        binary = self.root / "bin"
        binary.mkdir()
        docker = binary / "docker"
        docker.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$DOCKER_TRACE"\nexit 0\n')
        docker.chmod(0o755)
        trace = self.root / "docker-calls"
        environment = {"PATH": str(binary) + ":" + os.environ["PATH"],
                       "DOCKER_TRACE": str(trace)}
        def prepare():
            return subprocess.run(["bash", "prepare-normalizer.sh"], cwd=target,
                                  env=environment, capture_output=True, text=True)
        self.assertNotEqual(prepare().returncode, 0)
        self.assertFalse(media.exists())
        (media / "comics").mkdir(parents=True)
        (media / "manga").mkdir()
        self.assertEqual(prepare().returncode, 0)
        runtime = target / "normalizer.json"
        runtime.write_text('{"operator": "preserve"}\n')
        self.assertEqual(prepare().returncode, 0)
        self.assertEqual(runtime.read_text(), '{"operator": "preserve"}\n')
        self.assertEqual(runtime.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(" up", trace.read_text())
        self.assertNotIn(" run", trace.read_text())


if __name__ == "__main__":
    unittest.main()
