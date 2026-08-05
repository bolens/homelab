#!/usr/bin/env python3

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "sync-local-hosts.py"
SPEC = importlib.util.spec_from_file_location("sync_local_hosts", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class SyncLocalHostsTests(unittest.TestCase):
    def test_extracts_only_caddy_site_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            snippet = Path(directory) / "caddy_snippet.conf"
            snippet.write_text(
                """
                app.home, app.local, https://other.local:443 {
                    reverse_proxy backend.local:8080
                    tls internal
                }
                # ignored.local {
                public.example.com {
                }
                """
            )
            self.assertEqual(
                MODULE.aliases_from_caddy(snippet),
                {"app.local", "other.local"},
            )

    def test_managed_block_preserves_unmanaged_content(self):
        original = "127.0.0.1 localhost\n10.0.0.2 printer.local\n"
        first = MODULE.managed_content(original, ["10.0.0.3  app.local"])
        second = MODULE.managed_content(first, ["10.0.0.4  app.local"])
        self.assertIn("10.0.0.2 printer.local", second)
        self.assertNotIn("10.0.0.3  app.local", second)
        self.assertEqual(second.count(MODULE.BEGIN), 1)

    def test_replaces_legacy_managed_block(self):
        original = (
            "127.0.0.1 localhost\n\n"
            "# BEGIN docker-local\n"
            "10.0.0.3 old.local\n"
            "# END docker-local\n"
        )
        updated = MODULE.managed_content(original, ["10.0.0.4  new.local"])
        self.assertNotIn("old.local", updated)
        self.assertIn("new.local", updated)
        self.assertEqual(updated.count("# BEGIN docker-local"), 1)

    def test_overrides_include_and_exclude(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overrides"
            path.write_text("+status\n-admin.local\n")
            self.assertEqual(
                MODULE.read_overrides(path),
                ({"status.local"}, {"admin.local"}),
            )

    def test_replaces_legacy_hblock_footer(self):
        with tempfile.TemporaryDirectory() as directory:
            avahi = Path(directory) / "avahi"
            footer = Path(directory) / "footer"
            footer.write_text(
                "# .local entries from scripts/sync-local-hosts.sh (local-hosts.conf)\n"
                "# hblock appends this file when you run: hblock -F footer\n"
                "10.0.0.3 old.local\n"
            )
            desired = MODULE.desired_files("10.0.0.4", {"new.local"}, avahi, footer)
            self.assertNotIn("old.local", desired[footer])
            self.assertIn("new.local", desired[footer])

    def test_atomic_write_reports_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "target"
            self.assertTrue(MODULE.atomic_write(path, "value\n"))
            self.assertFalse(MODULE.atomic_write(path, "value\n"))

    def test_explicit_hblock_config_is_portable(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            for name in ("sources.list", "allow.list", "footer.list"):
                (config / name).write_text("")
            self.assertEqual(MODULE.find_hblock_config(config), config.resolve())

    def test_incomplete_explicit_hblock_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                MODULE.find_hblock_config(Path(directory))

    def test_hblock_discovery_uses_account_home_database(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / ".config/hblock"
            config.mkdir(parents=True)
            for name in ("sources.list", "allow.list", "footer.list"):
                (config / name).write_text("")
            account = SimpleNamespace(pw_dir=directory)
            with mock.patch.object(MODULE.pwd, "getpwall", return_value=[account]):
                self.assertEqual(MODULE.find_hblock_config(None), config.resolve())


if __name__ == "__main__":
    unittest.main()
