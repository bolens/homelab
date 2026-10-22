#!/usr/bin/env python3
"""Coordinate verified Calibre registration before a Kavita export. Requires root."""

import os
import stat
import json
import hashlib
import shutil
import subprocess
import sqlite3
import time
import base64
import importlib.util
import importlib.machinery
import uuid
import fcntl
import pwd
from pathlib import Path

os.umask(0o077)


def run(args):
    return subprocess.run(
        args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout


def inventory(root):
    out = {}
    for d, ds, fs in os.walk(root, followlinks=False):
        for p in (
            [Path(d)]
            + [Path(d) / f for f in fs]
            + [Path(d) / f for f in ds if (Path(d) / f).is_symlink()]
        ):
            s = p.lstat()
            r = str(p.relative_to(root))
            a = {
                k: base64.b64encode(os.getxattr(p, k, follow_symlinks=False)).decode()
                for k in os.listxattr(p, follow_symlinks=False)
            }
            v = {
                "mode": stat.S_IMODE(s.st_mode),
                "uid": s.st_uid,
                "gid": s.st_gid,
                "mtimeNs": s.st_mtime_ns,
                "attrs": a,
                "kind": "link" if p.is_symlink() else "dir" if p.is_dir() else "file",
            }
            if v["kind"] == "file":
                h = hashlib.sha256()
                with p.open("rb") as f:
                    for b in iter(lambda: f.read(1024 * 1024), b""):
                        h.update(b)
                v.update(bytes=s.st_size, sha256=h.hexdigest())
            elif v["kind"] == "link":
                v["target"] = os.readlink(p)
            out[r] = v
    return out


def copy(root, target, manifest):
    target.mkdir(mode=0o700)
    for rel, v in sorted(manifest.items(), key=lambda x: (x[0].count("/"), x[0])):
        p = root / rel
        q = target / rel
        if v["kind"] == "dir":
            q.mkdir(exist_ok=True)
        elif v["kind"] == "link":
            os.symlink(v["target"], q)
        else:
            with p.open("rb") as src, q.open("xb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
        os.chown(q, v["uid"], v["gid"], follow_symlinks=False)
        if v["kind"] != "link":
            os.chmod(q, v["mode"])
        for name, value in v["attrs"].items():
            if name != "system.nfs4_acl":
                os.setxattr(q, name, base64.b64decode(value), follow_symlinks=False)
    for rel, v in sorted(manifest.items(), key=lambda x: -x[0].count("/")):
        os.utime(target / rel, ns=(v["mtimeNs"], v["mtimeNs"]), follow_symlinks=False)


def compare(expected, actual):
    assert set(expected) == set(actual), "namespace mismatch"
    for rel, v in expected.items():
        a = actual[rel]
        v = {
            **v,
            "attrs": {k: x for k, x in v["attrs"].items() if k != "system.nfs4_acl"},
        }
        assert v == a, "restore mismatch"


# Installed as a root-owned supplier; work data is private and outside Git.

RUNTIME = Path(os.environ.get("CALIBRE_SYNC_STATE", "/var/lib/calibre-kavita-sync"))
LIBRARY = Path(os.environ.get("CALIBRE_LIBRARY_PATH", "/mnt/unraid/media/books"))
CONFIG = None
SERVICE = os.environ.get("CALIBRE_WEB_SERVICE", "/run/service/svc-calibre-web")
CALIBRE_CONTAINER = os.environ.get("CALIBRE_CONTAINER", "calibre-web")
WRITER_CONTAINER = os.environ.get("CALIBRE_WRITER_CONTAINER", "readarr")
MEDIA_MOUNT = Path(os.environ.get("CALIBRE_SOURCE_MOUNT", "/mnt/unraid/media"))
STATE_MOUNT = Path(os.environ.get("CALIBRE_SYNC_STATE_MOUNT", "/"))
SOURCE_UID = int(os.environ.get("CALIBRE_EXPORT_UID", "1000"))
SYNC_LOCK = Path(os.environ.get("KAVITA_SYNC_LOCK", str(RUNTIME / "publication.lock")))
PLANNER = Path(
    os.environ.get(
        "CALIBRE_IMPORT_PLANNER", "/usr/local/libexec/calibre-catalog-import"
    )
)
CORE = Path(
    os.environ.get("CALIBRE_CATALOG_SYNC", "/usr/local/libexec/calibre-catalog-sync")
)
EXPORT = os.environ.get(
    "CALIBRE_KAVITA_EXPORT", "/usr/local/libexec/calibre-kavita-sync"
)


def load(path, name):
    spec = importlib.util.spec_from_loader(
        name, importlib.machinery.SourceFileLoader(name, str(path))
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def nfs_proof(manifest, run_dir):
    # Attribute values are not representable on Btrfs. Roundtrip each distinct
    # type/mode/value on the actual mounted NFS filesystem as its owning user.
    fixture = MEDIA_MOUNT / (".calibre-restore-proof-" + uuid.uuid4().hex)
    run(
        [
            "runuser",
            "-u",
            pwd.getpwuid(SOURCE_UID).pw_name,
            "--",
            "mkdir",
            "-m",
            "0700",
            str(fixture),
        ]
    )
    payload = []
    seen = set()
    for value in manifest.values():
        if value["kind"] == "link":
            continue
        for name, raw in value["attrs"].items():
            key = (name, raw, value["kind"], value["mode"])
            if key not in seen:
                seen.add(key)
                payload.append(list(key))
    script = """import os,json,base64,sys
from pathlib import Path
r=Path(sys.argv[1]);items=json.load(sys.stdin)
for i,(name,raw,kind,mode) in enumerate(items):
 p=r/str(i)
 if kind=='dir':p.mkdir()
 else:p.write_bytes(b'fixture')
 p.chmod(mode);value=base64.b64decode(raw);os.setxattr(p,name,value);assert os.getxattr(p,name)==value
 if kind=='dir':p.rmdir()
 else:p.unlink()
r.rmdir()
"""
    command = [
        "runuser",
        "-u",
        pwd.getpwuid(SOURCE_UID).pw_name,
        "--",
        "/usr/bin/python3",
        "-c",
        script,
        str(fixture),
    ]
    p = subprocess.run(
        command,
        input=json.dumps(payload).encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert p.returncode == 0, "NFS restore metadata proof failed"
    return len(payload)


def require_root():
    if os.geteuid() != 0:
        raise RuntimeError("root required for scoped container coordination")


def record_sync_success():
    (RUNTIME / "last-sync-receipt.json").write_text(json.dumps({
        "status": "verified", "exportAndScanRequested": True,
        "finishedAtUnix": time.time(),
    }))
    (RUNTIME / "last-failure.log").unlink(missing_ok=True)


def main():
    require_root()
    assert run(
        ["findmnt", "-T", str(LIBRARY), "-no", "TARGET", "-t", "noautofs"]
    ).decode().strip() == str(MEDIA_MOUNT), "required media mount absent"
    assert run(
        ["findmnt", "-T", str(RUNTIME.parent), "-no", "TARGET", "-t", "noautofs"]
    ).decode().strip() == str(STATE_MOUNT), "required backup mount absent"
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    assert (
        RUNTIME.resolve() == RUNTIME
        and RUNTIME.stat().st_uid == os.geteuid()
        and stat.S_IMODE(RUNTIME.stat().st_mode) == 0o700
    )
    with (
        (RUNTIME / "runner.lock").open("a") as lock,
        SYNC_LOCK.open("a") as export_guard,
    ):
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(export_guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Catalog sync already running; skipped")
            return
        planner = load(PLANNER, "catalog_planner")
        plan = planner.plan(LIBRARY)
        (RUNTIME / "last-plan.json").write_text(json.dumps(plan))
        if os.environ.get("CALIBRE_AUTO_REGISTER", "false").lower() != "true":
            plan["candidates"] = []
        if not plan["candidates"]:
            print(
                "No clear new Calibre books; exporting registered catalog", flush=True
            )
            # Public export diagnostics may include titles; keep them in a private log.
            export_guard.close()
            log = RUNTIME / "last-export.log"
            with log.open("wb") as stream:
                p = subprocess.run(
                    [EXPORT],
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    env={**os.environ, "KAVITA_SYNC_LOCK": str(SYNC_LOCK)},
                )
            assert p.returncode == 0, "export failed; private log retained"
            record_sync_success()
            return
        source_bytes = sum(
            (Path(directory) / name).stat().st_size
            for directory, _, files in os.walk(LIBRARY, followlinks=False)
            for name in files
            if not (Path(directory) / name).is_symlink()
        )
        incoming_bytes = sum(row.get("bytes", 0) for row in plan["candidates"])
        required_bytes = 4 * source_bytes + 2 * incoming_bytes + 5 * 1024**3
        assert shutil.disk_usage(RUNTIME).free > required_bytes, (
            "backup and rehearsal capacity insufficient"
        )
        work = RUNTIME / ("run-" + uuid.uuid4().hex)
        work.mkdir(mode=0o700)
        (work / "plan.json").write_text(json.dumps(plan))
        attr_count = nfs_proof(inventory(LIBRARY), work)
        readarr_running = False
        web_up = False
        readarr_stopped = False
        web_stopped = False
        safe_resume = True
        try:
            item = json.loads(run(["docker", "inspect", WRITER_CONTAINER]))[0]
            readarr_running = item["State"]["Running"]
            status = run(
                ["docker", "exec", CALIBRE_CONTAINER, "s6-svstat", "-o", "up", SERVICE]
            ).strip()
            assert status in (b"true", b"false")
            web_up = status == b"true"
            if readarr_running:
                readarr_stopped = True
                run(["docker", "stop", "--time", "60", WRITER_CONTAINER])
            if web_up:
                web_stopped = True
                run(
                    [
                        "docker",
                        "exec",
                        CALIBRE_CONTAINER,
                        "s6-svc",
                        "-d",
                        "-wD",
                        "-T",
                        "30000",
                        SERVICE,
                    ]
                )
            fresh = planner.plan(LIBRARY)
            assert fresh["candidates"] == plan["candidates"], (
                "source changed before quiesce"
            )
            backup = work / "backup"
            restore = work / "restore"
            backup.mkdir(mode=0o700)
            restore.mkdir(mode=0o700)
            config_path = CONFIG or Path(
                run(
                    [
                        "docker",
                        "inspect",
                        "--format",
                        '{{range .Mounts}}{{if eq .Destination "/config"}}{{.Source}}{{end}}{{end}}',
                        CALIBRE_CONTAINER,
                    ]
                )
                .decode()
                .strip()
            )
            assert config_path.is_absolute() and config_path.is_dir(), (
                "Calibre config unavailable"
            )
            manifests = {}
            for name, source in {"books": LIBRARY, "calibre-web": config_path}.items():
                m = inventory(source)
                manifests[name] = m
                copy(source, backup / name, m)
                compare(m, inventory(backup / name))
                assert inventory(source) == m
                copy(backup / name, restore / name, m)
                compare(m, inventory(restore / name))
                for rel, value in m.items():
                    f = restore / name / rel
                    if value["kind"] == "file":
                        with f.open("rb") as stream:
                            magic = stream.read(16)
                        if magic == b"SQLite format 3\0":
                            c = sqlite3.connect(str(f))
                            assert c.execute("pragma integrity_check").fetchall() == [
                                ("ok",)
                            ]
                            c.close()
            attr_count = nfs_proof(manifests["books"], work)
            inv = work / "books-inventory.json"
            inv.write_text(json.dumps(manifests["books"]))
            receipt = {
                "version": 1,
                "status": "verified",
                "libraryPath": str(LIBRARY),
                "backupPath": str(backup / "books"),
                "inventoryPath": str(inv),
                "baselineDatabasePath": str(backup / "books/metadata.db"),
                "createdAtUnix": time.time(),
                "quiesced": True,
                "nfsAclVerified": True,
                "expectedCandidateHashes": [v["sha256"] for v in fresh["candidates"]],
            }
            receipt_path = work / "receipt.json"
            receipt_path.write_text(json.dumps(receipt))
            safe_resume = False
            with (work / "apply.log").open("wb") as log:
                p = subprocess.run(
                    [
                        "/usr/bin/python3",
                        str(CORE),
                        str(LIBRARY),
                        "--apply",
                        "--receipt",
                        str(receipt_path),
                        "--container",
                        CALIBRE_CONTAINER,
                        "--planner",
                        str(PLANNER),
                    ],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=1200,
                )
            # Core only returns success after old record/file checks. Failure recovery
            # must be proved before releasing writers; preserve evidence otherwise.
            if p.returncode != 0:
                m = manifests["books"]
                current = inventory(LIBRARY)
                safe_resume = current == m
                raise RuntimeError("catalog apply refused; private evidence retained")
            safe_resume = True
            assert inventory(config_path) == manifests["calibre-web"], (
                "Calibre-Web state changed during import"
            )
            c = sqlite3.connect(
                "file:" + str(LIBRARY / "metadata.db") + "?mode=ro", uri=True
            )
            assert c.execute("pragma integrity_check").fetchall() == [("ok",)]
            count = c.execute("select count(*) from books").fetchone()[0]
            c.close()
            assert count == fresh["baseline"]["bookCount"] + len(fresh["candidates"]), (
                "catalog count mismatch"
            )
            summary = {
                "status": "verified",
                "addedBooks": len(fresh["candidates"]),
                "catalogBooks": count,
                "nfsAttributeVariants": attr_count,
                "finishedAtUnix": time.time(),
            }
            (RUNTIME / "last-catalog-receipt.json").write_text(json.dumps(summary))
            print(json.dumps(summary), flush=True)
            # Remove only this verified run’s sensitive backup and rehearsal material.
            shutil.rmtree(work)
        finally:
            if safe_resume:
                if web_stopped:
                    run(["docker", "exec", CALIBRE_CONTAINER, "s6-svc", "-u", SERVICE])
                if readarr_stopped:
                    run(["docker", "start", WRITER_CONTAINER])
            else:
                print("Writers remain quiesced; recovery evidence retained", flush=True)
        export_guard.close()
        with (RUNTIME / "last-export.log").open("wb") as log:
            p = subprocess.run(
                [EXPORT],
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=1200,
                env={**os.environ, "KAVITA_SYNC_LOCK": str(SYNC_LOCK)},
            )
        assert p.returncode == 0, "catalog updated; export failed; private log retained"
        record_sync_success()
        print(
            "Catalog and verified export synchronized; Kavita scan requested",
            flush=True,
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        import traceback

        if (
            RUNTIME.is_dir()
            and not RUNTIME.is_symlink()
            and RUNTIME.stat().st_uid == os.geteuid()
            and stat.S_IMODE(RUNTIME.stat().st_mode) == 0o700
        ):
            (RUNTIME / "last-failure.log").write_text(traceback.format_exc())
        print(
            "Calibre synchronization stopped: "
            + type(error).__name__
            + "; private failure log retained",
            flush=True,
        )
        raise SystemExit(1)
