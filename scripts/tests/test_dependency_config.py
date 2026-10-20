"""Docker update coverage and application runtime policy regressions."""

import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("dependency_config", ROOT / "scripts/validate-dependency-config.py")
CONFIG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONFIG)


class DockerUpdateCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("acquire", "privotron", "ail-framework", "komga/ui"):
            target = self.root / "stacks" / name / "Dockerfile"
            target.parent.mkdir(parents=True)
            target.write_text("FROM scratch\n")
        self.config = {"updates": [{"package-ecosystem": "docker", "directories": ["/stacks/**"]}]}

    def validate(self, config):
        with patch.object(CONFIG, "ROOT", self.root), contextlib.redirect_stderr(io.StringIO()):
            CONFIG.validate_docker_coverage(config)

    def test_recursive_inventory_covers_nested_dockerfiles(self):
        self.validate(self.config)

    def test_new_uncovered_context_is_rejected(self):
        self.config["updates"][0]["directories"] = ["/stacks/acquire"]
        with self.assertRaises(SystemExit):
            self.validate(self.config)

    def test_overlapping_update_blocks_are_rejected(self):
        self.config["updates"].append({"package-ecosystem": "docker", "directory": "/stacks/acquire"})
        with self.assertRaises(SystemExit):
            self.validate(self.config)

    def test_split_groups_keep_complete_unique_ownership(self):
        self.config["updates"][0]["directories"] = ["/stacks/ail-framework", "/stacks/komga/ui"]
        self.config["updates"].append({"package-ecosystem": "docker", "directories": ["/stacks/acquire", "/stacks/privotron"]})
        self.validate(self.config)


class DockerIgnoreRequirementTests(unittest.TestCase):
    def check(self, ecosystem, versions):
        with contextlib.redirect_stderr(io.StringIO()):
            CONFIG.validate_docker_ignore_versions({
                "package-ecosystem": ecosystem,
                "ignore": [{"dependency-name": "example", "versions": versions}],
            })

    def test_image_tag_prefix_is_rejected_for_both_docker_managers(self):
        for ecosystem in ("docker", "docker-compose"):
            for version in ("v0.15.6", "v0.15.7", ">= v3.14"):
                with self.subTest(ecosystem=ecosystem, version=version), self.assertRaises(SystemExit):
                    self.check(ecosystem, [version])

    def test_numeric_versions_and_bundler_ranges_are_accepted(self):
        for ecosystem in ("docker", "docker-compose"):
            self.check(ecosystem, ["0.15.6", "0.15.7", ">= 3.14", "25.10", "~> 1.2, < 2.0", "1.2.3-beta.1"])

    def test_other_ecosystems_keep_their_native_requirement_syntax(self):
        self.check("npm", ["^1.0.0"])

    def test_invalid_or_empty_requirements_are_rejected(self):
        for version in (None, "", "*", "1.2,", "^1.0.0"):
            with self.subTest(version=version), self.assertRaises(SystemExit):
                self.check("docker-compose", [version])


class SelectedRuntimePolicyTests(unittest.TestCase):
    def setUp(self):
        self.config = yaml.safe_load((ROOT / ".github/dependabot.yml").read_text())
        self.docker = [item for item in self.config["updates"] if item["package-ecosystem"] == "docker"]

    def test_stoat_exclusions_use_numeric_requirement_syntax(self):
        compose = next(item for item in self.config["updates"] if item["package-ecosystem"] == "docker-compose")
        stoat = next(item for item in compose["ignore"] if item["dependency-name"] == "ghcr.io/stoatchat/*")
        self.assertEqual(stoat["versions"], ["0.15.6", "0.15.7"])
        CONFIG.validate_docker_ignore_versions(compose)

    def test_tracked_inventory_covers_each_dockerfile_once(self):
        CONFIG.validate_docker_coverage(self.config)

    def test_python_cap_applies_only_to_incompatible_applications(self):
        capped = [item for item in self.docker if {"dependency-name": "python", "versions": [">= 3.14"]} in item.get("ignore", [])]
        self.assertEqual(len(capped), 1)
        self.assertEqual(set(capped[0]["directories"]), {"/stacks/acquire", "/stacks/privotron"})
        self.assertNotIn("/stacks/ghunt", capped[0]["directories"])

    def test_interim_ubuntu_exclusion_preserves_other_selected_releases(self):
        general = next(item for item in self.docker if "/stacks/ail-framework" in item.get("directories", []))
        version_ignores = [item["versions"] for item in general["ignore"] if "versions" in item and item["dependency-name"] == "ubuntu"]
        self.assertEqual(version_ignores, [["25.10"]])
        self.assertIn("/stacks/hashcat", general["directories"])


if __name__ == "__main__":
    unittest.main()
