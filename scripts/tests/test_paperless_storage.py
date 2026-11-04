"""Verify optional Paperless originals storage without live env files or a daemon."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which("docker"), "Docker CLI unavailable")
class PaperlessStorageTests(unittest.TestCase):
    def test_originals_override_preserves_application_storage_and_requires_path(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = root / "stacks" / "paperless-ngx"
            target.mkdir(parents=True)
            for name in ("docker-compose.yml", "docker-compose.storage.yml"):
                shutil.copy2(ROOT / "stacks/paperless-ngx" / name, target / name)
            example = (ROOT / "stacks/paperless-ngx/stack.env.example").read_text()
            (target / "stack.env").write_text(example)
            command = ["docker", "compose", "--env-file", "stack.env", "-f", "docker-compose.yml"]
            env = {"PATH": os.environ["PATH"], "HOME": raw}

            def render(args):
                return subprocess.run(command + args + ["config", "--format", "json"],
                                      cwd=target, env=env, capture_output=True, text=True,
                                      check=False, timeout=30)

            base = render([])
            self.assertEqual(base.returncode, 0, base.stderr)
            override = ["-f", "docker-compose.storage.yml"]
            self.assertNotEqual(render(override).returncode, 0)
            missing = root / "absent-filesystem" / "originals"
            (target / "stack.env").write_text(example + f"\nPAPERLESS_ORIGINALS_PATH={missing}\n"
                "PAPERLESS_FILENAME_FORMAT={{ owner_username }}/{{ created_year }}/{{ doc_pk }}-{{ title }}\n")
            enabled = render(override)
            self.assertEqual(enabled.returncode, 0, enabled.stderr)
            old = json.loads(base.stdout)["services"]["webserver"]
            new = json.loads(enabled.stdout)["services"]["webserver"]
            mounts = {m["target"]: m for m in new["volumes"]}
            for mount in old["volumes"]:
                self.assertEqual(mounts[mount["target"]], mount)
            originals = mounts["/usr/src/paperless/media/documents/originals"]
            self.assertEqual(originals["source"], str(missing))
            self.assertIs(originals["bind"]["create_host_path"], False)
            self.assertFalse(missing.exists())
            self.assertEqual(old["networks"], new["networks"])
            self.assertEqual(old.get("ports"), new.get("ports"))
            self.assertEqual(new["environment"]["PAPERLESS_FILENAME_FORMAT"],
                             "{{ owner_username }}/{{ created_year }}/{{ doc_pk }}-{{ title }}")
