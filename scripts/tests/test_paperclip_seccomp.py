"""Keep the optional nested sandbox exception separate from the default stack."""

import hashlib
import json
from pathlib import Path
import unittest

import yaml


STACK = Path(__file__).resolve().parents[2] / "stacks/paperclip"


class PaperclipSeccompTests(unittest.TestCase):
    def test_only_the_documented_rule_differs_from_pinned_moby_default(self):
        profile = json.loads((STACK / "codex-seccomp.json").read_text())
        exception = profile["syscalls"].pop()
        self.assertEqual(exception, {
            "names": ["clone", "unshare", "setns", "mount", "umount2", "pivot_root"],
            "action": "SCMP_ACT_ALLOW",
        })
        canonical = json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(),
                         "a894b5730caa168d88da7fffe8ace974ad05fb84547e1766fa879d75d3ac6ba2")
        self.assertEqual(profile["defaultAction"], "SCMP_ACT_ERRNO")

    def test_override_adds_no_privileges_or_other_service_changes(self):
        override = yaml.safe_load((STACK / "docker-compose.codex-sandbox.yml").read_text())
        self.assertEqual(override, {"services": {"paperclip": {
            "security_opt": ["seccomp:./codex-seccomp.json"],
        }}})
        base = yaml.safe_load((STACK / "docker-compose.yml").read_text())
        self.assertNotIn("security_opt", base["services"]["paperclip"])


if __name__ == "__main__":
    unittest.main()
