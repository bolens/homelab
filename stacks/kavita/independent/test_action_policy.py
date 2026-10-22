"""Run the shipped C# and TypeScript action policies, without provider traffic."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


@unittest.skipUnless(shutil.which("dotnet") and shutil.which("node"), "requires .NET 10 and Node 24")
class ActionPolicyTests(unittest.TestCase):
    def test_compiled_policies_reject_cross_provider_and_catalog_capabilities(self):
        providers = []
        for name, caps in [("AniList", ["progress", "ratings", "reviews", "wantToRead", "safeWantToReadRemoval", "readingStatus"]),
                           ("MyAnimeList", ["progress", "ratings", "wantToRead", "safeWantToReadRemoval", "readingStatus"]),
                           ("Hardcover", ["progressWithExistingEdition", "ratings", "reviews", "friendsOnlyReviews", "wantToRead", "safeWantToReadRemoval", "readingStatus"]),
                           ("MangaBaka", ["progress", "ratings", "wantToRead", "safeWantToReadRemoval", "readingStatus"])]:
            providers.append({"name": name, "available": True, "capabilities": ["reviews"],
                              "adapters": {"sync": {"available": True, "capabilities": caps}}})
        cases = []
        expected = []
        for provider in (1, 2, 5, 6):
            for event in range(7):
                cases.append({"manifest": {"mode": "independent", "providers": providers}, "provider": provider, "event": event})
                expected.append(event < 6 and not (event == 4 and provider in (2, 6)))
        for entries in ([{"name": "AniList", "available": True, "capabilities": ["reviews"]}],
                        [providers[0], providers[0]], []):
            cases.append({"manifest": {"mode": "independent", "providers": entries}, "provider": 1, "event": 4})
            expected.append(False)
        disabled = copy.deepcopy(providers[0])
        disabled["available"] = False
        malformed = copy.deepcopy(providers[0])
        malformed["adapters"]["sync"]["capabilities"] = ["reviews", 42]
        for entry in (disabled, malformed):
            cases.append({"manifest": {"mode": "independent", "providers": [entry]}, "provider": 1, "event": 4})
            expected.append(False)
        with tempfile.TemporaryDirectory(prefix="kavita-action-policy-") as directory:
            root = Path(directory)
            shutil.copyfile(HERE / "IndependentScrobblePolicy.cs", root / "IndependentScrobblePolicy.cs")
            (root / "Probe.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>')
            (root / "Program.cs").write_text('''using System; using System.Text.Json; using System.Linq; using Kavita.Common;
var cases = JsonDocument.Parse(Console.In.ReadToEnd()).RootElement;
var result = cases.EnumerateArray().Select(c => IndependentScrobblePolicy.Allows(c.GetProperty("manifest"), c.GetProperty("provider").GetInt32(), c.GetProperty("event").GetInt32())).ToArray();
var m = cases[0].GetProperty("manifest");
if (IndependentScrobblePolicy.AllowsPayload(m,1,0,2,null,null) || IndependentScrobblePolicy.AllowsPayload(m,1,5,0,3,null) || IndependentScrobblePolicy.AllowsPayload(m,1,4,0,null,1) || !IndependentScrobblePolicy.AllowsPayload(m,5,4,0,null,1)) throw new Exception("Reread/reset/visibility admission failed");
Console.WriteLine(JsonSerializer.Serialize(result));
''')
            build = subprocess.run(["dotnet", "build", "-v", "quiet"], cwd=root, capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            result = subprocess.run(["dotnet", str(root / "bin/Debug/net10.0/Probe.dll")],
                                    input=json.dumps(cases), capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout), expected)
            script = '''import fs from 'node:fs';
import {personalSyncActions,supportsSyncAction} from INPUT;
const cases=JSON.parse(fs.readFileSync(0,'utf8'));
console.log(JSON.stringify(cases.map(c=>supportsSyncAction(personalSyncActions(c.manifest.providers),c.provider,c.event))));'''.replace("INPUT", json.dumps((HERE / "independent-actions.ts").as_uri()))
            result = subprocess.run(["node", "--input-type=module", "-e", script],
                                    input=json.dumps(cases), capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout), expected)
