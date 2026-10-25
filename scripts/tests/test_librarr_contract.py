"""Validate Librarr preparation and integration examples without live services."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]


def environment(home):
    return {"PATH": os.environ["PATH"], "HOME": str(home)}


def fixture(root, stack):
    target = root / "stacks" / stack
    target.mkdir(parents=True)
    for name in ("docker-compose.yml", "stack.env.example", "prepare-stack.sh",
                 "caddy_snippet.conf.example", "sources.json.example",
                 "docker-compose.readers.yml", "docker-compose.librarr.yml", "docker-compose.flood.yml",
                 "docker-compose.nzbget.yml"):
        source = ROOT / "stacks" / stack / name
        if source.exists():
            shutil.copy2(source, target / name)
    return target


class LibrarrPreparationTests(unittest.TestCase):
    def prepare(self, root, stack):
        scripts = root / "scripts"
        scripts.mkdir(exist_ok=True)
        shutil.copy2(ROOT / "scripts/prepare-stack-lib.sh", scripts)
        stubdir = root / "bin"
        stubdir.mkdir(exist_ok=True)
        docker = stubdir / "docker"
        # Only daemon readiness is allowed; lifecycle or resource writes fail.
        docker.write_text('#!/bin/sh\n[ "$*" = info ] && exit 1\nexit 99\n')
        docker.chmod(0o755)
        env = environment(root)
        env["PATH"] = str(stubdir) + os.pathsep + env["PATH"]
        return subprocess.run(["bash", str(stack / "prepare-stack.sh")],
                              env=env, capture_output=True, text=True, check=False)

    def configure(self, root, media):
        stack = fixture(root, "librarr")
        state = root / "state"
        config = (stack / "stack.env.example").read_text()
        config = config.replace("/path/to/media", str(media))
        config = config.replace("/path/to/appdata/librarr", str(state))
        config = config.replace("replace-me-with-a-unique-password",
                                "fixture-secret-keep-out-of-output")
        (stack / "stack.env").write_text(config)
        return stack, state

    def test_missing_mount_refuses_without_creating_media_or_state(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            media = root / "absent-mount" / "media"
            stack, state = self.configure(root, media)
            result = self.prepare(root, stack)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(media.parent.exists())
            self.assertFalse(state.exists())
            self.assertIn("LIBRARR_MEDIA_PATH", result.stdout + result.stderr)
            self.assertNotIn(str(media), result.stdout + result.stderr)

    def test_repeat_preserves_env_sources_state_and_media(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            media = root / "media"
            media.mkdir()
            (media / "retain.epub").write_bytes(b"existing-media")
            stack, state = self.configure(root, media)
            first = self.prepare(root, stack)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(state.stat().st_mode & 0o777, 0o700)
            (state / "settings.json").write_text('{"retain":"fixture-secret-keep-out-of-output"}')
            (stack / "sources.json").write_text('{"version":1}')
            paths = [stack / "stack.env", stack / "sources.json",
                     stack / "caddy_snippet.conf", state / "settings.json",
                     media / "retain.epub"]
            before = {path: path.read_bytes() for path in paths}
            second = self.prepare(root, stack)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(before, {path: path.read_bytes() for path in paths})
            self.assertEqual((stack / ".env").read_bytes(), before[stack / "stack.env"])
            self.assertFalse((stack / "docker-compose.override.yml").exists())
            self.assertNotIn("fixture-secret-keep-out-of-output", second.stdout + second.stderr)


class LibrarrSourceContractTests(unittest.TestCase):
    def test_host_path_creation_is_explicitly_disabled_in_all_source_binds(self):
        for stack, name in (("librarr", "docker-compose.yml"),
                            ("kavita", "docker-compose.librarr.yml"),
                            ("komga", "docker-compose.librarr.yml")):
            source = yaml.safe_load((ROOT / "stacks" / stack / name).read_text())
            mounts = source["services"][stack]["volumes"]
            for mount in mounts:
                with self.subTest(stack=stack, target=mount["target"]):
                    self.assertIs(mount["bind"]["create_host_path"], False)


# Compose v2 omits false bind fields in JSON; explicit source values are checked above.
@unittest.skipUnless(shutil.which("docker"), "Docker Compose CLI unavailable")
class LibrarrComposeTests(unittest.TestCase):
    def render(self, stack, *overrides, extra="", remove=None):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = fixture(root, stack)
            config = (target / "stack.env.example").read_text() + "\n" + extra
            if remove:
                config = "\n".join(line for line in config.splitlines()
                                   if not line.startswith(remove + "="))
            (target / "stack.env").write_text(config)
            args = ["docker", "compose", "--env-file", str(target / "stack.env"),
                    "-f", str(target / "docker-compose.yml")]
            for override in overrides:
                args += ["-f", str(target / override)]
            result = subprocess.run(args + ["config", "--format", "json"],
                                    cwd=target, env=environment(root),
                                    capture_output=True, text=True, check=False)
            return result

    def model(self, stack, *overrides, extra=""):
        result = self.render(stack, *overrides, extra=extra)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_each_required_credential_and_storage_input_refuses_if_missing(self):
        for key in ("AUTH_USERNAME", "AUTH_PASSWORD", "API_KEY", "TORZNAB_API_KEY",
                    "LIBRARR_CONFIG_PATH", "LIBRARR_MEDIA_PATH"):
            with self.subTest(key=key):
                result = self.render("librarr", remove=key)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(key, result.stderr)

    def test_flood_adapter_is_private_and_uses_existing_readonly_socket(self):
        model = self.model('librarr', 'docker-compose.flood.yml',
                           extra='BRIDGE_USER=fixture\nBRIDGE_PASSWORD=fixture-password-not-a-secret\n')
        bridge = model['services']['librarr-flood-adapter']
        self.assertFalse(bridge.get('ports'))
        self.assertEqual(set(bridge['networks']), {'torrents'})
        self.assertTrue(bridge['read_only'])
        self.assertTrue(all(m['read_only'] for m in bridge['volumes']))
        app = model['services']['librarr']['environment']
        self.assertEqual(app['TORRENT_CLIENT'], 'transmission')
        self.assertEqual(app['QB_SAVE_PATH'], '/data/downloads/librarr/ebooks')
        self.assertEqual(app['REMOVE_TORRENT_AFTER_IMPORT'], 'false')
        self.assertTrue(model['volumes']['flood_rtorrent_socket']['external'])

    def test_nzbget_adapter_is_private_and_maps_existing_completed_root(self):
        model = self.model('librarr', 'docker-compose.nzbget.yml',
                           extra='SABNZBD_API_KEY=fixture-random-key-not-a-secret\nNZBGET_USERNAME=fixture\nNZBGET_PASSWORD=fixture-password-not-a-secret\n')
        bridge = model['services']['librarr-nzbget-adapter']
        self.assertFalse(bridge.get('ports'))
        self.assertEqual(set(bridge['networks']), {'media-automation'})
        self.assertTrue(bridge['read_only'])
        self.assertTrue(all(m['read_only'] for m in bridge['volumes']))
        self.assertEqual(bridge['environment']['LIBRARR_NZB_ROOT'],
                         '/data/downloads/usenet/completed/librarr')
        self.assertEqual(model['services']['librarr']['environment']['SABNZBD_CATEGORY'], 'librarr')

    def test_flood_and_nzbget_overrides_preserve_both_clients(self):
        model = self.model('librarr', 'docker-compose.flood.yml', 'docker-compose.nzbget.yml',
                           extra='BRIDGE_USER=fixture\nBRIDGE_PASSWORD=fixture-password\nSABNZBD_API_KEY=fixture-key\nNZBGET_USERNAME=fixture\nNZBGET_PASSWORD=fixture-password\n')
        app = model['services']['librarr']
        self.assertEqual(app['environment']['TORRENT_CLIENT'], 'transmission')
        self.assertEqual(app['environment']['SABNZBD_URL'], 'http://librarr-nzbget-adapter:8080')
        self.assertEqual(set(app['depends_on']), {'librarr-flood-adapter', 'librarr-nzbget-adapter'})

    def test_flood_accounts_use_persistent_runtime(self):
        model = self.model('flood')['services']['flood']
        self.assertIn('--rundir=/data', model['command'])
        self.assertTrue(any(m['target'] == '/data' and m['type'] == 'volume'
                            for m in model['volumes']))

    def test_default_exposure_and_payload_retention(self):
        model = self.model("librarr")
        app = model["services"]["librarr"]
        self.assertFalse(app.get("ports"))
        self.assertNotIn("ingress-public", app["networks"])
        self.assertFalse(app.get("privileged", False))
        self.assertEqual(app["environment"]["IMPORT_MODE"], "copy")
        self.assertEqual(app["environment"]["REMOVE_TORRENT_AFTER_IMPORT"], "false")
        self.assertEqual(app["environment"]["SCHEDULER_AUTO_DOWNLOAD"], "false")
        self.assertEqual(app["environment"]["ZLIBRARY_ENABLED"], "false")
        self.assertEqual(app["platform"], "linux/amd64")
        self.assertIn("@sha256:", app["image"])
        self.assertTrue(all(not v.get("bind", {}).get("create_host_path", False) for v in app["volumes"]))
        source = next(v for v in app["volumes"] if v["target"] == "/etc/librarr/sources.json")
        self.assertTrue(source["read_only"])

    def test_reader_network_is_an_explicit_addition(self):
        app = self.model("librarr", "docker-compose.readers.yml")["services"]["librarr"]
        self.assertEqual(set(app["networks"]),
                         {"ingress-admin", "media-automation", "torrents", "ingress-public"})
        self.assertFalse(app.get("ports"))

    def test_readers_share_exact_outputs_read_only_and_preserve_original_mounts(self):
        owner = self.model("librarr")["services"]["librarr"]
        owner_env = owner["environment"]
        for stack, targets in (("kavita", {"/data/librarr-books": "EBOOK_DIR",
                                           "/data/librarr-manga": "MANGA_DIR"}),
                               ("komga", {"/data/librarr-manga": "MANGA_DIR"})):
            with self.subTest(stack=stack):
                original = self.model(stack)["services"][stack]
                reader = self.model(stack, "docker-compose.librarr.yml",
                                    extra="LIBRARR_MEDIA_PATH=/path/to/media\n")["services"][stack]
                self.assertEqual(reader["networks"], original["networks"])
                for mount in original["volumes"]:
                    self.assertIn(mount, reader["volumes"])
                for target, key in targets.items():
                    mount = next(v for v in reader["volumes"] if v["target"] == target)
                    self.assertEqual(mount["source"], "/path/to/media" + owner_env[key][len("/data"):])
                    self.assertTrue(mount["read_only"])
                    self.assertFalse(mount.get("bind", {}).get("create_host_path", False))
                result = self.render(stack, "docker-compose.librarr.yml")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("LIBRARR_MEDIA_PATH", result.stderr)

    def test_audiobook_and_torrent_paths_match_existing_consumers(self):
        owner = self.model("librarr")["services"]["librarr"]
        env = owner["environment"]
        abs_app = self.model("audiobookshelf")["services"]["audiobookshelf"]
        mount = next(v for v in abs_app["volumes"] if v["target"] == "/audiobooks")
        self.assertTrue(mount["read_only"])
        self.assertEqual(env["AUDIOBOOK_DIR"], "/data/audiobooks/Librarr")
        qb = yaml.safe_load((ROOT / "stacks/qbittorrent/docker-compose.yml").read_text())
        self.assertEqual(qb["services"]["qbittorrent"]["network_mode"], "service:gluetun")
        self.assertIn("torrents", qb["services"]["gluetun"]["networks"])
        self.assertEqual(env["QB_SAVE_PATH"], env["INCOMING_DIR"])
        self.assertEqual(env["QB_MANGA_SAVE_PATH"], env["MANGA_INCOMING_DIR"])
        self.assertEqual(len({env[key] for key in ("QB_CATEGORY", "QB_AUDIOBOOK_CATEGORY",
                                                 "QB_MANGA_CATEGORY")}), 3)


if __name__ == "__main__":
    unittest.main()
