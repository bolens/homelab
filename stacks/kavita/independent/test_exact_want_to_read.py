"""Compile and exercise exact provider matching against pinned native models."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent


@unittest.skipUnless(os.environ.get("KAVITA_MODEL_ASSEMBLY") and shutil.which("dotnet"),
                     "set KAVITA_MODEL_ASSEMBLY to compiled pinned Kavita.Models.dll")
class ExactWantToReadTests(unittest.TestCase):
    def test_exact_identity_without_names_cross_provider_or_prefix_fallback(self):
        with tempfile.TemporaryDirectory(prefix="kavita-exact-import-") as raw:
            root = Path(raw)
            shutil.copyfile(HERE / "IndependentWantToReadMatcher.cs", root / "IndependentWantToReadMatcher.cs")
            project = ET.Element("Project", Sdk="Microsoft.NET.Sdk")
            properties = ET.SubElement(project, "PropertyGroup")
            ET.SubElement(properties, "OutputType").text = "Exe"
            ET.SubElement(properties, "TargetFramework").text = "net10.0"
            references = ET.SubElement(project, "ItemGroup")
            reference = ET.SubElement(references, "Reference", Include="Kavita.Models")
            ET.SubElement(reference, "HintPath").text = str(Path(os.environ["KAVITA_MODEL_ASSEMBLY"]).resolve())
            ET.ElementTree(project).write(root / "Probe.csproj")
            (root / "Program.cs").write_text('''using System;
using Kavita.Services.Plus;
using Kavita.Models.DTOs.KavitaPlus.Metadata;
using Kavita.Models.Entities;
using Kavita.Models.Entities.Metadata;
using Kavita.Models.Entities.Enums;
var checks = 0;
void Check(bool condition, string reason) { if (!condition) throw new Exception(reason); checks++; }
Series Local(int id, int ani = 0, long mal = 0, int hc = 0, int mb = 0, bool book = false, string links = "") =>
    new Series { Id = id, Name = "Identical title", NormalizedName = "identicaltitle", NormalizedLocalizedName = "", SortName = "Identical title", LocalizedName = "", OriginalName = "Identical title", AniListId = ani, MalId = mal, HardcoverId = hc,
        MangaBakaId = mb, IsStandAlone = book, Metadata = new SeriesMetadata { WebLinks = links } };
var ani = new ExternalSeriesDetailDto { Name = "Identical title", Provider = ScrobbleProvider.AniList, AniListId = 123, MALId = 999 };
Check(IndependentWantToReadMatcher.Resolve(ani, new[] { Local(1, ani: 123) }) == 1, "exact AniList ID");
Check(IndependentWantToReadMatcher.Resolve(ani, new[] { Local(1) }) == null, "title-only match refused");
Check(IndependentWantToReadMatcher.Resolve(ani, new[] { Local(1, mal: 999) }) == null, "cross-provider fallback refused");
Check(IndependentWantToReadMatcher.Resolve(ani with { AniListId = null }, new[] { Local(1, mal: 999) }) == null, "missing authoritative ID refused");
Check(IndependentWantToReadMatcher.Resolve(ani, new[] { Local(1, ani: 123), Local(2, ani: 123) }) == null, "ambiguous duplicates refused");
Check(IndependentWantToReadMatcher.Resolve(ani, new[] { Local(1, links: "https://anilist.co/manga/123/") }) == 1, "exact canonical link");
Check(IndependentWantToReadMatcher.Resolve(ani, new[] { Local(1, links: "https://anilist.co/manga/1234/") }) == null, "numeric prefix refused");
Check(IndependentWantToReadMatcher.Resolve(ani, new[] { Local(1, links: "https://anilist.co.attacker.example/manga/123") }) == null, "spoofed origin refused");
Check(IndependentWantToReadMatcher.Resolve(ani, new[] { Local(1, links: "https://anilist.co/manga/123,https://anilist.co/manga/124") }) == null, "conflicting links refused");
Check(IndependentWantToReadMatcher.Resolve(ani, new[] { Local(1, ani: 123, links: "https://anilist.co/manga/124") }) == null, "stored ID/link conflict refused");
var mal = new ExternalSeriesDetailDto { Provider = ScrobbleProvider.Mal, MALId = 123 };
Check(IndependentWantToReadMatcher.Resolve(mal, new[] { Local(1, links: "https://myanimelist.net/manga/123/example-title") }) == 1, "MAL exact ID with title slug");
Check(IndependentWantToReadMatcher.Resolve(mal, new[] { Local(1, links: "https://myanimelist.net/anime/123/example-title") }) == null, "wrong media type refused");
var mb = new ExternalSeriesDetailDto { Provider = ScrobbleProvider.MangaBaka, MangabakaId = 123, AniListId = 999 };
Check(IndependentWantToReadMatcher.Resolve(mb, new[] { Local(1, mb: 123) }) == 1, "exact MangaBaka ID");
Check(IndependentWantToReadMatcher.Resolve(mb, new[] { Local(1, ani: 999) }) == null, "MangaBaka cross-ID refused");
var hc = new ExternalSeriesDetailDto { Provider = ScrobbleProvider.Hardcover, HardcoverId = 50, IsStandAlone = true };
Check(IndependentWantToReadMatcher.Resolve(hc, new[] { Local(1, hc: 50, book: true) }) == 1, "Hardcover standalone book identity");
Check(IndependentWantToReadMatcher.Resolve(hc, new[] { Local(1, hc: 50, book: false) }) == null, "Hardcover book/series collision refused");
Check(IndependentWantToReadMatcher.Resolve(hc, Array.Empty<Series>(), new[] { 7, 7 }) == 7, "book chapter maps to one parent series");
Check(IndependentWantToReadMatcher.Resolve(hc, new[] { Local(1, hc: 50, book: true) }, new[] { 7 }) == null, "ambiguous book containers refused");
Check(IndependentWantToReadMatcher.Resolve(hc with { IsStandAlone = false }, Array.Empty<Series>(), new[] { 7 }) == null, "chapter books never become provider series IDs");
Console.WriteLine($"{checks} exact identity checks passed");
''')
            build = subprocess.run(["dotnet", "build", "-v", "quiet"], cwd=root, capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            probe = subprocess.run(["dotnet", str(root / "bin/Debug/net10.0/Probe.dll")], capture_output=True, text=True, timeout=20)
            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertIn("19 exact identity checks passed", probe.stdout)


if __name__ == "__main__":
    unittest.main()
