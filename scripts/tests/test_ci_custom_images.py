"""Regression tests for custom-image CI selection."""

import ast
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
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


class AilBuildContractTests(unittest.TestCase):
    def test_final_stage_uses_completed_variant_and_runtime_patches(self):
        body = (ROOT / "stacks/ail-framework/Dockerfile.build").read_text()
        stages = [line for line in body.splitlines() if line.startswith("FROM ")]
        self.assertEqual(len(stages), 3)
        self.assertRegex(stages[0], r"^FROM ubuntu:22[.]04@sha256:[0-9a-f]{64} AS native_builder$")
        self.assertEqual(stages[1:], ["FROM native_builder AS variant_builder", "FROM scratch"])
        variant, final = body.split("FROM native_builder AS variant_builder", 1)[1].split("FROM scratch", 1)
        self.assertIn("ARG AIL_TORCH_VARIANT=cpu", variant)
        self.assertIn("AIL_TORCH_VARIANT=${AIL_TORCH_VARIANT}", variant)
        self.assertIn("apt-get purge -y", variant)
        self.assertIn("COPY --from=variant_builder / /", final)
        self.assertIn("/opt/AIL/AILENV/bin/pip install --require-hashes", final)
        for name in ("requirements-runtime.txt", "ail-dark-mode.css", "ail-dark-mode.js"):
            self.assertIn("COPY " + name + " /tmp/" + name, final)
        for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
            self.assertIn(variable + "=1", final)
        self.assertIn("host = 0.0.0.0", final)
        self.assertIn("/opt/AIL/bin/LAUNCH.sh", final)
        self.assertTrue(final.rstrip().endswith('ENTRYPOINT ["/bin/bash", "/opt/AIL/docker_start.sh"]'))

    def test_documented_variants_have_no_external_intermediate(self):
        stack = ROOT / "stacks/ail-framework"
        self.assertFalse((stack / "Dockerfile.runtime").exists())
        readme = (stack / "README.md").read_text()
        self.assertEqual(readme.count("docker build -f Dockerfile.build"), 2)
        for expected in ("AIL_TORCH_VARIANT=cpu", "AIL_TORCH_VARIANT=gpu", "-t ail-framework:7.0 .", "-t ail-framework:7.0-gpu ."):
            self.assertIn(expected, readme)
        for obsolete in ("Dockerfile.runtime", "BASE_IMAGE=", "7.0-cpu-build", "7.0-gpu-build"):
            self.assertNotIn(obsolete, readme)


class PythonRuntimeContractTests(unittest.TestCase):
    def test_acquire_keeps_dissect_compatible_python(self):
        stages = [line for line in (ROOT / "stacks/acquire/Dockerfile").read_text().splitlines()
                  if line.startswith("FROM ")]
        self.assertEqual(len(stages), 1)
        self.assertRegex(stages[0], r"^FROM python:3[.]13-slim-bookworm@sha256:[0-9a-f]{64}$")

    def test_privotron_keeps_both_lock_compatible_stages(self):
        stages = [line for line in (ROOT / "stacks/privotron/Dockerfile").read_text().splitlines()
                  if line.startswith("FROM ")]
        self.assertEqual(len(stages), 2)
        self.assertRegex(stages[0], r"^FROM python:3[.]13-slim-bookworm@sha256:[0-9a-f]{64} AS builder$")
        self.assertEqual(stages[1], stages[0].removesuffix(" AS builder"))


class MylarStagePreservationTests(unittest.TestCase):
    """Preserve checked external-tree patches across the real final COPY routes."""

    STACK = ROOT / "stacks/mylar3"

    def copy_checked_artifact(self, body, checked, final, artifact):
        stage = body.rsplit("\nFROM ", 1)[1]
        for line in stage.splitlines():
            if not line.startswith("COPY --from=checked "):
                continue
            fields = shlex.split(line)
            for source in fields[2:-1]:
                if source == artifact:
                    target = fields[-1]
                    if target.endswith("/"):
                        target += Path(source).name
                elif source.endswith("/") and artifact.startswith(source):
                    target = fields[-1].rstrip("/") + "/" + artifact[len(source):]
                else:
                    continue
                destination = final / target.lstrip("/")
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(checked / artifact.lstrip("/"), destination)

    def test_final_stage_preserves_real_mega_patch_and_checks_installed_guard(self):
        config = self.STACK / "config"
        fixture = config / "test_fixtures/cache_admission/mega_library.py.txt"
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-c",
             "import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
             "import patch_cache_admission as patch; "
             "sys.stdout.write(patch.mega_library(Path(sys.argv[2]).read_text()))",
             str(config), str(fixture)], capture_output=True, text=True, check=True)
        original = fixture.read_text()
        patched = result.stdout
        self.assertNotEqual(original, patched)
        body = (self.STACK / "Dockerfile").read_text()
        artifact = "/app/mylar3/lib/mega/mega.py"
        with tempfile.TemporaryDirectory() as directory:
            checked, final = Path(directory) / "checked", Path(directory) / "final"
            for root, content in ((checked, patched), (final, original)):
                leaf = root / artifact.lstrip("/")
                leaf.parent.mkdir(parents=True)
                leaf.write_text(content)
            self.copy_checked_artifact(body, checked, final, artifact)
            installed = final / artifact.lstrip("/")
            self.assertEqual(installed.read_text(), patched)
            stage = body.rsplit("\nFROM ", 1)[1]
            guard = next(shlex.split(line)[-1] for line in stage.splitlines()
                         if line.startswith("RUN python3 -I -B -c ")
                         and artifact in line)
            # Execute the actual final-stage assertion with only its fixed path
            # projected into the disposable checked/final file trees.
            def verify(path):
                tree = ast.parse(guard)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and node.value == artifact:
                        node.value = str(path)
                return subprocess.run(
                    [sys.executable, "-I", "-B", "-c", ast.unparse(tree)],
                    capture_output=True, text=True)
            self.assertEqual(verify(installed).returncode, 0)
            installed.write_text(original)
            self.assertNotEqual(verify(installed).returncode, 0)

    def test_final_stage_preserves_external_workflow_template(self):
        artifact = "/app/mylar3/data/interfaces/default/workflow.html"
        content = (self.STACK / "config/workflow.html").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            checked, final = Path(directory) / "checked", Path(directory) / "final"
            source = checked / artifact.lstrip("/")
            source.parent.mkdir(parents=True)
            source.write_bytes(content)
            self.copy_checked_artifact((self.STACK / "Dockerfile").read_text(),
                                       checked, final, artifact)
            self.assertEqual((final / artifact.lstrip("/")).read_bytes(), content)


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
