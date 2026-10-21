"""Private artwork bridge boundaries and reviewed-template behavior."""

import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[2] / "stacks/dispatcharr/helpers/library_artwork.py"
SPEC = importlib.util.spec_from_file_location("library_artwork", SOURCE)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)
FIXTURE = "server {\n    listen NGINX_PORT;\n    listen [::]:NGINX_PORT;\n" + bridge.ANCHOR + "}\n"


class LibraryArtworkTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(bridge, "REVIEWED_TEMPLATE_SHA256", hashlib.sha256(FIXTURE.encode()).hexdigest())
        guard.start()
        self.addCleanup(guard.stop)

    def test_template_and_initialized_ports_are_accepted_idempotently(self):
        for value in [FIXTURE, FIXTURE.replace("NGINX_PORT", "9191")]:
            result = bridge.render(value, "https://dispatcharr.example.com")
            self.assertEqual(result, bridge.render(result, "https://dispatcharr.example.com"))
            self.assertIn("allow 127.0.0.1;\n        deny all;", result)
            self.assertIn("limit_except GET { deny all; }", result)
            self.assertIn("resolver 127.0.0.11 valid=30s", result)
            self.assertIn("(posters|thumbnails|logos)/(plex/[0-9]+", result)
            self.assertNotIn("proxy_pass $arg", result)

    def test_origin_change_replaces_only_the_bridge(self):
        first = bridge.render(FIXTURE, "https://dispatcharr.example.com")
        second = bridge.render(first, "https://tv.example.com")
        self.assertEqual(second.count(bridge.BEGIN), 1)
        self.assertIn("proxy_set_header Host tv.example.com;", second)
        self.assertIn("listen NGINX_PORT;", second)

    def test_unknown_template_and_ambiguous_markers_refuse(self):
        for value in [FIXTURE + "# unexpected upstream change\n", bridge.BEGIN + FIXTURE,
                      bridge.BEGIN + bridge.BEGIN + bridge.END + FIXTURE]:
            with self.assertRaises(ValueError):
                bridge.render(value, "https://dispatcharr.example.com")

    def test_only_public_https_dns_origin_without_path_is_allowed(self):
        for origin in ["http://dispatcharr.example.com", "https://127.0.0.1", "https://192.168.1.2",
                       "https://localhost", "https://host.local", "https://host.home.arpa",
                       "https://u:p@dispatcharr.example.com", "https://dispatcharr.example.com/path",
                       "https://dispatcharr.example.com?x=1", "https://dispatcharr.example.com#x",
                       "https://dispatcharr.example.com; injected", "https://dispatcharr.example.com:99999",
                       "https://dispatcharr.example.com\n; injected"]:
            with self.assertRaises(ValueError):
                bridge.render(FIXTURE, origin)


if __name__ == "__main__":
    unittest.main()
