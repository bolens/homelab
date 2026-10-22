"""Exercise the actual C# manifest client against an isolated authenticated fixture."""
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

HERE = Path(__file__).resolve().parent


@unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK unavailable")
class CapabilityRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        version = subprocess.run(["dotnet", "--version"], capture_output=True, text=True, check=True).stdout
        if not version.startswith("10."):
            raise unittest.SkipTest("requires .NET 10 SDK")
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        shutil.copyfile(HERE / "IndependentProvider.cs", cls.root / "IndependentProvider.cs")
        shutil.copyfile(HERE / "IndependentScrobblePolicy.cs", cls.root / "IndependentScrobblePolicy.cs")
        shutil.copyfile(HERE / "IndependentOAuth.cs", cls.root / "IndependentOAuth.cs")
        (cls.root / "Probe.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework></PropertyGroup><ItemGroup><FrameworkReference Include="Microsoft.AspNetCore.App"/></ItemGroup></Project>')
        (cls.root / "Program.cs").write_text('''using System; using Kavita.Common;
if (args.Length > 0) {
  if (args[0] == "creation") {
    Console.WriteLine($"{await IndependentProvider.CanQueueScrobbleEvents()}:{IndependentProvider.KnownScrobbleAction(1, 3)}:{await IndependentProvider.ScrobbleAction(1, 3)}");
  }
  else if (args[0] == "expiry") {
    var expiry = await IndependentProvider.KnownTokenExpiry(int.Parse(args[1]), args[2]);
    Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(expiry));
  }
  else if (args[0] == "native-expiry") {
    try {
    var directory = System.IO.Path.GetDirectoryName(args[1])!;
    System.Runtime.Loader.AssemblyLoadContext.Default.Resolving += (context, name) => {
      var file = System.IO.Path.Combine(directory, name.Name + ".dll");
      return System.IO.File.Exists(file) ? context.LoadFromAssemblyPath(file) : null;
    };
    var type = System.Reflection.Assembly.LoadFrom(args[1]).GetType("Kavita.Services.Plus.ScrobblingService")!;
    var service = System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(type);
    var method = type.GetMethod("GetTokenExpiry", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)!;
    var provider = Enum.ToObject(method.GetParameters()[0].ParameterType, int.Parse(args[2]));
    var task = (System.Threading.Tasks.Task)method.Invoke(service, new object[] {provider, 1, args[3], System.Threading.CancellationToken.None})!;
    await task;
    Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(task.GetType().GetProperty("Result")!.GetValue(task)));
    } catch (Exception exception) { Console.Error.WriteLine(exception); Environment.ExitCode = 1; }
  }
  else if (args[0] == "authorize") Console.WriteLine(IndependentOAuth.ValidAuthorizationUrl(int.Parse(args[1]), args[2], args[3]));
  else { try { Console.WriteLine(IndependentOAuth.CallbackUrl); Console.WriteLine(IndependentOAuth.SettingsUrl); } catch { Console.WriteLine("invalid"); } }
  return;
}
Console.WriteLine((await IndependentProvider.Manifest()).GetRawText()); Console.WriteLine(await IndependentProvider.Has("metadata"));''')
        subprocess.run(["dotnet", "build", "-v", "quiet"], cwd=cls.root, check=True, capture_output=True, timeout=60)
        cls.key = "isolated-test-key-" + "x" * 32
        (cls.root / "key").write_text(cls.key)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def probe(self, manifest=None, status=200):
        observed = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                observed.append(dict(self.headers))
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(manifest).encode())
            def log_message(self, *args):
                pass
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            env = os.environ.copy()
            env["KAVITA_PROVIDER_KEY_FILE"] = str(self.root / "key")
            env["KAVITA_PROVIDER_ACTIONS_FILE"] = str(self.root / "actions.json")
            if manifest is not None:
                env["KAVITA_PROVIDER_URL"] = f"http://127.0.0.1:{server.server_port}"
            else:
                env.pop("KAVITA_PROVIDER_URL", None)
            result = subprocess.run(["dotnet", str(self.root / "bin/Debug/net10.0/Probe.dll")],
                                    env=env, check=True, capture_output=True, text=True, timeout=20)
            lines = result.stdout.strip().splitlines()
            return json.loads(lines[-2]), lines[-1], observed
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def expiry_probe(self, response, status=200, native=False, provider=2):
        observed = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                observed.append({"path": self.path, "headers": dict(self.headers), "body": body})
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            def log_message(self, *args):
                pass
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            env = os.environ.copy()
            env["KAVITA_PROVIDER_URL"] = f"http://127.0.0.1:{server.server_port}"
            env["KAVITA_PROVIDER_KEY_FILE"] = str(self.root / "key")
            env["KAVITA_PROVIDER_ACTIONS_FILE"] = str(self.root / "actions.json")
            arguments = ["native-expiry", os.environ["KAVITA_SERVICES_ASSEMBLY"], str(provider), "opaque-personal-token"] if native else ["expiry", "3", "opaque-personal-token"]
            result = subprocess.run(["dotnet", str(self.root / "bin/Debug/net10.0/Probe.dll"), *arguments],
                                    env=env, check=True, capture_output=True, text=True, timeout=20)
            return json.loads(result.stdout.strip()), observed
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_actual_gateway_expiry_for_opaque_tokens_and_unknown_pat(self):
        result, observed = self.expiry_probe({"isSuccess": True, "data": "2030-01-02T03:04:05Z"})
        self.assertEqual(result, "2030-01-02T03:04:05Z")
        self.assertEqual(observed[0]["path"], "/api/v3/oauth/token-expiration")
        self.assertEqual(observed[0]["body"], {"upstream": 3, "accessToken": "opaque-personal-token"})
        self.assertEqual(observed[0]["headers"]["X-Provider-Key"], self.key)
        unknown, _ = self.expiry_probe({"isSuccess": False, "errorMessage": "Expiry unknown"}, status=501)
        self.assertIsNone(unknown)
        invalid, _ = self.expiry_probe({"isSuccess": True, "data": "0001-01-01T00:00:00"})
        self.assertIsNone(invalid)

    @unittest.skipUnless(os.environ.get("KAVITA_SERVICES_ASSEMBLY"), "set KAVITA_SERVICES_ASSEMBLY to compiled native service")
    def test_native_get_expiry_uses_registry_for_opaque_mal_and_anilist_tokens(self):
        for provider, upstream in [(1, 2), (2, 3), (5, 4), (6, 1)]:
            with self.subTest(provider=provider):
                result, observed = self.expiry_probe({"isSuccess": True, "data": "2030-01-02T03:04:05Z"}, native=True, provider=provider)
                self.assertEqual(result, "2030-01-02T03:04:05Z")
                self.assertEqual(observed[0]["body"]["upstream"], upstream)
        result, _ = self.expiry_probe({"isSuccess": False, "errorMessage": "Expiry unknown"}, status=501, native=True)
        self.assertIsNone(result)

    def oauth_probe(self, arguments, public_url="https://reader.example/base"):
        env = os.environ.copy()
        env["KAVITA_PUBLIC_URL"] = public_url
        return subprocess.run(["dotnet", str(self.root / "bin/Debug/net10.0/Probe.dll"), *arguments],
                              env=env, check=True, capture_output=True, text=True, timeout=20).stdout.strip()

    def test_oauth_callback_uses_fixed_configured_url_and_base_path(self):
        self.assertEqual(self.oauth_probe(["canonical"]), "https://reader.example/base/api/oauth/independent-callback\n/base/settings?loading=true#scrobble-settings")
        for url in ["http://reader.example", "https://user:password@reader.example", "https://reader.example/?redirect=bad", "https://reader.example/#fragment"]:
            with self.subTest(url=url):
                self.assertEqual(self.oauth_probe(["canonical"], url), "invalid")

    def test_oauth_redirect_allowlist_and_state_binding(self):
        state = "s" * 64
        valid = [(1, "https://mangabaka.org/auth/oauth2/authorize"), (2, "https://anilist.co/api/v2/oauth/authorize"),
                 (3, "https://myanimelist.net/v1/oauth2/authorize"), (4, "https://hardcover.app/oauth2/authorize")]
        for upstream, url in valid:
            with self.subTest(upstream=upstream):
                self.assertEqual(self.oauth_probe(["authorize", str(upstream), url + "?state=" + state, state]), "True")
        for url in ["https://attacker.example/authorize?state=" + state,
                    "https://anilist.co.attacker.example/api/v2/oauth/authorize?state=" + state,
                    "https://anilist.co/api/v2/oauth/authorize?state=wrong",
                    "https://anilist.co/api/v2/oauth/authorize?state=" + state + "&state=" + state,
                    "https://anilist.co/api/v2/oauth/authorize?state=" + state + "#fragment"]:
            self.assertEqual(self.oauth_probe(["authorize", "2", url, state]), "False")

    def test_official_mode_does_not_request_gateway(self):
        result, available, observed = self.probe()
        self.assertEqual(result["mode"], "official")
        self.assertEqual(available, "False")
        self.assertEqual(observed, [])

    def test_authenticated_capability_and_no_license_header(self):
        result, available, observed = self.probe({"protocolVersion": 1, "mode": "independent", "providers": [
            {"name": "fixture", "available": True, "capabilities": ["metadata"]}], "limitations": ["Sync unavailable"]})
        self.assertEqual(available, "True")
        self.assertEqual(len(observed), 1)  # cached by the Has call
        self.assertEqual(observed[0]["X-Provider-Key"], self.key)
        self.assertFalse(any("license" in name.lower() for name in observed[0]))
        self.assertEqual(result["limitations"], ["Sync unavailable"])

    def test_incompatible_manifest_disables_capabilities(self):
        result, available, _ = self.probe({"protocolVersion": 2, "mode": "independent", "providers": [], "limitations": []})
        self.assertEqual(available, "False")
        self.assertTrue(result["limitations"])

    def test_denied_manifest_disables_capabilities(self):
        result, available, _ = self.probe({}, status=401)
        self.assertEqual(available, "False")
        self.assertTrue(result["limitations"])

    def test_cold_process_recovers_authenticated_snapshot_only_for_creation(self):
        manifest = {"protocolVersion": 1, "mode": "independent", "limitations": [], "providers": [
            {"name": "AniList", "available": True, "capabilities": ["scrobbling"],
             "adapters": {"sync": {"available": True, "capabilities": ["ratings"]}}}]}
        class Handler(http.server.BaseHTTPRequestHandler):
            status = 200
            value = manifest
            def do_GET(self):
                self.send_response(self.status)
                self.end_headers()
                self.wfile.write(json.dumps(self.value).encode())
            def log_message(self, *args):
                pass
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "actions.json"
            key = Path(directory) / "key"
            key.write_text(self.key)
            env = {**os.environ, "KAVITA_PROVIDER_URL": f"http://127.0.0.1:{server.server_port}",
                   "KAVITA_PROVIDER_KEY_FILE": str(key), "KAVITA_PROVIDER_ACTIONS_FILE": str(snapshot)}
            def fresh(**override):
                return subprocess.run(["dotnet", str(self.root / "bin/Debug/net10.0/Probe.dll"), "creation"],
                                      env={**env, **override}, capture_output=True, text=True, check=True, timeout=20).stdout.strip()
            try:
                self.assertEqual(fresh(), "True:True:True")
                saved = snapshot.read_bytes()
                self.assertEqual(snapshot.stat().st_mode & 0o777, 0o600)
                self.assertNotIn(self.key.encode(), saved)
                Handler.status = 503
                self.assertEqual(fresh(), "True:True:False")
                key.write_text("rotated-fixture-key-" + "r" * 32)
                self.assertEqual(fresh(), "False:False:False")
                key.write_text(self.key)
                self.assertEqual(fresh(KAVITA_PROVIDER_URL="http://127.0.0.1:1"), "False:False:False")
                snapshot.write_text('{"payload":"corrupt","signature":"00"}')
                self.assertEqual(fresh(), "False:False:False")
                snapshot.write_bytes(b"x" * 524289)
                self.assertEqual(fresh(), "False:False:False")
                snapshot.write_bytes(saved)
                Handler.status = 200
                Handler.value = {**manifest, "providers": []}
                self.assertEqual(fresh(), "False:False:False")
                Handler.status = 503
                self.assertEqual(fresh(), "False:False:False")
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == "__main__":
    unittest.main()
