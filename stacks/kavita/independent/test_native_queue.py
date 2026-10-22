"""Native SQLite queue and real authenticated gateway; all upstream calls are fixtures."""
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent


@unittest.skipUnless(os.environ.get("KAVITA_PATCHED_SOURCE") and shutil.which("dotnet"),
                     "set KAVITA_PATCHED_SOURCE to a freshly patched isolated pinned export")
class NativeQueueTests(unittest.TestCase):
    def test_native_queue_gateway_restart_and_failure_recovery(self):
        source = Path(os.environ["KAVITA_PATCHED_SOURCE"])
        project = source / "Kavita.Services.Tests/Kavita.Services.Tests.csproj"
        reference = '<ItemGroup><ProjectReference Include="../Kavita.Server/Kavita.Server.csproj" /></ItemGroup>'
        if reference not in project.read_text():
            project.write_text(project.read_text().replace('</Project>', reference + '\n</Project>'))
        fixture = source / "Kavita.Services.Tests/IndependentQueueTests.cs"
        expected = (HERE / "IndependentQueueTests.cs").read_bytes()
        if fixture.exists():
            self.assertEqual(fixture.read_bytes(), expected, "native fixture path already has different content")
        else:
            fixture.write_bytes(expected)
        with tempfile.TemporaryDirectory(prefix="kavita-native-queue-") as raw:
            root = Path(raw)
            key = root / "key"
            key.write_text("native-fixture-key-123456789012345678901234")
            key.chmod(0o600)
            with (root / "gateway.stderr").open("w") as stderr:
                server = subprocess.Popen([sys.executable, str(HERE / "native_queue_fixture.py"), "controller", str(root / "gateway.db")],
                                          stdout=subprocess.PIPE, stderr=stderr, text=True)
                try:
                    self.assertTrue(select.select([server.stdout], [], [], 20)[0], "gateway fixture not ready")
                    ports = json.loads(server.stdout.readline())
                    env = {**os.environ, "KAVITA_PROVIDER_URL": ports["gateway"],
                           "KAVITA_QUEUE_CONTROL": ports["control"], "KAVITA_PROVIDER_ACTIONS_FILE": str(root / "actions.json"), "KAVITA_PROVIDER_KEY_FILE": str(key)}
                    result = subprocess.run(["dotnet", "test", str(source / "Kavita.Services.Tests/Kavita.Services.Tests.csproj"),
                                             "-c", "Release", "--filter", "FullyQualifiedName~IndependentQueueTests.Native_",
                                             "--logger", "trx;LogFileName=queue.trx", "--results-directory", str(root)],
                                            env=env, capture_output=True, text=True, timeout=240)
                    self.assertEqual(result.returncode, 0, "\n".join(line for line in result.stdout.splitlines() if ": error " in line) + result.stdout[-10000:] + result.stderr[-2000:] + (root / "gateway.stderr").read_text()[-2000:])
                    counters = ET.parse(root / "queue.trx").find(".//{*}Counters").attrib
                    self.assertEqual(counters["total"], "13")
                    self.assertEqual(counters["passed"], "13")
                finally:
                    server.terminate()
                    server.wait(timeout=15)
                    server.stdout.close()
