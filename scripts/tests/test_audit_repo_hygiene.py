#!/usr/bin/env python3

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "audit-repo-hygiene.py"
SPEC = importlib.util.spec_from_file_location("audit_repo_hygiene", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class PortableAssignmentTests(unittest.TestCase):
    def test_rejects_structurally_local_values(self):
        cases = (
            "DATA_DIR=/home/alice/app",
            "MEDIA_DIR=/mnt/nas/media",
            "TZ=Europe/Amsterdam",
            "SERVER_HOST=node.tail123abc.ts.net",
            "PUBLIC_URL=https://app.personal-domain.dev",
        )
        for value in cases:
            with self.subTest(value=value):
                self.assertIsNotNone(MODULE.local_assignment_reason(value))

    def test_accepts_portable_values(self):
        cases = (
            "DATA_DIR=/home/user/app",
            "MEDIA_DIR=${MEDIA_ROOT}/movies",
            "TZ=UTC",
            "TZ=Etc/UTC",
            "TZ=${TZ:-UTC}",
            "PUBLIC_URL=https://app.example.com",
            "PUBLIC_URL=https://app.home",
            "HOSTNAME=app.yourdomain.com",
            "OLLAMA_BASE_URL=http://host.docker.internal:11434",
            "API_URL=http://service:8080",
        )
        for value in cases:
            with self.subTest(value=value):
                self.assertIsNone(MODULE.local_assignment_reason(value))


if __name__ == "__main__":
    unittest.main()
