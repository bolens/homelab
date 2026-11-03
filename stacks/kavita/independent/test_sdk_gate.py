"""Unavailable SDKs skip optional probes; real compiler failures remain failures."""
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


class SDKGateTests(unittest.TestCase):
    def run_probes(self, version, cases):
        with tempfile.TemporaryDirectory(prefix="kavita-sdk-gate-") as directory:
            root = Path(directory)
            marker = root / "compiler-called"
            compiler = root / "dotnet"
            listing = "" if version is None else version + " [/fixture/sdk]"
            compiler.write_text(
                '#!/bin/sh\nif [ "$1" = "--list-sdks" ]; then\n'
                "printf '%s' " + shlex.quote(listing) + '\nexit 0\nfi\n'
                'if [ "$1" = "--version" ]; then\n'
                + ('exit 42\n' if version is None else "printf '%s\\n' " + shlex.quote(version) + '\nexit 0\n')
                + 'fi\n'
                + "printf 'called\\n' >> " + shlex.quote(str(marker)) + '\nexit 42\n')
            compiler.chmod(0o755)
            node = root / "node"
            node.write_text("#!/bin/sh\nexit 42\n")
            node.chmod(0o755)
            environment = dict(os.environ, PATH=str(root)+os.pathsep+os.environ.get("PATH", ""),
                               KAVITA_MODEL_ASSEMBLY=str(root/"unread-model.dll"),
                               KAVITA_PATCHED_SOURCE=str(root/"unread-source"))
            result = subprocess.run([sys.executable, "-B", "-m", "unittest", "-v", *cases],
                                    cwd=HERE, env=environment, capture_output=True, text=True, timeout=30)
            return result, marker.exists()

    def test_older_SDKs_skip_all_five_probes_before_build_or_optional_input_reads(self):
        cases = ["test_action_policy.ActionPolicyTests", "test_capabilities.CapabilityRuntimeTests",
                 "test_native_dtos.NativeDtoTests", "test_exact_want_to_read.ExactWantToReadTests",
                 "test_native_queue.NativeQueueTests"]
        for version in ("8.0.400", "9.0.300"):
            with self.subTest(version=version):
                result, compiled = self.run_probes(version, cases)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                self.assertEqual(result.stderr.count("requires .NET 10 SDK"), 5, result.stderr)
                self.assertFalse(compiled)

    def test_runtime_without_any_SDK_skips_before_version_or_build(self):
        cases = ["test_action_policy.ActionPolicyTests", "test_capabilities.CapabilityRuntimeTests",
                 "test_native_dtos.NativeDtoTests", "test_exact_want_to_read.ExactWantToReadTests",
                 "test_native_queue.NativeQueueTests"]
        result, compiled = self.run_probes(None, cases)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertEqual(result.stderr.count("requires .NET 10 SDK"), 5, result.stderr)
        self.assertFalse(compiled)

    def test_supported_SDK_build_failure_is_fatal(self):
        result, compiled = self.run_probes("10.0.403", ["test_action_policy.ActionPolicyTests"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAILED", result.stderr)
        self.assertTrue(compiled)


if __name__ == "__main__":
    unittest.main()
