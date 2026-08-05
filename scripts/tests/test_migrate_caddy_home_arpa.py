#!/usr/bin/env python3

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "migrate-caddy-home-arpa.py"
SPEC = importlib.util.spec_from_file_location("migrate_caddy_home_arpa", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class MigrateCaddyHomeArpaTests(unittest.TestCase):
    def test_adds_matching_site_labels_only(self):
        source = (
            "app.home, app.local {\n"
            "    reverse_proxy backend.local:8080\n"
            "}\n"
            "http://app.local, https://secure.local:8443 {\n"
            "}\n"
        )
        expected = (
            "app.home, app.local, app.home.arpa {\n"
            "    reverse_proxy backend.local:8080\n"
            "}\n"
            "http://app.local, http://app.home.arpa, https://secure.local:8443, "
            "https://secure.home.arpa:8443 {\n"
            "}\n"
        )
        self.assertEqual(MODULE.migrate_text(source), expected)

    def test_is_idempotent_and_preserves_comments(self):
        source = "app.local, app.home.arpa { # local route\n"
        self.assertEqual(MODULE.migrate_text(source), source)


if __name__ == "__main__":
    unittest.main()
