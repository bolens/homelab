"""Private artwork bridge boundaries and reviewed-template behavior."""

import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import textwrap
import tempfile
import xml.etree.ElementTree as ET


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


class PlexSpecialsTests(unittest.TestCase):
    def test_startup_rejects_raw_exporter_drift_before_either_file_changes(self):
        source = "# synthetic guard fixture\n" + bridge.EXPORTER_LINE + "\n"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nginx.conf"
            exporter = Path(directory) / "epg.py"
            target.write_text(FIXTURE)
            raw = source.replace("\n", "\r\n").encode()
            exporter.write_bytes(raw)
            paths = {"/etc/nginx/sites-enabled/default": target, "/app/apps/output/epg.py": exporter}
            with patch.object(bridge, "Path", side_effect=lambda value: paths[value]), patch.object(
                    bridge, "REVIEWED_TEMPLATE_SHA256", hashlib.sha256(FIXTURE.encode()).hexdigest()), patch.object(
                    bridge, "REVIEWED_EXPORTER_SHA256", hashlib.sha256(source.encode()).hexdigest()), patch.dict(
                    bridge.os.environ, {"PLEX_XMLTV_SPECIALS": "true",
                                        "LIBRARY_ARTWORK_ORIGIN": "https://dispatcharr.example.com"}):
                with self.assertRaisesRegex(ValueError, "Unreviewed XMLTV"):
                    bridge.main()
            self.assertEqual(target.read_text(), FIXTURE)
            self.assertEqual(exporter.read_bytes(), raw)

    def test_disabled_mode_does_not_modify_an_unreviewed_exporter(self):
        source = "# a different exporter\n"
        self.assertEqual(bridge.render_exporter(source, False), source)
        with self.assertRaisesRegex(ValueError, "Unreviewed XMLTV"):
            bridge.render_exporter(source, True)

    def test_reviewed_patch_is_idempotent_and_reversible(self):
        source = "# synthetic guard fixture\n" + bridge.EXPORTER_LINE + "\n"
        with patch.object(bridge, "REVIEWED_EXPORTER_SHA256", hashlib.sha256(source.encode()).hexdigest()):
            updated = bridge.render_exporter(source, True)
            self.assertEqual(bridge.render_exporter(updated, True), updated)
            self.assertEqual(bridge.render_exporter(updated, False), source)
            with self.assertRaisesRegex(ValueError, "Unreviewed XMLTV"):
                bridge.render_exporter(updated + "# unrelated edit\n", True)

    def test_partial_duplicate_and_modified_patches_refuse(self):
        for source in [bridge.EXPORTER_PATCH + bridge.EXPORTER_PATCH,
                       bridge.EXPORTER_PATCH.replace("episode >= -1", "episode >= -2"),
                       "# BEGIN Plex special-episode identity compatibility\n"]:
            for enabled in (True, False):
                with self.subTest(enabled=enabled), self.assertRaises(ValueError):
                    bridge.render_exporter(source, enabled)

    def test_only_matching_numbered_special_uses_its_existing_onscreen_identity(self):
        for episode in (1, 7, 99, 100):
            label = f"S00E{episode:02d}"
            data = {"season": 0, "episode": episode, "onscreen_episode": label}
            before = dict(data)
            output = [f'<episode-num system="onscreen">{label}</episode-num>']
            scope = {"custom_data": data, "season": -1, "episode": episode - 1, "program_xml": output}
            exec(compile(textwrap.dedent(bridge.EXPORTER_PATCH), "reviewed-export-block", "exec"), scope)
            xml = ET.fromstring("<programme>" + "".join(output) + "</programme>")
            self.assertEqual([(e.get("system"), e.text) for e in xml], [("onscreen", label)])
            self.assertEqual(data, before)

    def test_regular_episodes_missing_or_conflicting_labels_and_invalid_numbers_keep_namespace(self):
        for season, episode, label in [(0, 6, "S01E07"), (1, 6, "S02E07"),
                                       (-1, 6, None), (-1, 6, "E7"),
                                       (-1, 6, "S00E08"), (-1, -2, "S00E-1")]:
            with self.subTest(season=season, episode=episode, label=label):
                output = []
                scope = {"custom_data": {"onscreen_episode": label}, "season": season,
                         "episode": episode, "program_xml": output}
                exec(compile(textwrap.dedent(bridge.EXPORTER_PATCH), "reviewed-export-block", "exec"), scope)
                self.assertEqual(output, [f'    <episode-num system="xmltv_ns">{season}.{episode}.</episode-num>'])

    def test_explicit_zero_episode_does_not_override_its_onscreen_identity(self):
        for season, label in [(3, "S04E00"), (-1, "S00E00")]:
            output = []
            scope = {"custom_data": {"onscreen_episode": label}, "season": season,
                     "episode": -1, "program_xml": output}
            exec(compile(textwrap.dedent(bridge.EXPORTER_PATCH), "reviewed-export-block", "exec"), scope)
            self.assertEqual(output, [])


if __name__ == "__main__":
    unittest.main()
