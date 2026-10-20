"""Render optional stack contracts without reading live config or using Docker's daemon."""

import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class WriterProtocolContractTests(unittest.TestCase):
    def test_both_images_ship_identical_writer_protocol(self):
        self.assertEqual((ROOT/'stacks/mylar3/config/media_writer.py').read_bytes(),
                         (ROOT/'stacks/komga/normalizer/media_writer.py').read_bytes())


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

    def test_coordination_preparation_requires_existing_state_and_preserves_settings(self):
        target=self.fixture('komga','docker-compose.coordination.yml')
        scripts=self.root/'scripts';scripts.mkdir()
        shutil.copy2(ROOT/'scripts/prepare-stack-lib.sh',scripts)
        shutil.copy2(ROOT/'stacks/komga/prepare-coordination.sh',target)
        shared=self.root/'missing'/'protocol'
        (target/'stack.env').write_text(f'MYLAR_WRITER_STATE_PATH={shared}\n')
        def prepare():
            return subprocess.run(['bash','prepare-coordination.sh'],cwd=target,
                                  env={'PATH':os.environ['PATH']},capture_output=True,text=True)
        self.assertNotEqual(prepare().returncode,0)
        self.assertFalse(shared.parent.exists())
        shared.mkdir(parents=True)
        before=(target/'stack.env').read_bytes()
        self.assertEqual(prepare().returncode,0);self.assertEqual(prepare().returncode,0)
        self.assertEqual((target/'stack.env').read_bytes(),before)
        self.assertEqual(list(shared.iterdir()),[])

    def test_writer_coordination_mount_is_narrow_and_requires_existing_storage(self):
        override='docker-compose.normalizer.yml'
        target=self.fixture('komga',override,'MYLAR_WRITER_STATE_PATH=/tmp/fixture-writer-state')
        extra='docker-compose.coordination.yml'
        shutil.copy2(ROOT/'stacks/komga'/extra,target)
        command=[self.docker,'compose','--env-file','stack.env','-f','docker-compose.yml',
                 '-f',override,'-f',extra,'config','--format','json']
        result=subprocess.run(command,cwd=target,env={'PATH':os.environ['PATH'],'HOME':str(self.root)},
                              capture_output=True,text=True,check=True,timeout=30)
        services=json.loads(result.stdout)['services']
        mounts={m['target']:m for m in services['comic-normalizer']['volumes']}
        self.assertFalse(mounts['/mylar-writer'].get('read_only',False))
        # Compose versions may omit false-valued fields from normalized JSON.
        self.assertFalse(mounts['/mylar-writer'].get('bind', {}).get('create_host_path', False))
        self.assertTrue(mounts['/mylar']['read_only'])
        self.assertNotIn('/mylar-writer',{m['target'] for m in services['komga']['volumes']})

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

    def test_recurring_packs_override_changes_only_command_and_health(self):
        target = self.fixture("komga", "docker-compose.normalizer.yml", "\n".join([
            f"MYLAR_DDL_CACHE_PATH={self.root}/ddl-cache",
            f"MYLAR_WRITER_STATE_PATH={self.root}/writer-state",
        ]))
        overrides = ["docker-compose.normalizer.yml", "docker-compose.maintenance.yml",
                     "docker-compose.coordination.yml"]
        for name in [*overrides[1:], "docker-compose.packs.yml"]:
            shutil.copy2(ROOT / "stacks/komga" / name, target)

        def model(extra=()):
            command = [self.docker, "compose", "--env-file", "stack.env",
                       "-f", "docker-compose.yml"]
            for name in [*overrides, *extra]:
                command.extend(["-f", name])
            result = subprocess.run(
                [*command, "config", "--format", "json"], cwd=target,
                env={"PATH": os.environ["PATH"], "HOME": str(self.root)},
                capture_output=True, text=True, check=True, timeout=30,
            )
            return json.loads(result.stdout)

        before, after = model(), model(["docker-compose.packs.yml"])
        old_worker = before["services"]["comic-normalizer"]
        new_worker = after["services"]["comic-normalizer"]
        self.assertIsNone(old_worker.pop("command", None))
        self.assertEqual(new_worker.pop("command"), ["--packs-only"])
        self.assertEqual(old_worker["healthcheck"].pop("test"),
                         ["CMD", "python3", "/app/normalize.py", "--health"])
        self.assertEqual(new_worker["healthcheck"].pop("test"),
                         ["CMD", "python3", "/app/normalize.py", "--packs-only", "--health"])
        self.assertEqual(before, after)

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


class HarborInstallerContractTests(unittest.TestCase):
    """Harbor remains an installer pointer; preparation never applies an upgrade."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.stack = self.root / "stacks/harbor"
        self.stack.mkdir(parents=True)
        scripts = self.root / "scripts"
        scripts.mkdir()
        shutil.copy2(ROOT / "scripts/prepare-stack-lib.sh", scripts)
        for name in ("prepare-stack.sh", "stack.env.example",
                     "docker-compose.override.yml.example", "caddy_snippet.conf.example"):
            shutil.copy2(ROOT / "stacks/harbor" / name, self.stack)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "docker.log"
        self.acl_log = self.root / "acl.log"
        docker = self.bin / "docker"
        docker.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$*" >> "$FIXTURE_DOCKER_LOG"\n'
            'case "$*" in\n'
            ' info) exit 0 ;;\n'
            ' "network inspect ingress-admin") test -f "$FIXTURE_NETWORK" ;;\n'
            ' "network create ingress-admin") : > "$FIXTURE_NETWORK" ;;\n'
            ' *) exit 91 ;;\n'
            'esac\n', encoding="utf-8")
        docker.chmod(0o755)
        acl = self.bin / "setfacl"
        acl.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$FIXTURE_ACL_LOG"\n', encoding="utf-8")
        acl.chmod(0o755)

    def prepare(self):
        result = subprocess.run(
            ["bash", str(self.stack / "prepare-stack.sh")], cwd=self.stack,
            env={"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": str(self.root),
                 "FIXTURE_DOCKER_LOG": str(self.log),
                 "FIXTURE_NETWORK": str(self.root / "network-created"),
                 "FIXTURE_ACL_LOG": str(self.acl_log)},
            capture_output=True, text=True, check=False, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_installer_and_proxy_versions_must_move_together(self):
        override = (ROOT / "stacks/harbor/docker-compose.override.yml.example").read_text()
        readme = (ROOT / "stacks/harbor/README.md").read_text()
        version = re.search(r"image: goharbor/nginx-photon:v(\d+\.\d+\.\d+)\s", override).group(1)
        installers = re.findall(r"harbor-offline-installer-v(\d+\.\d+\.\d+)\.tgz", readme)
        self.assertTrue(installers)
        self.assertEqual(set(installers), {version})
        self.assertIn(f"The example targets **{version}**", readme)
        self.assertIn(f"goharbor/nginx-photon:v{version}", readme)
        self.assertIn("Updating only `proxy.image` is insufficient", readme)
        self.assertIn("!reset []", override)
        self.assertEqual(len(re.findall(r"^\s+image:", override, re.M)), 1)

    def test_security_defaults_are_explicit_review_not_preparation_mutation(self):
        readme = (ROOT / "stacks/harbor/README.md").read_text()
        for option in ("network.allow_private_network_access",
                       "content_trust.legacy_signer_pull_enabled"):
            self.assertIn(option, readme)
        self.assertIn("allow_private_network_access: false", readme)
        self.assertIn("legacy_signer_pull_enabled: false", readme)
        self.assertIn("User-Agent is spoofable", readme)
        self.assertIn("private, loopback, link-local and cloud", readme)
        self.assertIn("does not bypass the vulnerability-prevention policy", readme)
        metadata = (ROOT / "stacks/harbor/stack.yaml").read_text()
        self.assertIn("recommended_backup: true", metadata)
        self.assertIn("priority: high", metadata)
        env = (ROOT / "stacks/harbor/stack.env.example").read_text()
        self.assertTrue(all(not line.strip() or line.lstrip().startswith("#")
                            for line in env.splitlines()))
        prepare = (ROOT / "stacks/harbor/prepare-stack.sh").read_text()
        self.assertNotIn("allow_private_network_access", prepare)
        self.assertNotIn("legacy_signer_pull_enabled", prepare)

    def test_external_network_preparation_precedes_installer_start(self):
        readme = (ROOT / "stacks/harbor/README.md").read_text()
        fresh = readme.split("4. **Prepare**", 1)[1].split("6. **Caddy**", 1)[0]
        wrapper = "(cd .. && ./prepare-stack.sh)"
        self.assertEqual(fresh.count(wrapper), 2)
        first, second = fresh.index(wrapper), fresh.rindex(wrapper)
        self.assertLess(first, fresh.index("sudo ./prepare"))
        self.assertLess(fresh.index("sudo ./prepare"), second)
        self.assertLess(second, fresh.index("sudo ./install.sh"))
        portainer = readme.split("### Deploying via Portainer", 1)[1].split("## Harbor behind Caddy", 1)[0]
        self.assertLess(portainer.index("Before any start"), portainer.index("./install.sh"))

    def test_fresh_preparation_copies_reference_without_starting_or_creating_install(self):
        for _ in range(2):
            self.prepare()
        for target, source in (("stack.env", "stack.env.example"),
                               (".env", "stack.env.example"),
                               ("docker-compose.override.yml", "docker-compose.override.yml.example"),
                               ("caddy_snippet.conf", "caddy_snippet.conf.example")):
            self.assertEqual((self.stack / target).read_bytes(), (self.stack / source).read_bytes())
        self.assertFalse((self.stack / "harbor").exists())
        self.assertFalse(self.acl_log.exists())
        calls = self.log.read_text().splitlines()
        self.assertEqual(calls.count("network create ingress-admin"), 1)
        self.assertEqual(calls, ["info", "network inspect ingress-admin", "network create ingress-admin",
                                 "info", "network inspect ingress-admin"])

    def test_existing_private_configuration_and_active_overrides_survive_repeat(self):
        sentinel = "fixture-only-preserved-secret"
        original = {"stack.env": f"HARBOR_FIXTURE_SECRET={sentinel}\n",
                    "docker-compose.override.yml": "# existing reference override\n",
                    "caddy_snippet.conf": "# existing ingress\n",
                    "harbor/harbor.yml": f"harbor_admin_password: {sentinel}\n",
                    "harbor/docker-compose.override.yml": "# installed operator override\n",
                    "harbor/common/config/nginx/nginx.conf": "# generated nginx config\n"}
        frames = {}
        for relative, text in original.items():
            path = self.stack / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            frames[relative] = path.stat()
        for _ in range(2):
            result = self.prepare()
            self.assertNotIn(sentinel, result.stdout + result.stderr)
        for relative, text in original.items():
            path = self.stack / relative
            self.assertEqual(path.read_text(), text)
            if relative.endswith("nginx.conf"):
                # ACL calls are recorded, not executed; their real metadata effect
                # is deliberately outside this no-permission-mutation fixture.
                continue
            before, after = frames[relative], path.stat()
            for key in ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink",
                        "st_size", "st_mtime_ns", "st_ctime_ns"):
                self.assertEqual(getattr(before, key), getattr(after, key), (relative, key))
        self.assertEqual((self.stack / ".env").read_text(), original["stack.env"])
        self.assertEqual(self.acl_log.read_text().splitlines(),
                         [f"-m u:10000:r {self.stack}/harbor/common/config/nginx/nginx.conf"] * 2)
        self.assertTrue(all(line in ("info", "network inspect ingress-admin", "network create ingress-admin")
                            for line in self.log.read_text().splitlines()))


if __name__ == "__main__":
    unittest.main()
