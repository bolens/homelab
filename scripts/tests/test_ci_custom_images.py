"""Regression tests for custom-image CI selection."""

import importlib.util
import json
import os
import subprocess
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("ci_custom_images", ROOT / "scripts/ci-custom-images.py")
CI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CI)


class ImageSelectionTests(unittest.TestCase):
    def setUp(self):
        self.images = json.loads((ROOT / ".github/custom-images.json").read_text())

    def test_full_run_keeps_every_image(self):
        self.assertEqual(CI.select(self.images, None, full=True), self.images)

    def test_empty_selection(self):
        self.assertEqual(CI.select(self.images, []), [])

    def test_single_and_shared_contexts(self):
        for image in self.images:
            self.assertEqual(CI.select(self.images, [image["image"]]), [image])
            self.assertIn(image["context"] + "/**", CI.filters(self.images)[image["image"]])
        contexts = [image for image in self.images if image["context"] == "stacks/ail-framework"]
        self.assertEqual(len(contexts), 2)
        self.assertEqual(CI.select(self.images, [image["image"] for image in contexts]), contexts)

    def test_shared_inputs_select_all_filters(self):
        for patterns in CI.filters(self.images).values():
            for shared in CI.SHARED:
                self.assertIn(shared, patterns)

    def test_invalid_detection_fails(self):
        for changed in (None, "", {}, ["unknown"], [None]):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                CI.select(self.images, changed)

    def test_duplicate_inventory_fails(self):
        with self.assertRaises(ValueError):
            CI.select(self.images + self.images[:1], [], full=True)

    def test_inventory_inputs_exist(self):
        for image in self.images:
            self.assertTrue((ROOT / image["context"]).is_dir())
            self.assertTrue((ROOT / image["dockerfile"]).is_file())

    def test_every_stack_dockerfile_has_a_publication_decision(self):
        # Keep reasons aligned with documents/CUSTOM-IMAGES.md. A new Dockerfile
        # must enter the publish matrix or receive a reviewed exclusion.
        excluded = {
            "stacks/ail-framework/Dockerfile.build",  # Untracked vendor source.
            "stacks/ail-framework/Dockerfile.runtime",  # Requires the local build.
            "stacks/searx-ng/Dockerfile.4get",  # Operator-managed unlicensed source.
            "stacks/searx-ng/Dockerfile.4get-sidecar",  # Same source restriction.
        }
        dockerfiles = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "stacks").rglob("*")
            if path.is_file() and "Dockerfile" in path.name
            and "repo" not in path.relative_to(ROOT).parts
        }
        published = {image["dockerfile"] for image in self.images}
        self.assertFalse(published & excluded)
        self.assertEqual(dockerfiles, published | excluded)


class MylarInstalledGateTests(unittest.TestCase):
    """Exercise the workflow shell without a Docker daemon or image pulls."""

    def invoke(self, failed_command=None):
        workflow = (ROOT / ".github/workflows/repository-validation.yml").read_text()
        section = workflow.split("  mylar-image:\n", 1)[1].split("  comic-maintenance:\n", 1)[0]
        body = section.split("        run: |\n", 1)[1]
        script = "\n".join(line[10:] for line in body.splitlines() if line.strip())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stack = root / "stacks/mylar3"
            stack.mkdir(parents=True)
            (stack / "Dockerfile").write_bytes((ROOT / "stacks/mylar3/Dockerfile").read_bytes())
            log = root / "calls.jsonl"
            docker = root / "docker"
            docker.write_text("""#!/usr/bin/env python3
import json,os,sys
args=sys.argv[1:]
body=sys.stdin.read() if args[0]=='build' else ''
with open(os.environ['CI_GATE_LOG'],'a') as output:
 output.write(json.dumps([args,body])+'\\n')
if args[0]==os.environ.get('CI_GATE_FAIL'):sys.exit(13)
""")
            docker.chmod(0o755)
            verifier = stack / "verify-image.sh"
            verifier.write_text("""#!/usr/bin/env python3
import json,os,sys
with open(os.environ['CI_GATE_LOG'],'a') as output:
 output.write(json.dumps([['verify',*sys.argv[1:]],''])+'\\n')
assert sys.argv[1]=='mylar-ci-installed'
""")
            verifier.chmod(0o755)
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script], cwd=root,
                                    env=dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'],
                                             CI_GATE_LOG=str(log), CI_GATE_FAIL=failed_command or ""),
                                    text=True, capture_output=True)
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            return result, calls

    def test_base_source_is_installed_before_exact_origin_gate(self):
        result, calls = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([call[0][0] for call in calls], ['pull', 'build', 'verify'])
        self.assertIn('@sha256:', calls[0][0][1])
        self.assertIn('--network=none', calls[1][0])
        self.assertIn('FROM ' + calls[0][0][1] + '\n', calls[1][1])
        self.assertIn('COPY config/ /opt/mylar3-fixes/', calls[1][1])
        self.assertIn('apply_patches.py /app/mylar3/mylar', calls[1][1])
        self.assertEqual(calls[2][0], ['verify', 'mylar-ci-installed'])

    def test_failed_pull_never_builds_or_verifies(self):
        result, calls = self.invoke('pull')
        self.assertEqual(result.returncode, 13)
        self.assertEqual([call[0][0] for call in calls], ['pull'])

    def test_failed_install_never_runs_verifier(self):
        result, calls = self.invoke('build')
        self.assertEqual(result.returncode, 13)
        self.assertEqual([call[0][0] for call in calls], ['pull', 'build'])


if __name__ == "__main__":
    unittest.main()
