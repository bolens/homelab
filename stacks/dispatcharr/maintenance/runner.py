#!/usr/bin/env python3
"""Opt-in host maintenance. Requires private configuration and scoped Docker access."""

import argparse
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from policy import decide, source_unhealthy


def command(args, timeout=120):
    result = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    if result.returncode:
        # Child stderr can contain provider URLs or database connection details.
        raise RuntimeError("Child command failed: " + Path(args[0]).name)
    return result.stdout


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as output:
        json.dump(value, output, sort_keys=True)
        output.flush()
        os.fsync(output.fileno())
    temporary.chmod(0o600)
    os.replace(temporary, path)


def require_mount(path, expected):
    actual = command(["findmnt", "-T", str(path), "-n", "-o", "FSTYPE,SOURCE"]).decode()
    rows = [line.split(maxsplit=1) for line in actual.splitlines() if line.strip()]
    if not rows or rows[-1] != [expected["fstype"], expected["source"]]:
        raise RuntimeError("Expected mounted filesystem is unavailable")


class Maintenance:
    def __init__(self, config):
        self.config = config
        if not isinstance(config.get("quarantine_enabled", True), bool):
            raise ValueError("quarantine_enabled must be a JSON boolean")
        self.state = Path(config["state_directory"])
        self.state.mkdir(mode=0o700, parents=False, exist_ok=True)
        self.container = config.get("container", "dispatcharr")
        self.plex = config.get("plex_container", "plex")
        self.adapter = Path(__file__).with_name("django_adapter.py").read_text()
        if config.get("quarantine_days", 14) < 14 or config.get("minimum_failed_days", 3) < 3:
            raise ValueError("Quarantine requires at least fourteen days and three failed days")
        if config.get("backup_generations", 7) < 1:
            raise ValueError("Keep at least one verified backup generation")

    def django(self, mode, extra=None):
        payload = {"mode": mode, "protected_profiles": self.config["protected_profiles"]}
        payload.update(extra or {})
        output = command([
            "docker", "exec", "-i", "-u", "1000", "-e",
            "IPTV_MAINTENANCE_INPUT=" + json.dumps(payload), self.container,
            "python", "manage.py", "shell", "-c", self.adapter,
        ], timeout=300).decode()
        line = next(line for line in reversed(output.splitlines())
                    if line.startswith("IPTV_MAINTENANCE "))
        return json.loads(line.removeprefix("IPTV_MAINTENANCE "))

    def inspect(self, name):
        return json.loads(command(["docker", "inspect", name]))[0]

    def require_ersatztv_mount(self, root):
        require_mount(root, self.config["ersatztv"]["config_mount"])

    def plex_call(self, path, method="GET", params=None):
        token = ET.parse(Path(self.config["plex_root"]) / "Preferences.xml").getroot().get(
            "PlexOnlineToken")
        if params:
            path += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request("http://127.0.0.1:32400" + path, method=method,
                                         headers={"X-Plex-Token": token})
        with urllib.request.urlopen(request, timeout=45) as response:
            body = response.read()
            if not body.strip() and method != "GET":
                return ET.Element("MediaContainer")
            return ET.fromstring(body)

    def recording_defaults(self):
        """Apply retention once to new series in explicitly dedicated DVR libraries."""
        path = self.state / "recording-defaults.json"
        subscriptions = list(self.plex_call("/media/subscriptions").iter("MediaSubscription"))
        if not path.exists():
            # First admission establishes existing rules without changing retention.
            atomic_json(path, {"processed": [row.get("key") for row in subscriptions
                                             if row.get("key")]})
            return
        state = json.loads(path.read_text())
        allowed = {str(value) for value in self.config.get("dvr_library_ids", [])}
        for subscription in subscriptions:
            key = subscription.get("key")
            if not key or key in state["processed"]:
                continue
            # Never impose deletion rules on a shared movie/TV library or an existing rule.
            if subscription.get("targetLibrarySectionID") in allowed and subscription.get(
                    "type") == "2":
                self.plex_call("/media/subscriptions/" + urllib.parse.quote(key, safe=""),
                               "PUT", {
                                   "prefs[autoDeletionItemPolicyUnwatchedLibrary]": "5",
                                   "prefs[autoDeletionItemPolicyWatchedLibrary]": "7",
                               })
            state["processed"].append(key)
        atomic_json(path, state)

    def quarantine(self, snapshot):
        if self.config.get("quarantine_enabled", True) is False:
            return {"paused": True}
        path = self.state / "quarantine.json"
        state = json.loads(path.read_text()) if path.exists() else {"history": {}}
        if "pending_generation" in state:
            # Finish the persisted transaction even when the checker has advanced.
            # The next invocation can then admit that newer snapshot.
            generation = state["pending_generation"]
            history, actions = state["history"], state["pending_actions"]
            deletes = {row["uuid"] for row in actions if row["kind"] == "delete"}
            if deletes:
                progress = snapshot["progress"]
                observed = progress.get("end_time")
                if progress.get("status") != "idle" or not observed or not snapshot["results"]:
                    return {"pending_first_check": True}
                # A failed DB call must not replay deletion after health or protection
                # changes. Retain pending restores while reassessing destructive actions.
                history, refreshed = decide(
                    [row for row in snapshot["channels"] if row["uuid"] in deletes],
                    snapshot["results"], history, float(observed),
                    self.config.get("quarantine_days", 14),
                    self.config.get("minimum_failed_days", 3))
                actions = [row for row in actions if row["kind"] != "delete"] + refreshed
        else:
            progress = snapshot["progress"]
            observed = progress.get("end_time")
            if progress.get("status") != "idle" or not observed or not snapshot["results"]:
                return {"pending_first_check": True}
            digest = hashlib.sha256(json.dumps(snapshot["results"], sort_keys=True).encode()).hexdigest()
            generation = str(observed) + ":" + digest
            if state.get("completed_generation") == generation:
                return {"unchanged": True}
            history, actions = decide(snapshot["channels"], snapshot["results"], state["history"],
                                      float(observed), self.config.get("quarantine_days", 14),
                                      self.config.get("minimum_failed_days", 3))
        # Write-ahead original names/groups survive a crash between file and DB commits.
        state.update({"history": history, "pending_generation": generation,
                      "pending_actions": actions})
        atomic_json(path, state)
        counts = self.django("apply", {"actions": actions})
        state["completed_generation"] = generation
        state.pop("pending_generation", None)
        state.pop("pending_actions", None)
        for action in actions:
            if action["kind"] == "delete":
                state["history"].pop(action["uuid"], None)
        atomic_json(path, state)
        return counts

    def backup(self):
        require_mount(self.state, self.config["state_mount"])
        directory = self.state / "backups"
        directory.mkdir(mode=0o700, exist_ok=True)
        name = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        staging = directory / (".staging-" + name)
        staging.mkdir(mode=0o700)
        dump = None
        try:
            native = self.django("backup")
            dump = native["dump"]
            command(["docker", "cp", self.container + ":" + dump,
                     str(staging / "dispatcharr.dump")])
            meta = self.inspect(self.container)
            data = Path(next(mount["Source"] for mount in meta["Mounts"]
                             if mount["Destination"] == "/data"))
            for item in ["plugins", "scripts", "jwt", "uploads", "logos"]:
                source = data / item
                if source.is_dir():
                    shutil.copytree(source, staging / item)
                elif source.is_file():
                    shutil.copy2(source, staging / item)
            configuration_map = {}
            for item in self.config.get("configuration_files", []) + [
                str(self.state / "quarantine.json"), str(self.state / "recording-defaults.json")
            ]:
                source = Path(item)
                if source.is_file():
                    destination = staging / "configuration" / str(len(list(
                        (staging / "configuration").glob("*")
                    )) if (staging / "configuration").exists() else 0)
                    destination.parent.mkdir(mode=0o700, exist_ok=True)
                    shutil.copy2(source, destination)
                    configuration_map[str(destination.relative_to(staging))] = str(source)
            atomic_json(staging / "configuration-map.json", configuration_map)
            plex_root = Path(self.config["plex_root"])
            plex_destination = staging / "plex"
            plex_destination.mkdir(mode=0o700)
            shutil.copy2(plex_root / "Preferences.xml", plex_destination / "Preferences.xml")
            engine = "/usr/lib/plexmediaserver/Plex SQLite"
            database_root = "/config/Library/Application Support/Plex Media Server/Plug-in Support/Databases/"
            for database in (plex_root / "Plug-in Support/Databases").glob("*.db"):
                if "-loading" in database.name:
                    continue
                temporary = "/tmp/iptv-maintenance-" + database.name
                restore = temporary + ".restore"
                try:
                    command(["docker", "exec", self.plex, engine,
                             "file:" + database_root + database.name + "?mode=ro",
                             ".backup " + temporary])
                    command(["docker", "cp", self.plex + ":" + temporary,
                             str(plex_destination / database.name)])
                    command(["docker", "exec", self.plex, "cp", temporary, restore])
                    result = command(["docker", "exec", self.plex, engine, restore,
                                      "PRAGMA integrity_check;"])
                    if result.strip() != b"ok":
                        raise RuntimeError("Plex isolated restore integrity failed")
                finally:
                    command(["docker", "exec", self.plex, "rm", "-f", temporary, restore,
                             restore + "-wal", restore + "-shm"])
            etv = None
            if self.config.get("ersatztv"):
                from ersatztv import ErsatzTV
                etv = ErsatzTV(self).backup(staging / "ersatztv")
            manifest = {}
            for item in staging.rglob("*"):
                if item.is_file():
                    item.chmod(0o600)
                    manifest[str(item.relative_to(staging))] = hashlib.sha256(
                        item.read_bytes()).hexdigest()
            # Restore file content into a separate directory and compare every digest.
            with tempfile.TemporaryDirectory(prefix=".restore-", dir=directory) as scratch:
                restored = Path(scratch) / "files"
                shutil.copytree(staging, restored)
                for item, expected in manifest.items():
                    if hashlib.sha256((restored / item).read_bytes()).hexdigest() != expected:
                        raise RuntimeError("Backup file restore integrity failed")
            receipt = {"verified": True, "timestamp": time.time(), "manifest": manifest,
                       "owner": "dispatcharr-maintenance-v1",
                       "dispatcharr_image": meta["Image"],
                       "plex_image": self.inspect(self.plex)["Image"]}
            if etv:
                receipt["ersatztv"] = etv
            atomic_json(staging / "verified.json", receipt)
            os.rename(staging, directory / name)
            atomic_json(self.state / "backup-status.json", receipt)
            # Only verified generations owned by this helper are eligible for retention.
            verified = sorted(p for p in directory.iterdir() if p.is_dir()
                              and re.fullmatch(r"\d{8}T\d{6}Z", p.name)
                              and (p / "verified.json").exists()
                              and json.loads((p / "verified.json").read_text()).get("owner")
                              == "dispatcharr-maintenance-v1")
            for expired in verified[:-self.config.get("backup_generations", 7)]:
                if json.loads((expired / "verified.json").read_text()).get("verified"):
                    shutil.rmtree(expired)
            return {"verified": True, "generation": name, "files": len(manifest)}
        finally:
            if dump:
                command(["docker", "exec", self.container, "rm", "-f", dump])

    def health(self, snapshot, job_success=True):
        now = time.time()
        storage = True
        free_bytes = 0
        try:
            require_mount(Path(self.config["recordings_directory"]), self.config["recordings_mount"])
            free_bytes = shutil.disk_usage(self.config["recordings_directory"]).free
            storage = free_bytes >= self.config.get("minimum_recording_free_bytes", 100 * 2**30)
        except (OSError, RuntimeError, subprocess.SubprocessError):
            storage = False
        backup_path = self.state / "backup-status.json"
        backup = json.loads(backup_path.read_text()) if backup_path.exists() else {}
        job_path = self.state / "backup-job.json"
        job = json.loads(job_path.read_text()) if job_path.exists() else {}
        plex_failed = 0
        if job_success:
            scheduled = self.plex_call("/media/subscriptions/scheduled")
            plex_failed = sum(
                item.get("status", "").lower() in {"error", "failed"}
                for item in scheduled.iter("MediaGrabOperation")
            )
        guides = bool(snapshot["guides"]) and snapshot["current_programs"] > 0 and not any(
            source_unhealthy(s["status"], s["updated_at"], now, s["interval"])
            for s in snapshot["guides"])
        metrics = {
            "iptv_maintenance_timestamp_seconds": now,
            "iptv_maintenance_success": int(job_success),
            "iptv_guides_healthy": int(guides),
            "iptv_failed_recordings_24h": snapshot["failed_recordings"],
            "iptv_plex_failed_recordings": plex_failed,
            "iptv_recording_storage_healthy": int(storage),
            "iptv_recording_free_bytes": free_bytes,
            "iptv_backup_verified_timestamp_seconds": backup.get("timestamp", 0),
            "iptv_backup_job_success": int(job.get("success", False)),
        }
        if self.config.get("ersatztv"):
            from ersatztv import ErsatzTV
            try:
                report = ErsatzTV(self).check()
            except Exception:
                # Keep exception text, credentials and programme titles out of metrics.
                report = {"enabled": 1, "check_success": 0, "guide_correct": 0,
                          "restrictions_healthy": 0, "recipe_drift": -1,
                          "guide_hours_min": 0, "channels_checked": 0}
            atomic_json(self.state / "ersatztv-health.json", {"timestamp": now, **report})
            metrics.update({"iptv_ersatztv_" + key: value for key, value in report.items()})
            metrics["iptv_ersatztv_backup_verified_timestamp_seconds"] = (
                backup.get("timestamp", 0) if backup.get("ersatztv", {}).get("verified") else 0)
        output = Path(self.config["metrics_file"])
        # The process umask is deliberately private. Newly created metric
        # directories must still be traversable by Node Exporter's unprivileged UID.
        missing = []
        directory = output.parent
        while not directory.exists():
            missing.append(directory)
            directory = directory.parent
        for directory in reversed(missing):
            directory.mkdir(mode=0o755)
            directory.chmod(0o755)
        temporary = output.with_suffix(".tmp")
        temporary.write_text("".join(f"{key} {value}\n" for key, value in metrics.items()))
        temporary.chmod(0o644)
        os.replace(temporary, output)
        return {"guides_healthy": guides, "storage_healthy": storage,
                "failed_recordings_24h": snapshot["failed_recordings"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["backup", "check", "recipes-export", "recipes-reconcile"])
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="Apply guarded derived-filter reconciliation")
    args = parser.parse_args()
    os.umask(0o077)
    config = json.loads(args.config.read_text())
    require_mount(Path(config["state_directory"]).parent, config["state_mount"])
    runner = Maintenance(config)
    with (runner.state / "maintenance.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            if args.mode == "backup":
                atomic_json(runner.state / "backup-job.json",
                            {"success": False, "started_at": time.time()})
                result = runner.backup()
                atomic_json(runner.state / "backup-job.json",
                            {"success": True, "finished_at": time.time()})
            elif args.mode.startswith("recipes-"):
                from ersatztv import ErsatzTV
                etv = ErsatzTV(runner)
                if args.mode == "recipes-export":
                    # Export must not silently accept drift in an existing baseline.
                    if etv.recipe_path.exists():
                        raise RuntimeError("Recipe export destination already exists")
                    atomic_json(etv.recipe_path, etv.export())
                    result = {"exported": True}
                else:
                    result = etv.reconcile(args.apply)
                    # Full queries belong only in the private plan file.
                    atomic_json(runner.state / "ersatztv-reconcile-plan.json", result)
                    result = {"apply": args.apply, "changes": len(result.get("changes", [])),
                              "updated_filters": result.get("updated_filters", 0)}
            else:
                snapshot = runner.django("snapshot")
                runner.quarantine(snapshot)
                runner.recording_defaults()
                result = runner.health(snapshot)
        except Exception:
            runner.health({"guides": [], "current_programs": 0, "failed_recordings": 0},
                          job_success=False)
            raise
        print(json.dumps(result))


if __name__ == "__main__":
    main()
