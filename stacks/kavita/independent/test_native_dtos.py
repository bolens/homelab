"""Deserialize adapter fixtures with the pinned native Kavita model assembly."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


@unittest.skipUnless(os.environ.get("KAVITA_MODEL_ASSEMBLY") and shutil.which("dotnet"),
                     "set KAVITA_MODEL_ASSEMBLY to the compiled pinned Kavita.Models.dll")
class NativeDtoTests(unittest.TestCase):
    def test_metadata_payloads_deserialize_in_pinned_application(self):
        providers = Path(__file__).resolve().parents[1] / "providers"
        sys.path.insert(0, str(providers))
        try:
            from metadata import Metadata
            from test_metadata import BOOK, MANGA, REVIEW, SERIES, FixtureTransport
            transport = FixtureTransport()
            adapter = Metadata(transport)
            payloads = []
            transport.responses = [{"status": 200, "data": MANGA},
                                   {"Page": {"reviews": [REVIEW], "pageInfo": {"hasNextPage": False}}},
                                   {"status": 200, "data": []}]
            payloads.append(adapter.dispatch("/api/v3/metadata/series-detail", {
                "provider": 3, "mangabakaId": 1, "includeRelationships": False,
                "includeRecommendations": False}, {}))
            for standalone, row in ((True, BOOK), (False, SERIES)):
                transport.responses = [{"books_by_pk" if standalone else "series_by_pk": row}]
                payloads.append(adapter.dispatch("/api/v3/metadata/series-detail", {
                    "provider": 2, "hardcoverId": 10, "isStandAlone": standalone,
                    "includeRecommendations": False}, {}))
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory(prefix="kavita-native-dto-") as raw:
            root = Path(raw)
            project = ET.Element("Project", Sdk="Microsoft.NET.Sdk")
            properties = ET.SubElement(project, "PropertyGroup")
            ET.SubElement(properties, "OutputType").text = "Exe"
            ET.SubElement(properties, "TargetFramework").text = "net10.0"
            references = ET.SubElement(project, "ItemGroup")
            reference = ET.SubElement(references, "Reference", Include="Kavita.Models")
            ET.SubElement(reference, "HintPath").text = str(Path(os.environ["KAVITA_MODEL_ASSEMBLY"]).resolve())
            ET.ElementTree(project).write(root / "Probe.csproj")
            (root / "Program.cs").write_text('''using System;
using System.Text.Json;
using Kavita.Models.DTOs.KavitaPlus.ExternalMetadata;
var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
var items = JsonSerializer.Deserialize<JsonElement[]>(Console.In.ReadToEnd());
foreach (var item in items!) {
    var dto = item.Deserialize<SeriesDetailPlusApiDto>(options);
    if (dto?.Series == null || string.IsNullOrEmpty(dto.Series.Name)) throw new Exception("Missing native series");
}
Console.WriteLine("Native metadata DTOs accepted");
''')
            build = subprocess.run(["dotnet", "build", "-v", "quiet"], cwd=root,
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            probe = subprocess.run(["dotnet", str(root / "bin/Debug/net10.0/Probe.dll")],
                                   input=json.dumps(payloads), capture_output=True, text=True, timeout=20)
            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertIn("Native metadata DTOs accepted", probe.stdout)


if __name__ == "__main__":
    unittest.main()
