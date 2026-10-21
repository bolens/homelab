"""Optional ErsatzTV recovery, recipes and read-only guide correctness checks."""

from contextlib import closing
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


DEFINITION_TABLES = (
    "Channel", "FFmpegProfile", "ProgramSchedule", "ProgramScheduleItem",
    "ProgramScheduleOneItem", "ProgramScheduleMultipleItem", "ProgramScheduleDurationItem",
    "ProgramScheduleFloodItem", "ProgramScheduleAlternate", "SmartCollection",
    "Collection", "CollectionItem", "FillerPreset", "ChannelWatermark",
)
REBUILDABLE = {"logs", "next", "search-index", "ffmpeg-reports", "temp-pool"}


def stamp(value):
    return int(dt.datetime.strptime(value, "%Y%m%d%H%M%S %z").timestamp())


def programme_key(start, end, title, subtitle):
    return (int(start), int(end), title or "", subtitle or "")


def xml_programmes(raw):
    root = ET.fromstring(raw)
    channels = {c.get("id"): c.findtext("display-name", "") for c in root.findall("channel")}
    programmes = {}
    for row in root.findall("programme"):
        programmes.setdefault(row.get("channel"), []).append(programme_key(
            stamp(row.get("start")), stamp(row.get("stop")), row.findtext("title"),
            row.findtext("sub-title")))
    return channels, {key: sorted(rows) for key, rows in programmes.items()}


def compare_guides(bindings, native, dispatch, plex, start, end):
    """Compare complete overlapping airings, preserving duplicate detection."""
    failures = {"missing_channels": 0, "gaps": 0, "overlaps": 0, "differences": 0}
    for binding in bindings:
        key = binding["guide_id"]
        expected = [r for r in native.get(key, []) if r[1] > start and r[0] < end]
        if not expected or expected[0][0] > start or expected[-1][1] < end:
            failures["missing_channels"] += 1
        for previous, current in zip(expected, expected[1:]):
            failures["gaps"] += int(previous[1] < current[0])
            failures["overlaps"] += int(previous[1] > current[0])
        for actual in (dispatch.get(key, []), plex.get(str(binding["output_number"]), [])):
            actual = sorted(r for r in actual if r[1] > start and r[0] < end)
            if sorted(expected) != actual:
                failures["differences"] += 1
    return failures


def definitions(database):
    result = {}
    for table in DEFINITION_TABLES:
        result[table] = sorted((dict(r) for r in database.execute('SELECT * FROM "' + table + '"')),
                               key=lambda row: json.dumps(row, sort_keys=True))
    result["ChannelArtwork"] = [dict(r) for r in database.execute(
        "SELECT Id,ChannelId,Path,SourcePath,ArtworkKind FROM Artwork "
        "WHERE ChannelId IS NOT NULL ORDER BY Id")]
    result["Playout"] = [dict(r) for r in database.execute(
        "SELECT Id,ChannelId,ProgramScheduleId,DailyRebuildTime,ScheduleKind,ScheduleFile "
        "FROM Playout ORDER BY Id")]
    result["ConfigElement"] = [dict(r) for r in database.execute(
        "SELECT Key,Value FROM ConfigElement WHERE Key IN "
        "('playout.days_to_build','xmltv.days_to_build','ffmpeg.extract_embedded_subtitles') ORDER BY Key")]
    return result


def definition_drift(expected, actual):
    return sum(expected.get(key) != actual.get(key) for key in set(expected) | set(actual))


def derived_plan(recipe, actual):
    smart = {r["Id"]: r for r in actual["SmartCollection"]}
    baseline = {r["Id"]: r for r in recipe["definitions"]["SmartCollection"]}
    result = []
    for rule in recipe.get("derived", []):
        source, target = smart[rule["source_id"]], smart[rule["target_id"]]
        for row in (source, target):
            if {k: v for k, v in row.items() if k != "Query"} != {
                    k: v for k, v in baseline[row["Id"]].items() if k != "Query"}:
                raise RuntimeError("Derived filter has unreviewed non-query drift")
        if target["Query"] != baseline[target["Id"]]["Query"]:
            raise RuntimeError("Derived filter has an unreviewed independent edit")
        query = "(" + source["Query"] + ") AND type:movie AND library_id:" + str(rule["library_id"])
        if target["Query"] != query:
            result.append({"id": target["Id"], "name": target["Name"],
                           "previous": target["Query"], "query": query})
    return result


def asset_manifest(root):
    result = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if relative.parts[0] in REBUILDABLE or str(relative).startswith("cache/channel-guide/"):
            continue
        if relative.name in {"ersatztv.sqlite3", "ersatztv.sqlite3-wal", "ersatztv.sqlite3-shm"}:
            continue
        if path.is_symlink():
            raise RuntimeError("Preserved configuration contains an unsupported symlink")
        if path.is_file():
            result[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def online_backup(root, destination):
    """Consistent SQL plus stable assets; retained backup SQL is never opened."""
    destination.mkdir(mode=0o700)
    before = asset_manifest(root)
    database = destination / "ersatztv.sqlite3"
    with closing(sqlite3.connect("file:" + str(root / "ersatztv.sqlite3") + "?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(database)) as target:
            source.backup(target)
            counts = {table: target.execute('SELECT COUNT(*) FROM "' + table + '"').fetchone()[0]
                      for table in ["Channel", "SmartCollection", "CollectionItem", "MediaItem", "PlayoutItem"]}
    for relative in before:
        target = destination / relative
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copy2(root / relative, target)
    if before != asset_manifest(root) or before != asset_manifest(destination):
        raise RuntimeError("Configuration assets changed during backup")
    digest = hashlib.sha256(database.read_bytes()).hexdigest()
    # WAL-mode read-only connections may create sidecars. Query only a disposable copy.
    with tempfile.TemporaryDirectory(prefix=".etv-restore-", dir=destination.parent) as scratch:
        restore = Path(scratch) / "config"
        shutil.copytree(destination, restore)
        with closing(sqlite3.connect(restore / "ersatztv.sqlite3")) as check:
            if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or check.execute(
                    "PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("ErsatzTV isolated SQL restore failed")
            for table, count in counts.items():
                if check.execute('SELECT COUNT(*) FROM "' + table + '"').fetchone()[0] != count:
                    raise RuntimeError("ErsatzTV restored records differ")
        if asset_manifest(restore) != before:
            raise RuntimeError("ErsatzTV asset restore differs")
    if hashlib.sha256(database.read_bytes()).hexdigest() != digest:
        raise RuntimeError("Retained ErsatzTV database changed during verification")
    if {x.name for x in destination.glob("ersatztv.sqlite3*")} != {"ersatztv.sqlite3"}:
        raise RuntimeError("Unexpected sidecar beside retained ErsatzTV backup")
    return {"verified": True, "counts": counts, "assets": len(before), "sqlite_sha256": digest,
            "rebuildable_excluded": sorted(REBUILDABLE | {"cache/channel-guide"})}


class ErsatzTV:
    def __init__(self, owner):
        self.owner = owner
        self.config = owner.config["ersatztv"]
        self.root = Path(self.config["config_root"])
        self.recipe_path = Path(self.config["recipe_file"])
        meta = owner.inspect(self.config.get("container", "ersatztv"))
        mounts = [m for m in meta["Mounts"] if m["Destination"] == "/config"]
        if len(mounts) != 1 or Path(mounts[0]["Source"]).resolve() != self.root.resolve():
            raise RuntimeError("ErsatzTV configuration mount binding differs")
        self.meta = meta
        address = meta["NetworkSettings"]["Networks"][self.config["network"]]["IPAddress"]
        self.origin = "http://" + address + ":8409"

    def database(self):
        database = sqlite3.connect("file:" + str(self.root / "ersatztv.sqlite3") + "?mode=ro", uri=True)
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA query_only=ON")
        return database

    def request(self, path, body=None):
        headers = {}
        if path.startswith("/api/"):
            headers["X-Etv-Api-Key"] = json.loads((self.root / "api-secrets.json").read_text())["ApiKey"]
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.origin + path, headers=headers,
                                         data=json.dumps(body).encode() if body is not None else None,
                                         method="PUT" if body is not None else "GET")
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.read()

    def backup(self, destination):
        self.owner.require_ersatztv_mount(self.root)
        result = online_backup(self.root, destination)
        result["image"] = self.meta["Image"]
        return result

    def export(self):
        with closing(self.database()) as database:
            result = {"schema": 1, "definitions": definitions(database), "bindings": [],
                      "restrictions": self.config.get("restrictions", []),
                      "derived": self.config.get("derived", [])}
            enabled = list(database.execute("SELECT Id,Number,Name FROM Channel WHERE IsEnabled=1"))
        names, _ = xml_programmes(self.request("/iptv/xmltv.xml"))
        data = self.owner.django("library_guide", {"account_id": self.config["account_id"],
                                "source_id": self.config["source_id"], "hours": 2})
        for channel in enabled:
            guide_id = next(key for key, name in names.items()
                            if name == channel["Number"] + " " + channel["Name"])
            bindings = [row for row in data["bindings"] if row["guide_id"] == guide_id]
            if len(bindings) != 1:
                raise RuntimeError("Native/Dispatcharr station mapping is not unique")
            result["bindings"].append({"channel_id": channel["Id"], "name": channel["Name"],
                                        "native_number": channel["Number"], **bindings[0]})
        return result

    def recipe(self):
        if self.recipe_path.stat().st_mode & 0o077:
            raise RuntimeError("Recipe file must be private")
        result = json.loads(self.recipe_path.read_text())
        if result.get("schema") != 1 or not result.get("bindings"):
            raise RuntimeError("Unsupported or empty channel recipe")
        for field in ["channel_id", "guide_id", "output_number", "uuid"]:
            if len({row[field] for row in result["bindings"]}) != len(result["bindings"]):
                raise RuntimeError("Duplicate recipe station identity")
        for restriction in result.get("restrictions", []):
            if not restriction.get("episodes_only") and not restriction.get("show_ids"):
                raise RuntimeError("Personal station restriction has no allowed shows")
        return result

    def check(self):
        recipe = self.recipe()
        with closing(self.database()) as database:
            actual = definitions(database)
            violations = 0
            for restriction in recipe.get("restrictions", []):
                allowed = set(restriction.get("show_ids", []))
                movies = set(restriction.get("movie_ids", []))
                if restriction.get("quiet"):
                    channel = database.execute("SELECT WatermarkId FROM Channel WHERE Id=?",
                                               (restriction["channel_id"],)).fetchone()
                    if channel is None or channel[0] is not None:
                        violations += 1
                    violations += database.execute(
                        "SELECT COUNT(*) FROM PlayoutItem WHERE PlayoutId=? AND FillerKind!=0",
                        (restriction["playout_id"],)).fetchone()[0]
                rows = database.execute(
                    "SELECT p.MediaItemId,s.ShowId FROM PlayoutItem p "
                    "LEFT JOIN Episode e ON e.Id=p.MediaItemId "
                    "LEFT JOIN Season s ON s.Id=e.SeasonId "
                    "WHERE p.PlayoutId=? AND p.FillerKind=0", (restriction["playout_id"],))
                for row in rows:
                    if (allowed and row["ShowId"] not in allowed and row["MediaItemId"] not in movies) or (
                            restriction.get("episodes_only") and row["ShowId"] is None):
                        violations += 1
        _, native = xml_programmes(self.request("/iptv/xmltv.xml"))
        hours = self.config.get("monitor_window_hours", 2)
        data = self.owner.django("library_guide", {"account_id": self.config["account_id"],
                                "source_id": self.config["source_id"], "hours": hours})
        bindings = recipe["bindings"]
        mapping_ok = sorted(data["bindings"], key=lambda r: r["uuid"]) == sorted(
            [{k: row[k] for k in ["uuid", "output_number", "guide_id"]} for row in bindings],
            key=lambda r: r["uuid"])
        start = int(time.time()) + 120
        end = start + hours * 3600
        dispatch = {}
        for row in data["programmes"]:
            dispatch.setdefault(row[0], []).append(programme_key(*row[1:]))
        provider = next((row for row in self.owner.plex_call("/livetv/dvrs").findall("Dvr")
                         if row.get("key") == str(self.config.get("dvr_id", "1"))), None)
        if provider is None:
            raise RuntimeError("Plex DVR is missing")
        provider = provider.get("epgIdentifier")
        # The comparison operator is part of the key; urlencode supplies "=".
        grid = self.owner.plex_call("/" + provider + "/grid", params={
            "type": "1,4", "sort": "beginsAt", "endsAt>": start, "beginsAt<": end,
            "X-Plex-Container-Start": 0, "X-Plex-Container-Size": 20000})
        if int(grid.get("totalSize", str(len(grid)))) > len(grid):
            raise RuntimeError("Plex programme response is truncated")
        plex = {}
        numbers = {str(row["output_number"]) for row in bindings}
        for video in grid:
            for media in video.findall("Media"):
                number = media.get("channelVcn")
                if number in numbers:
                    episode = video.get("type") == "episode"
                    plex.setdefault(number, []).append(programme_key(
                        media.get("beginsAt"), media.get("endsAt"),
                        video.get("grandparentTitle") if episode else video.get("title"),
                        video.get("title") if episode else ""))
        differences = compare_guides(bindings, native, dispatch, plex, start, end)
        horizons = [(max((row[1] for row in native.get(b["guide_id"], [])), default=start) - start) / 3600
                    for b in bindings]
        result = {"enabled": 1, "check_success": 1, "channels_checked": len(bindings),
                  "guide_correct": int(mapping_ok and not any(differences.values())),
                  "restrictions_healthy": int(violations == 0),
                  "recipe_drift": definition_drift(recipe["definitions"], actual),
                  "guide_hours_min": min(horizons), **differences}
        return result

    def reconcile(self, apply=False):
        recipe = self.recipe()
        with closing(self.database()) as database:
            actual = definitions(database)
        changes = derived_plan(recipe, actual)
        if not apply or not changes:
            return {"apply": apply, "changes": changes}
        # Any viewing or scheduled recording refuses the operation conservatively.
        if len(self.owner.plex_call("/status/sessions")) or len(self.owner.plex_call(
                "/media/subscriptions/scheduled")):
            raise RuntimeError("Viewing or scheduled recordings prevent reconciliation")
        activity = self.owner.django("library_guide", {"account_id": self.config["account_id"],
                                    "source_id": self.config["source_id"], "hours": 168})
        if activity["recordings"]:
            raise RuntimeError("Dispatcharr recordings prevent reconciliation")
        if json.loads(self.request("/api/sessions")):
            raise RuntimeError("Native playback prevents reconciliation")
        from runner import command
        processes = command(["docker", "top", self.config.get("container", "ersatztv"),
                             "-eo", "pid,comm"]).decode()
        if any("ersatztv-channe" in line.lower() or "ffmpeg" in line.lower()
               for line in processes.splitlines()[1:]):
            raise RuntimeError("Native playback prevents reconciliation")
        scratch = Path(tempfile.mkdtemp(prefix=".recipe-recovery-", dir=self.owner.state))
        self.backup(scratch / "config")
        try:
            applied = []
            try:
                for change in changes:
                    self.request("/api/collections/smart/update", {
                        "id": change["id"], "name": change["name"], "query": change["query"]})
                    applied.append(change)
            except Exception:
                for change in reversed(applied):
                    self.request("/api/collections/smart/update", {
                        "id": change["id"], "name": change["name"], "query": change["previous"]})
                raise
            with closing(self.database()) as database:
                updated = definitions(database)
            for change in changes:
                if not any(r["Id"] == change["id"] and r["Query"] == change["query"]
                           for r in updated["SmartCollection"]):
                    raise RuntimeError("Reconciled query did not persist")
        except BaseException:
            # Keep the verified recovery packet on all uncertain/failure paths.
            raise
        # Only explicitly derived filters and their source queries are accepted.
        for rule in recipe.get("derived", []):
            for ident in [rule["source_id"], rule["target_id"]]:
                row = next(r for r in updated["SmartCollection"] if r["Id"] == ident)
                old = next(r for r in recipe["definitions"]["SmartCollection"] if r["Id"] == ident)
                old["Query"] = row["Query"]
        from runner import atomic_json
        atomic_json(self.recipe_path, recipe)
        shutil.rmtree(scratch)
        return {"apply": True, "updated_filters": len(changes)}
