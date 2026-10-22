"""Render only public fixtures. No Docker daemon or runtime configuration."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


STACK = Path(__file__).resolve().parents[1]


class ComposeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docker = shutil.which("docker")
        if not cls.docker:
            raise unittest.SkipTest("Docker CLI unavailable; example rendering skipped")

    def test_override_preserves_app_state_and_keeps_gateway_private(self):
        with tempfile.TemporaryDirectory(prefix="kavita-compose-fixture-") as raw:
            target = Path(raw)
            for filename in ("docker-compose.yml", "docker-compose.providers.yml"):
                shutil.copyfile(STACK / filename, target / filename)
            (target / "stack.env").write_text((STACK / "stack.env.example").read_text() + "\n"
                + f"KAVITA_PROVIDER_KEY_PATH={target}/provider_key\n"
                + f"KAVITA_HARDCOVER_TOKEN_PATH={target}/hardcover_token\n")
            (target / "provider_key").write_text("fixture-key-with-more-than-32-characters")
            (target / "hardcover_token").write_text("")
            (target / "providers").mkdir()
            shutil.copyfile(STACK / "providers/oauth-clients.json.example", target / "providers/oauth-clients.json.example")
            env = {"PATH": os.environ["PATH"], "HOME": str(target)}
            command = [self.docker, "compose", "--env-file", "stack.env", "-f", "docker-compose.yml"]
            base = subprocess.run(command + ["config", "--format", "json"], cwd=target,
                                  env=env, capture_output=True, text=True, check=True)
            extended = subprocess.run(command + ["-f", "docker-compose.providers.yml", "config", "--format", "json"],
                                      cwd=target, env=env, capture_output=True, text=True, check=True)
            original = json.loads(base.stdout)
            current = json.loads(extended.stdout)
            self.assertNotIn("kavita-providers", original["services"])
            app = current["services"]["kavita"]
            self.assertEqual(app["volumes"], original["services"]["kavita"]["volumes"])
            gateway = current["services"]["kavita-providers"]
            self.assertFalse(gateway.get("ports"))
            self.assertNotIn("ingress-public", gateway["networks"])
            self.assertTrue(gateway["read_only"])
            self.assertEqual(gateway["cap_drop"], ["ALL"])
            self.assertFalse(gateway.get("privileged"))
            self.assertEqual(app["environment"]["KAVITA_PROVIDER_URL"], "http://kavita-providers:8080")
            self.assertEqual({m["target"] for m in gateway["volumes"]}, {"/state"})
            self.assertEqual({s["source"] for s in gateway["secrets"]}, {"provider_key", "hardcover_token", "oauth_clients"})


if __name__ == "__main__":
    unittest.main()
