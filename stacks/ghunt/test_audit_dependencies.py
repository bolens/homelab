"""Narrow GHunt metadata exception and build-context regression controls."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("ghunt_dependency_audit", HERE / "audit-dependencies.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
KNOWN = "ghunt 2.3.4 has requirement pillow<11.0.0,>=10.4.0, but you have pillow 12.3.0."
VERSIONS = {"ghunt": "2.3.4", "pillow": "12.3.0"}

class DependencyAuditTests(unittest.TestCase):
    def result(self, code=1, out=KNOWN, err=""):
        return subprocess.CompletedProcess([], code, out + "\n", err)

    def test_clean_metadata_needs_no_exception(self):
        self.assertEqual(audit.validate(self.result(0, "No broken requirements found."), {}), "clean")

    def test_only_exact_documented_pillow_pair_is_accepted(self):
        self.assertEqual(audit.validate(self.result(), VERSIONS), "documented-pillow-override")
        for versions in ({"ghunt": "2.3.5", "pillow": "12.3.0"}, {"ghunt": "2.3.4", "pillow": "12.3.1"}, {}):
            with self.subTest(versions=versions), self.assertRaises(audit.Refused):
                audit.validate(self.result(), versions)

    def test_missing_or_incompatible_parent_dependencies_refuse(self):
        errors = [
            "alive-progress 3.3.0 has requirement about-time==4.2.1, but you have about-time 4.2.2.",
            "ghunt 2.3.4 has requirement autoslot<2023.0.0,>=2022.12.1, but you have autoslot 2025.11.1.",
            "anyio 4.15.1 requires typing-extensions, which is not installed.",
            "ghunt 2.3.4 has requirement rich<14.0.0,>=13.9.1, but you have rich 15.0.0.",
        ]
        for error in errors:
            for out in (error, KNOWN + "\n" + error):
                with self.subTest(error=error), self.assertRaises(audit.Refused):
                    audit.validate(self.result(out=out), VERSIONS)

    def test_unexpected_status_stdout_stderr_and_duplicates_refuse(self):
        for result in (self.result(0), self.result(1, ""), self.result(2), self.result(1, KNOWN + "\n" + KNOWN), self.result(1, KNOWN, "unexpected"), self.result(0, "unexpected")):
            with self.subTest(result=result), self.assertRaises(audit.Refused):
                audit.validate(result, VERSIONS)

    def test_main_calls_actual_interpreter_pip_check_without_network_flags(self):
        with patch.object(audit.subprocess, "run", return_value=self.result()) as run, patch.object(audit.metadata, "version", side_effect=lambda n: VERSIONS[n]), patch("builtins.print"):
            audit.main()
        self.assertEqual(run.call_args.args[0], [audit.sys.executable, "-I", "-B", "-m", "pip", "check"])
        self.assertTrue(run.call_args.kwargs["capture_output"])
        self.assertEqual(run.call_args.kwargs["timeout"], 30)

    def test_image_runs_audit_after_install_and_context_allows_only_own_script(self):
        text = (HERE / "Dockerfile").read_text()
        self.assertIn("COPY audit-dependencies.py /tmp/audit-dependencies.py", text)
        self.assertIn("&& python -I -B /tmp/audit-dependencies.py", text)
        self.assertEqual((HERE / ".dockerignore").read_text().splitlines(), ["**", "!Dockerfile", "!requirements.txt", "!audit-dependencies.py"])

if __name__ == "__main__":
    unittest.main()
