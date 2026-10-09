"""Default-off ACTIVE-scope parent for newly owned NFS fixtures; no library grant.
Scope evidence is root-reviewed, not discovered here. Unknown or lost ACK retains
fixtures/container, with no automatic retry, deletion or fallback.
"""

import argparse
import importlib.util
import selectors
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import threading
import weakref

IMAGE = None
KOMGA = None
WORKER = None
PROBE = None
PROBE_SHA = None
HARDLINK_KERNEL = None
HARDLINK_KERNEL_SHA = "393d398e1e08ce147d4f8efa60879b99a910af582fbb6ae70e0f71cc0229d0bf"
READY = None
READY_SHA = None
PARITY = None
PARITY_SHA = None
MAP = None
MAP_SHA = None
NATIVE_RECEIPT = None
NATIVE_RECEIPT_SHA = None
NATIVE_IMAGE = None
NATIVE_MAP_COUNT = None
WRITER_SHA = None
SELECTED_SDK = None
READY_INPUT = None
READY_INPUT_SHA = None
SCOPE_SHA="6d4b43c84a653aa56cbf22e25563b26e4cb8a5c700cce5d8a124612be3818608"
_NATIVE_PROJECTOR=None
CHECKED_PROBE_SHA = "77325f0a7fd14b6e2e1a1f91aaf4c66cb53b5e2fd4cffdd34453642002afd1ec"
_COHORT = None
DOCKER = ["pkexec", "/usr/bin/docker", "--host", "unix:///run/docker.sock"]


class Held(ValueError):
    pass


def check(v, why):
    if not v:
        raise Held(why)


def encode(v):
    return json.dumps(
        v, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def exact(v, keys):
    check(type(v) is dict and set(v) == set(keys), "schema")


def canonical(raw):
    p = Path(raw)
    check(
        p.is_absolute()
        and ".." not in p.parts
        and p.resolve(strict=False) == p
        and not any(x.is_symlink() for x in (p, *p.parents)),
        "canonical",
    )
    return p


def stamp(p):
    x = os.lstat(canonical(p))
    return [
        x.st_dev,
        x.st_ino,
        x.st_size,
        x.st_mtime_ns,
        x.st_ctime_ns,
        x.st_mode,
        x.st_uid,
        x.st_gid,
        x.st_nlink,
    ]


def checked_buffer(p, expected=None, source=False):
    p = canonical(p)
    before = tuple(stamp(p))
    nodes = tuple((str(q), tuple(stamp(q)[i] for i in (0,1,5,6,7))) for q in p.parents)
    check(stat.S_ISREG(before[5]) and before[6] == 1000
          and stat.S_IMODE(before[5]) in ((0o600,0o644) if source else (0o600,))
          and before[8] == 1 and 0 <= before[2] <= 32*1024**2, 'private-file')
    fd = os.open(p, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        x = os.fstat(fd)
        if (x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode,x.st_uid,x.st_gid,x.st_nlink) != before:raise Held('read-fd-CAS')
        parts=[];remaining=before[2]+1
        while remaining:
            raw=os.read(fd,min(remaining,1024**2))
            if not raw:break
            parts.append(raw);remaining-=len(raw)
        raw=b''.join(parts);sha=digest(raw)
        check(len(raw)==before[2] and (expected is None or sha==expected), 'file-drift')
        x=os.fstat(fd)
        if (x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode,x.st_uid,x.st_gid,x.st_nlink)!=before:raise Held('read-fd-CAS')
    finally:
        os.close(fd)
    result={'signature':list(before),'sha256':sha}
    for q,v in nodes:
        x=os.lstat(q)
        if (x.st_dev,x.st_ino,x.st_mode,x.st_uid,x.st_gid)!=v:raise Held('read-ancestor-CAS')
    x=os.lstat(p)
    if (x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode,x.st_uid,x.st_gid,x.st_nlink)!=before:raise Held('read-leaf-CAS')
    return raw,result


def fact(p, expected=None, source=False):
    return checked_buffer(p,expected,source)[1]


def read(p, expected=None):
    raw,f=checked_buffer(p,expected)
    def pairs(items):
        out={}
        for k,v in items:
            check(k not in out,'duplicate-key');out[k]=v
        return out
    v=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(Held('number')))
    if fact(p)!=f:raise Held('read-drift')
    return v,f


def ancestry(paths):
    out = {}
    for p in paths:
        for q in canonical(p).parents:
            v = stamp(q)
            check(stat.S_ISDIR(v[5]), "ancestor")
            value = [v[i] for i in (0, 1, 5, 6, 7)]
            if str(q) in out and out[str(q)] != value:raise Held('ancestor-conflict')
            out[str(q)] = value
    return out


def write(p, v):
    raw = encode(v)
    fd = os.open(
        canonical(p), os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    fd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return fact(p, digest(raw))


def private_parent(p):
    s = stamp(p)
    check(
        stat.S_ISDIR(s[5]) and s[6] == 1000 and stat.S_IMODE(s[5]) == 0o700,
        "private-parent",
    )
    return s


def fresh_scope(scope):
    check(
        type(scope["observed"]) is int and 0 <= time.time() - scope["observed"] <= 120,
        "scope-expired-fresh-recapture-required",
    )


def outside(path, roots):
    return all(not path.is_relative_to(r) and not r.is_relative_to(path) for r in roots)


def validate(plan, scope):
    exact(
        plan,
        (
            "version",
            "kind",
            "scope",
            "fixture_parent",
            "fixture_name",
            "fixture_parent_signature",
            "library_root",
            "expected_device",
            "mount_identity",
            "output_root",
        ),
    )
    check(
        type(plan["version"]) is int
        and plan["version"] == 2
        and plan["kind"] == "approved-negative-nfs-active-probe-parent",
        "plan",
    )
    exact(
        scope,
        (
            "version",
            "kind",
            "approved_disposable_diagnostic",
            "observed",
            "current_active_scanner_publication_paths_reviewed",
            "future_mylar_destination_verified",
            "future_mylar_destination",
            "writer_lifecycle_resume_authorized",
            "forbidden_roots",
            "sources",
        ),
    )
    check(
        type(scope["version"]) is int
        and scope["version"] == 2
        and scope["kind"] == "root-reviewed-nfs-active-disposable-scope"
        and scope["approved_disposable_diagnostic"] is True
        and scope["current_active_scanner_publication_paths_reviewed"] is True
        and scope["future_mylar_destination_verified"] is False
        and scope["future_mylar_destination"] is None
        and scope["writer_lifecycle_resume_authorized"] is False
        and type(scope["observed"]) is int
        and 0 <= time.time() - scope["observed"] <= 120,
        "scope",
    )
    check(
        type(scope["forbidden_roots"]) is list
        and 1 <= len(scope["forbidden_roots"]) <= 32
        and len(scope["forbidden_roots"]) == len(set(scope["forbidden_roots"])),
        "roots",
    )
    roots = [canonical(x) for x in scope["forbidden_roots"]]
    check(all(p.is_dir() for p in roots), "roots")
    parent = canonical(plan["fixture_parent"])
    library = canonical(plan["library_root"])
    out = canonical(plan["output_root"])
    check(
        library in roots,
        "library-required",
    )
    check(
        type(plan["expected_device"]) is int
        and plan["expected_device"] > 0
        and stamp(library)[0] == plan["expected_device"],
        "device",
    )
    check(
        type(plan["fixture_name"]) is str
        and re.fullmatch(r"\.comic-nfs-probe-[0-9a-f]{32}", plan["fixture_name"]),
        "new-own-name",
    )
    fixture = parent / plan["fixture_name"]
    check(not os.path.lexists(fixture) and not os.path.lexists(out), "new-paths")
    check(
        outside(fixture, roots)
        and outside(out, roots)
        and not out.is_relative_to(fixture)
        and not fixture.is_relative_to(out),
        "scope-overlap",
    )
    check(
        stamp(parent) == plan["fixture_parent_signature"]
        and stamp(parent)[0] == plan["expected_device"]
        and stat.S_ISDIR(stamp(parent)[5]),
        "parent-device-signature",
    )
    check(
        stamp(parent)[6] == 1000 and not stat.S_IMODE(stamp(parent)[5]) & 0o022,
        "owned-parent",
    )
    private_parent(out.parent)
    physical = {tuple(stamp(r)[:2]) for r in roots}
    check(
        not any(
            tuple(stamp(p)[:2]) in physical
            for p in (parent, *parent.parents, out.parent, *out.parent.parents)
        ),
        "physical-overlap",
    )
    exact(
        plan["mount_identity"],
        ("source", "target", "fstype", "fsroot", "options", "maj:min"),
    )
    check(
        plan["mount_identity"]["fstype"] == "nfs4"
        and all(type(v) is str and v for v in plan["mount_identity"].values()),
        "mount-identity",
    )
    check(
        type(scope["sources"]) is dict
        and set(scope["sources"])
        == {"current_runtime_bracket", "current_mylar_hold", "current_worker_created",
            "current_komga_libraries", "current_komga_effective_scope",
            "protected_catalog_cache_recovery_scope", "continuous_raw_writer_lease"},
        "complete-scope-sources",
    )
    for ref in scope["sources"].values():
        exact(ref, ("path", "sha256"))
        fact(ref["path"], ref["sha256"])
    return fixture, out, roots


def fresh_native(call, container_id):
    check(type(container_id) is str and re.fullmatch("[a-f0-9]{64}",container_id),"fresh-daemon-container")
    source,original=checked_buffer(READY,READY_SHA,source=True)
    request,original_input=checked_buffer(READY_INPUT,READY_INPUT_SHA)
    expected=json.loads(request)
    response=call(DOCKER+['exec','-i','--user','1000:1000',container_id,'/lsiopy/bin/python3','-I','-B','-c',source.decode()],request)
    raw=response if type(response) is bytes else response.stdout
    value=json.loads(raw)
    exact(value,('version','nonce','source_sha256','process','publication','config'))
    check(value['version']==1 and value['nonce']==expected['nonce'] and value['source_sha256']==READY_SHA,'fresh-daemon-probe-binding')
    exact(value['process'],('pid','start_ticks','argv'))
    check(type(value['process']['pid']) is int and value['process']['pid']>0
          and type(value['process']['start_ticks']) is int and value['process']['start_ticks']>0
          and type(value['process']['argv']) is list and value['process']['argv'],'fresh-daemon-process')
    exact(value['config'],('path','sha256','signature9'))
    if fact(READY,READY_SHA,source=True)!=original or fact(READY_INPUT,READY_INPUT_SHA)!=original_input:raise Held('fresh-daemon-probe-source-CAS')
    return value


def native_gate():
    if _COHORT is None:raise Held('explicit-current-source-cohort-required')
    _COHORT.close()
    return _COHORT.readiness()


def identities(rows):
    check(type(rows) is list and len(rows) == 2, "containers")
    rows = {r["Name"]: r for r in rows}
    check(set(rows) == {"/mylar3", "/komga-comic-normalizer-1"}, "containers")
    out = []
    for name, image, status, running in (
        ("/mylar3", NATIVE_IMAGE, "running", True),
        ("/komga-comic-normalizer-1", WORKER, "created", False),
    ):
        r = rows[name]
        s = r["State"]
        check(
            r["Image"] == image
            and s["Status"] == status
            and s["Running"] is running
            and all(
                s[k] is False for k in ("Paused", "Restarting", "Dead", "OOMKilled")
            )
            and type(s["Pid"]) is int
            and (s["Pid"] > 0 if running else s["Pid"] == 0)
            and re.fullmatch("[a-f0-9]{64}", r["Id"]),
            "runtime",
        )
        out.append(
            dict(id=r["Id"], image=image, pid=s["Pid"], started_at=s["StartedAt"])
        )
    return out


def configured_writer_mapping(mounts,config,writer_root):
    # Derive DATA from the COMPLETE original mount table, never just /config.
    check(type(mounts) is list and 1<=len(mounts)<=64,'native-config-mount-table')
    child=Path(config['path']);destination=Path('/config')
    check(child.is_absolute() and '..' not in child.parts and child.name=='config.ini' and child.parent.is_relative_to(destination),'native-config-child-path')
    base=[m for m in mounts if m.get('Destination')=='/config']
    check(len(base)==1 and base[0]['Type'] in ('bind','volume') and base[0]['RW'] is True,'native-config-mount')
    def project(path):
        choices=[]
        for row in mounts:
            check(type(row) is dict and row.get('Type') in ('bind','volume') and type(row.get('RW')) is bool,'native-config-mount-kind')
            source=canonical(row['Source']);target=Path(row['Destination'])
            check(target.is_absolute() and '..' not in target.parts and str(target)==row['Destination'],'native-config-destination')
            if path==target or target in path.parents:choices.append((len(target.parts),source,target,row['RW']))
        check(bool(choices),'native-config-unmapped')
        maximum=max(value[0] for value in choices);selected=[value for value in choices if value[0]==maximum]
        check(len(selected)==1 and selected[0][3] is True,'native-config-ambiguous-or-readonly')
        _,source,target,_=selected[0]
        return canonical(source/path.relative_to(target))
    data=project(child.parent)
    check(project(child)==data/'config.ini' and project(child.parent/'media-writer')==data/'media-writer','native-config-leaf-or-writer-shadow')
    check(canonical(writer_root)==data/'media-writer','same-actual-native-config-writer-mapping')
    return data


def live_mapping(rows, roots):
    check(type(rows) is list and len(rows) == 3, "live-three-container-mapping")
    byname = {r["Name"]: r for r in rows}
    check(
        set(byname) == {"/mylar3", "/komga-comic-normalizer-1", "/komga"}, "live-names"
    )
    ids = identities([byname["/mylar3"], byname["/komga-comic-normalizer-1"]])
    native = [m for m in byname["/mylar3"]["Mounts"] if m["Destination"] == "/data"]
    check(
        len(native) == 1
        and native[0]["Type"] == "bind"
        and canonical(native[0]["Source"]).is_absolute(),
        "mylar-media-map",
    )
    reader = byname["/komga"]
    state = reader["State"]
    check(
        reader["Image"] == KOMGA
        and state["Running"] is True
        and state["Status"] == "running"
        and all(
            state[k] is False for k in ("Paused", "Restarting", "Dead", "OOMKilled")
        )
        and type(state["Pid"]) is int
        and state["Pid"] > 0
        and re.fullmatch("[a-f0-9]{64}", reader["Id"]),
        "reader-runtime",
    )
    mounts = [m for m in reader["Mounts"] if m["Destination"].startswith("/data")]
    check(
        len(mounts) == 2
        and sorted((m["Destination"], str(canonical(m["Source"])), m["Type"]) for m in mounts)
        == [
            ("/data/comics", str(canonical(Path(native[0]["Source"])/"comics")), "bind"),
            ("/data/manga", str(canonical(Path(native[0]["Source"])/"manga")), "bind"),
        ],
        "reader-media-map",
    )
    check(
        all(canonical(m["Source"]) in roots for m in mounts),
        "all-reader-mounted-roots-forbidden",
    )
    return dict(
        native_worker=ids,
        reader=dict(
            id=reader["Id"],
            image=reader["Image"],
            pid=state["Pid"],
            started_at=state["StartedAt"],
        ),
        media_mounts=[
            dict(source=m["Source"], destination=m["Destination"], rw=m["RW"])
            for m in mounts
        ],
    )


def mount_identity(value):
    check(
        type(value) is dict
        and set(value) == {"filesystems"}
        and len(value["filesystems"]) == 1,
        "findmnt",
    )
    row = value["filesystems"][0]
    check(
        set(row) == {"source", "target", "fstype", "fsroot", "options", "maj:min"}
        and row["fstype"] == "nfs4",
        "findmnt",
    )
    return row


def command(name, fixture, out, roots, inp, input_sha):
    mounts = [
        (str(fixture), str(fixture), True),
        (str(fixture), "/config", False),
        (str(out), str(out), True),
        (str(PROBE), str(PROBE), False),
        (str(HARDLINK_KERNEL), str(HARDLINK_KERNEL), False),
        (str(inp), str(inp), False),
    ] + [(str(p), str(p), False) for p in roots]
    check(len(set(x[1] for x in mounts)) == len(mounts), "duplicate-mount")
    argv = DOCKER + [
        "create",
        "--pull",
        "never",
        "--name",
        name,
        "--label",
        "com.homelab.nfs.probe=" + name,
        "--user",
        "1000:1000",
        "--read-only",
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "64",
        "--entrypoint",
        "/lsiopy/bin/python3",
    ]
    for source, target, rw in mounts:
        check(not any(c in source + target for c in ",\n\r"), "mount-spelling")
        argv += [
            "--mount",
            "type=bind,src=" + source + ",dst=" + target + ("" if rw else ",readonly"),
        ]
    return argv + [
        IMAGE,
        str(PROBE),
        "--input",
        str(inp),
        "--input-sha256",
        input_sha,
        "--source-sha256",
        PROBE_SHA,
        "--kernel",
        str(HARDLINK_KERNEL),
    ], mounts


def profile(row, name, mounts):
    h = row["HostConfig"]
    c = row["Config"]
    s = row["State"]
    check(
        row["Image"] == IMAGE
        and c["User"] == "1000:1000"
        and c["Labels"].get("com.homelab.nfs.probe") == name
        and s["Status"] == "created"
        and s["Running"] is False
        and type(s["Pid"]) is int and s["Pid"] == 0
        and all(s.get(k) is False for k in ("Paused","Restarting","Dead","OOMKilled")),
        "child",
    )
    check(
        h["ReadonlyRootfs"] is True
        and h["Privileged"] is False
        and h["NetworkMode"] == "none"
        and h["PidMode"] == ""
        and not h.get("CapAdd")
        and h["CapDrop"] == ["ALL"]
        and h["SecurityOpt"] == ["no-new-privileges"]
        and h["PidsLimit"] == 64
        and not h.get("Binds")
        and not h.get("Tmpfs")
        and not h.get("Devices"),
        "child-profile",
    )
    check(
        len(row["Mounts"]) == len(mounts)
        and all(m["Type"] == "bind" for m in row["Mounts"])
        and sorted((m["Source"], m["Destination"], m["RW"]) for m in row["Mounts"])
        == sorted(mounts),
        "child-mounts",
    )
    check(re.fullmatch("[a-f0-9]{64}", row["Id"]), "child-id")
    return row["Id"]


def probe_existing_parent(a, engine=subprocess.run, lease=None):
    check(os.geteuid() == 1000, "caller-uid")
    os.umask(0o077)
    plan, pf = read(a.input, a.input_sha256)
    exact(plan["scope"], ("path", "sha256"))
    scope, sf = read(plan["scope"]["path"], plan["scope"]["sha256"])
    fixture, out, roots = validate(plan, scope)
    controls = {
        canonical(a.input): pf,
        canonical(plan["scope"]["path"]): sf,
        Path(__file__): fact(__file__, a.source_sha256,source=True),
        READY: fact(READY, READY_SHA, source=True),
        PARITY: fact(PARITY, PARITY_SHA, source=True),
        MAP: fact(MAP, MAP_SHA),
        PROBE:fact(PROBE,PROBE_SHA,source=True),
        HARDLINK_KERNEL:fact(HARDLINK_KERNEL,HARDLINK_KERNEL_SHA,source=True),
        **native_gate(),
    }
    for ref in scope["sources"].values():
        controls[canonical(ref["path"])] = fact(ref["path"], ref["sha256"])
    ancestors = ancestry([*controls, fixture, out, *roots])
    rootstates = {p: stamp(p) for p in roots}
    if not a.execute:
        return dict(
            executable=False,
            current_active_scope_reviewed=True,
            future_mylar_destination_verified=False,
            actual_library_platform_verified=False,
            publication_authority=False,
        )
    out.mkdir(mode=0o700)
    ancestors = ancestry([*controls, fixture, out / "acceptance.json", *roots])

    def emit(name, value):
        p = out / name
        controls[p] = write(p, value)
        return p

    def call(argv, data=None):
        try:
            r = engine(argv, input=data, capture_output=True, timeout=900, check=False)
        except (subprocess.TimeoutExpired, PermissionError, OSError):
            raise Held("engine-ack-unavailable-no-replay") from None
        check(
            r.returncode == 0
            and len(r.stdout) <= 8 * 1024**2
            and len(r.stderr) <= 4 * 1024**2,
            "engine-exit",
        )
        return r

    def observe():
        rows = json.loads(
            call(
                DOCKER + ["inspect", "mylar3", "komga-comic-normalizer-1", "komga"]
            ).stdout
        )
        ids = live_mapping(rows, roots)
        health = fresh_native(call, next(r["Id"] for r in rows if r["Name"]=="/mylar3"))
        pub = health['publication']
        if lease is None:
            check(pub['state'] == 'held' and pub['reason'] == 'startup-restart-required'
                  and pub['census']['revision'] == 13 and len(pub['census']['keys']) == 13, 'held-census')
        else:
            lease.pulse()
            check(pub['state'] == 'held' and pub['reason'] == 'writer-busy'
                  and pub['census'] is None, 'held-by-continuous-own-writer')
        return dict(identity=ids, publication=pub,native_process=health["process"],native_config=health["config"])

    def continuity():
        for p, f in controls.items():
            check(fact(p, source=p in (READY, PARITY, Path(__file__),PROBE,HARDLINK_KERNEL)) == f, "control-drift")
        check(
            ancestry([*controls, fixture, out, *roots]) == ancestors, "ancestor-drift"
        )
        for p, s in rootstates.items():
            check(stamp(p) == s, "forbidden-root-drift")

    fresh_scope(scope)
    initial = observe()
    emit("preflight.json", initial)
    modules = json.loads(
        call(
            DOCKER
            + ["exec", "-i", "--user", "1000", "mylar3", "/lsiopy/bin/python3", "-"],
            PARITY.read_bytes(),
        ).stdout
    )
    check(
        modules == read(MAP, MAP_SHA)[0] and len(modules) == NATIVE_MAP_COUNT, "actual-native-module-parity"
    )
    emit("parity.json", modules)
    observed_mount = mount_identity(
        json.loads(
            call(
                [
                    "findmnt",
                    "--json",
                    "--target",
                    plan["fixture_parent"],
                    "--output",
                    "SOURCE,TARGET,FSTYPE,FSROOT,OPTIONS,MAJ:MIN",
                ]
            ).stdout
        )
    )
    check(observed_mount == plan["mount_identity"], "mount-drift")
    check(
        mount_identity(
            json.loads(
                call(
                    [
                        "findmnt",
                        "--json",
                        "--target",
                        plan["library_root"],
                        "--output",
                        "SOURCE,TARGET,FSTYPE,FSROOT,OPTIONS,MAJ:MIN",
                    ]
                ).stdout
            )
        )
        == observed_mount,
        "same-library-mount",
    )
    check(
        stamp(plan["fixture_parent"]) == plan["fixture_parent_signature"],
        "parent-drift",
    )
    continuity()
    check(observe() == initial, "pre-create-held-drift")
    fresh_scope(scope)
    # Newly absent fixture is the only NFS write scope. No pre-existing files touched.
    fd = os.open(
        canonical(plan["fixture_parent"]), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    )
    try:
        s = os.fstat(fd)
        check(
            [
                s.st_dev,
                s.st_ino,
                s.st_size,
                s.st_mtime_ns,
                s.st_ctime_ns,
                s.st_mode,
                s.st_uid,
                s.st_gid,
                s.st_nlink,
            ]
            == plan["fixture_parent_signature"],
            "parent-fd",
        )
        os.mkdir(plan["fixture_name"], 0o700, dir_fd=fd)
        os.fsync(fd)
    finally:
        os.close(fd)
    private_parent(fixture)
    check(
        stamp(fixture)[0] == plan["expected_device"] and not os.listdir(fixture),
        "fixture-device",
    )
    continuity()
    fd=os.open(fixture,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        z=os.fstat(fd)
        check([z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]==stamp(fixture),'fixed-created-scope')
        for leaf in ('source','target'):
            os.mkdir(leaf,0o700,dir_fd=fd)
        os.fsync(fd)
    finally:os.close(fd)
    probe_input = emit('probe-input.json',dict(version=1,kind='reviewed-disposable-hardlink-nfs-canary',nonce=uuid.uuid4().hex+uuid.uuid4().hex,
        root=str(fixture),root9=stamp(fixture),source_parent9=stamp(fixture/'source'),target_parent9=stamp(fixture/'target'),
        device=plan['expected_device'],mount=plan['mount_identity'],forbidden_roots=[str(p) for p in roots],seconds=120))
    name = "comic-nfs-probe-" + uuid.uuid4().hex
    argv, mounts = command(
        name, fixture, out, roots, probe_input, controls[probe_input]["sha256"]
    )
    emit(
        "create-intent.json",
        dict(
            argv=argv,
            fixture_retained=True,
            container_retained=True,
            automatic_retry=False,
        ),
    )
    child = call(argv).stdout.decode().strip()
    check(re.fullmatch("[a-f0-9]{64}", child), "create-ack")
    emit("create-result.json", dict(id=child, name=name))
    row = json.loads(call(DOCKER + ["inspect", child]).stdout)
    check(
        type(row) is list and len(row) == 1 and profile(row[0], name, mounts) == child,
        "profile-ack",
    )
    check(row[0]["Config"].get("Entrypoint")==["/lsiopy/bin/python3"] and row[0]["Config"].get("Cmd")==argv[argv.index(IMAGE)+1:],"child-exact-command")
    initial_child_static={k:row[0][k] for k in ("Config","HostConfig","Mounts")}
    emit("profile.json", row[0])
    continuity()
    check(observe() == initial, "pre-start-held-drift")
    fresh_scope(scope)
    r = call(DOCKER + ["start", "-a", child])
    ack = json.loads(r.stdout)
    exact(ack,('version','kind','source_sha256','kernel_sha256','input_sha256','report','transitions','facts','directories','root9','actual_library_platform_verified','native_grant','publication_authority'))
    check(ack['version']==1 and ack['kind']=='checked-hardlink-canary-child' and ack['source_sha256']==PROBE_SHA and ack['kernel_sha256']==HARDLINK_KERNEL_SHA
          and ack['input_sha256']==controls[probe_input]['sha256'] and all(ack[k] is False for k in ('actual_library_platform_verified','native_grant','publication_authority')),'hardlink-child-ack')
    check([(v['action'],v['nlink']) for v in ack['transitions']]==[('stage',2),('collision',2),('retire',1),('restore',2),('unstage',1)],'hardlink-finite-projections')
    exact(ack['report'],('path','sha256','signature9'))
    check(ack['report']['path']==str(fixture/'result.json'),'hardlink-report-path')
    report,rf=read(fixture/'result.json',ack['report']['sha256'])
    check(rf['signature']==ack['report']['signature9'] and report['transitions']==ack['transitions'] and report['collision_errno']==17,'hardlink-report-original')
    emit('probe-ack.json',ack)
    supported=True
    terminal = json.loads(call(DOCKER + ["inspect", child]).stdout)[0]
    check(
        all(terminal[k]==v for k,v in initial_child_static.items())
        and terminal["Id"] == child
        and terminal["Image"] == IMAGE
        and terminal["State"]["Status"] == "exited"
        and terminal["State"]["ExitCode"] == 0
        and terminal["State"]["Running"] is False
        and type(terminal["State"]["Pid"]) is int and terminal["State"]["Pid"]==0
        and all(terminal["State"].get(k) is False for k in ("Paused","Restarting","Dead","OOMKilled")),
        "child-terminal",
    )
    check(observe() == initial, "post-held-drift")
    fresh_scope(scope)
    emit("postflight.json", initial)
    expected={'source/source.bin','source/collision.bin','target/foreign.bin','stage-intent.json','collision-intent.json','retire-intent.json','restore-intent.json','unstage-intent.json','result.json'}
    check(set(os.listdir(fixture))=={'source','target'}|{n for n in expected if '/' not in n}
          and set(os.listdir(fixture/'source'))=={'source.bin','collision.bin'} and set(os.listdir(fixture/'target'))=={'foreign.bin'},'hardlink-fixture-census')
    fixture_files={fixture/name:fact(fixture/name) for name in expected}
    fixture_dirs={name:stamp(fixture/name) for name in ('source','target')}
    check(set(ack['facts'])==set(str(p) for p in fixture_files) and ack['directories']==fixture_dirs and ack['root9']==stamp(fixture),'hardlink-child-original-namespace')
    for q,f in fixture_files.items():
        check(ack['facts'][str(q)]==dict(signature9=f['signature'],sha256=f['sha256']),'hardlink-child-original-leaf')
    check(fixture_files[fixture/'source'/'source.bin']['signature']==report['transitions'][-1]['source9'] and fixture_files[fixture/'source'/'source.bin']['sha256']==report['source_sha256']
          and fixture_files[fixture/'target'/'foreign.bin']['signature']==report['foreign_original9'],'hardlink-kernel-original-leaves')
    for name in ('stage-intent.json','collision-intent.json','retire-intent.json','restore-intent.json','unstage-intent.json','result.json'):
        body,original_journal=read(fixture/name,ack['facts'][str(fixture/name)]['sha256'])
        check(original_journal['signature']==ack['facts'][str(fixture/name)]['signature9'],'journal-original-child-CAS')
        emit('kernel-'+name,dict(original_child_ref=dict(path=str(fixture/name),**ack['facts'][str(fixture/name)]),body=body,publication_authority=False))
    fixture_stamp = list(ack["root9"])
    payload = dict(
        fixture_facts={str(p): f for p, f in fixture_files.items()},
        fixture_signature=fixture_stamp,
        fixture_directories=fixture_dirs,
        version=1,
        kind="owned-disposable-nfs-parent",
        probe_verified=False,
        final_ack_required=True,
        fixture=str(fixture),
        fixture_retained=True,
        container_id=child,
        container_retained_stopped=True,
        platform_supported=supported,
        report_sha256=rf["sha256"],
        same_process_held=True,
        actual_library_platform_verified=False,
        native_grant=False,
        publication_authority=False,
        future_mylar_destination_verified=False,
        writer_lifecycle_resume_authorized=False,
    )
    acceptance = emit("acceptance.json", payload)
    continuity()
    census = {p.name: stamp(p) for p in out.iterdir()}
    check(set(census) == {p.name for p in controls if p.parent == out}, "output-census")
    for p, f in fixture_files.items():
        check(fact(p) == f, "fixture-full-drift")
    check(stamp(fixture) == fixture_stamp, "fixture-root-drift")
    final_output = {p.name: stamp(p) for p in out.iterdir()}
    check(final_output == census, "final-output-census-drift")
    out_stamp = stamp(out)
    check(set(fixture.iterdir()) == {fixture/'source',fixture/'target'}|{q for q in fixture_files if q.parent==fixture}, 'final-fixture-census')
    check(
        ancestry([*controls, fixture, out, *roots]) == ancestors, "final-ancestor-drift"
    )
    terminal_result = dict(
        probe_verified=True,
        acceptance_sha256=controls[acceptance]["sha256"],
        platform_supported=supported,
        fixture_retained=True,
        container_retained_stopped=True,
        actual_library_platform_verified=False,
        native_grant=False,
        publication_authority=False,
        future_mylar_destination_verified=False,
        writer_lifecycle_resume_authorized=False,
    )

    file_items = tuple((str(p), tuple(f['signature'])) for p, f in {**controls, **fixture_files}.items()) + ((str(fixture), tuple(fixture_stamp)), (str(out), tuple(out_stamp))) + tuple((str(p), tuple(v)) for p, v in rootstates.items()) + tuple((str(fixture/name),tuple(v)) for name,v in fixture_dirs.items())
    node_items = tuple((str(p), tuple(v)) for p, v in ancestors.items())
    fixture_names = frozenset({'source','target'}|{p.name for p in fixture_files if p.parent==fixture})
    output_names = frozenset(census)
    if frozenset(os.listdir(fixture)) != fixture_names:raise Held('terminal-fixture-census')
    if frozenset(os.listdir(out)) != output_names:raise Held('terminal-output-census')
    for p, v in node_items:
        x = os.lstat(p)
        if (x.st_dev,x.st_ino,x.st_mode,x.st_uid,x.st_gid) != v:raise Held('terminal-ancestor')
    for p, v in file_items:
        x = os.lstat(p)
        if (x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode,x.st_uid,x.st_gid,x.st_nlink) != v:raise Held('terminal-leaf')
    return terminal_result


LIFECYCLE = None
LIFECYCLE_SHA = None
WRITER_ROOT = None
ACTIVE_TESTS = None
# Replaced with the frozen actual test-source digest after fixture completion.
ACTIVE_TESTS_SHA = None
ACTIVE_TEST_COUNT = None
EFFECTIVE_HELPER_SHA = None
EFFECTIVE_PARENT_SHA = None
WRITER_FIXTURE = None
CORE_PARENT = None
CORE_PARENT_SHA = None
CORE_TESTS = None
CORE_TESTS_SHA = None
JAR_SHA = None
KOMGA_COMMIT = None


def active_native_controls(ref, source_sha):
    if _COHORT is None:raise Held('explicit-current-source-cohort-required')
    if ref != _COHORT.receipt_ref:raise Held('selected-readiness-ref-conflict')
    if source_sha != _COHORT.parent_sha:raise Held('selected-parent-pin')
    return _COHORT.readiness()


def process_start(pid):
    check(type(pid) is int and pid > 0, 'process-pid')
    path = Path('/proc') / str(pid) / 'stat'
    raw = path.read_text()
    check(raw.split(' ', 1)[0] == str(pid), 'process-pid-binding')
    tail = raw.rsplit(')', 1)[1].split()
    check(len(tail) >= 20 and tail[19].isdigit(), 'process-start-field')
    return int(tail[19])


def validate_effective_nodes(report, roots):
    roles = {'config', 'database', 'tasks', 'index', 'fonts'}
    check(set(report['scopes']) == roles and set(report['scope_presence']) == roles,
          'effective-five-scopes')
    check(all(type(v) is bool and (v or role == 'fonts')
              for role, v in report['scope_presence'].items()), 'effective-required-presence')
    absent = report['optional_absent_scopes']
    check(type(absent) is dict, 'effective-optional-map')
    expected_absent = set()
    expected_present = set()
    for role, value in report['scopes'].items():
        p = canonical(value['host_path'])
        node = p if role in ('config', 'index', 'fonts') else p.parent
        check(any(node == root or node.is_relative_to(root) for root in roots), 'effective-scope-forbidden')
        if not report['scope_presence'][role]:
            expected_absent.add(str(p))
            check(not os.path.lexists(p) and str(p) in absent, 'effective-fonts-absence')
            proof = absent[str(p)]
            exact(proof, ('nearest_existing_ancestor', 'ancestor_identity'))
            parent = canonical(proof['nearest_existing_ancestor'])
            x = stamp(parent)
            check(parent == p.parent and stat.S_ISDIR(x[5])
                  and [x[i] for i in (0, 1, 5, 6, 7)] == proof['ancestor_identity'],
                  'effective-absent-parent-identity')
        else:
            expected_present.add(str(p))
            x = stamp(p)
            check([x[i] for i in (0, 1, 5, 6, 7)] == report['scope_identities'][str(p)],
                  'effective-scope-identity')
    check(set(absent) == expected_absent and set(report['scope_identities']) == expected_present,
          'effective-scope-proof-census')


def active_effective_controls(review, roots):
    exact(review, ('producer', 'parent_source', 'report', 'ack', 'runtime', 'acceptance', 'parent_ack'))
    check(review['producer']['sha256'] == EFFECTIVE_HELPER_SHA
          and review['parent_source']['sha256'] == EFFECTIVE_PARENT_SHA, 'independently-reviewed-effective-pins')
    controls = {}
    values = {}
    for role, ref in review.items():
        exact(ref, ('path', 'sha256'))
        p = canonical(ref['path'])
        if role in ('producer', 'parent_source'):
            controls[p] = fact(p, ref['sha256'], source=True)
        else:
            values[role], controls[p] = read(p, ref['sha256'])
    report, ack, runtime = values['report'], values['ack'], values['runtime']
    acceptance, parent_ack = values['acceptance'], values['parent_ack']
    check(parent_ack.get('scope_observation_verified') is True and parent_ack.get('same_process_verified') is True
          and parent_ack.get('acceptance_sha256') == review['acceptance']['sha256']
          and parent_ack.get('report_sha256') == review['report']['sha256']
          and all(parent_ack.get(k) is False for k in ('backup_verified', 'publication_acceptance', 'mutation_authority')),
          'effective-parent-root-final-ack')
    check(acceptance.get('kind') == 'accepted-komga-effective-scope'
          and acceptance.get('scope_observation_verified') is False and acceptance.get('final_ack_required') is True
          and acceptance.get('same_process_verified') is True
          and acceptance.get('report_sha256') == review['report']['sha256']
          and acceptance.get('source_sha256') == EFFECTIVE_PARENT_SHA
          and acceptance.get('helper_sha256') == EFFECTIVE_HELPER_SHA
          and all(acceptance.get(k) is False for k in ('backup_verified', 'publication_acceptance', 'mutation_authority')),
          'effective-parent-pending-receipt')
    check(ack.get('scope_observation_verified') is True
          and ack.get('report_sha256') == review['report']['sha256']
          and all(ack.get(k) is False for k in ('backup_verified', 'publication_acceptance', 'mutation_authority')),
          'effective-producer-final-ack')
    check(report.get('kind') == 'komga-effective-persistent-scope-observation'
          and report.get('source_sha256') == review['producer']['sha256']
          and report.get('runtime_sha256') == review['runtime']['sha256']
          and report.get('image') == KOMGA and report.get('jar_sha256') == JAR_SHA
          and report.get('source_commit') == KOMGA_COMMIT
          and report.get('scope_observation_verified') is False and report.get('final_ack_required') is True
          and report.get('unsupported_imports_observed') is False
          and report.get('all_library_settings_verified') is False
          and report.get('process_verified_by_parent') is False, 'effective-pending-report-contract')
    check(runtime.get('kind') == 'reviewed-komga-effective-scope-runtime'
          and runtime.get('jar_sha256') == JAR_SHA and runtime.get('source_commit') == KOMGA_COMMIT
          and runtime['container']['Id'] == report['container_id']
          and runtime['pid'] == report['pid'] and runtime['start_time'] == report['start_time'],
          'effective-runtime-bound')
    fresh_scope(runtime)
    validate_effective_nodes(report, roots)
    for rawpath, f in report['config_files'].items():
        p = canonical(rawpath)
        controls[p] = fact(p, f['sha256'], source=True)
        check(controls[p]['signature'] == f['signature9'], 'effective-config-binding')
    check(not any(os.path.lexists(p) for p in report['absent_config_files']), 'effective-config-still-absent')
    return controls, runtime, report


class RefuseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Held('library-query-redirect')


def fresh_libraries(query_plan, rows, controls, expected_roots):
    exact(query_plan, ('version', 'kind', 'configuration', 'expected_base_url'))
    check(query_plan['version'] == 1 and query_plan['kind'] == 'approved-active-komga-library-query', 'query-plan')
    ref = query_plan['configuration']
    exact(ref, ('path', 'sha256'))
    cfg, f = read(ref['path'], ref['sha256'])
    controls[canonical(ref['path'])] = f
    base, key = cfg['komga']['url'], cfg['komga']['api_key']
    u = urllib.parse.urlsplit(base)
    check(base == query_plan['expected_base_url'] and u.scheme in ('http', 'https')
          and u.netloc and not u.username and not u.password and not u.query and not u.fragment
          and type(key) is str and key and key != 'REPLACE_ME', 'private-query-configuration')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), RefuseRedirect())
    def get(route):
        check(route in ('/api/v2/users/me', '/api/v1/libraries'), 'only-library-get')
        request = urllib.request.Request(base.rstrip('/') + route, headers={'X-API-Key': key}, method='GET')
        with opener.open(request, timeout=30) as response:
            raw = response.read(8 * 1024**2 + 1)
        check(len(raw) <= 8 * 1024**2, 'library-json-bound')
        def pairs(items):
            value = {}
            for k, v in items:
                check(k not in value, 'duplicate-library-response-key')
                value[k] = v
            return value
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(Held('library-json-number')))
    user = get('/api/v2/users/me')
    check(type(user) is dict and {'id', 'roles', 'sharedAllLibraries', 'sharedLibrariesIds',
                                  'labelsAllow', 'labelsExclude', 'ageRestriction'} <= set(user)
          and 'ADMIN' in user.get('roles', []) and user.get('sharedAllLibraries') is True
          and user.get('sharedLibrariesIds') == [] and user.get('labelsAllow') == []
          and user.get('labelsExclude') == [] and user.get('ageRestriction') is None
          and type(user.get('id')) is str and user['id'], 'unrestricted-admin')
    libraries = get('/api/v1/libraries')
    check(type(libraries) is list and 1 <= len(libraries) <= 1000
          and libraries == get('/api/v1/libraries'), 'complete-stable-library-pair')
    required = {'id', 'root', 'scanOnStartup', 'scanInterval', 'emptyTrashAfterScan', 'convertToCbz',
                'repairExtensions', 'scanForceModifiedTime', 'scanDirectoryExclusions', 'unavailable'}
    check(all(type(v) is dict and required <= set(v) and type(v['id']) is str and v['id']
              and v['unavailable'] is False and type(v['scanInterval']) is str
              and type(v['scanDirectoryExclusions']) is list
              and all(type(v[k]) is bool for k in ('scanOnStartup', 'emptyTrashAfterScan', 'convertToCbz',
                                                 'repairExtensions', 'scanForceModifiedTime', 'unavailable'))
              for v in libraries)
          and len({v['id'] for v in libraries}) == len(libraries), 'library-full-dto')
    komga = next(r for r in rows if r['Name'] == '/komga')
    mapped = set()
    for value in libraries:
        raw = value['root']
        check(type(raw) is str and raw.startswith('/') and '..' not in Path(raw).parts
              and '\\' not in raw and '\0' not in raw and str(Path(raw)) == raw, 'library-root-encoding')
        matching = [m for m in komga['Mounts'] if Path(raw) == Path(m['Destination'])
                    or Path(raw).is_relative_to(Path(m['Destination']))]
        check(matching, 'mapped-library-root')
        best = max(len(Path(m['Destination']).parts) for m in matching)
        matching = [m for m in matching if len(Path(m['Destination']).parts) == best]
        check(len(matching) == 1 and matching[0]['Type'] in ('bind', 'volume'), 'unambiguous-library-mount')
        m = matching[0]
        actual = canonical(Path(m['Source']) / Path(raw).relative_to(m['Destination']))
        check(actual.is_dir() and any(actual == root or actual.is_relative_to(root) for root in expected_roots),
              'every-current-library-forbidden')
        mapped.add(str(actual))
    return {'principal_id': user['id'], 'libraries': libraries, 'mapped_roots': sorted(mapped)}


def lifecycle_module():
    raw, original = checked_buffer(LIFECYCLE, LIFECYCLE_SHA, source=True)
    spec = importlib.util.spec_from_file_location('active_nfs_lifecycle', LIFECYCLE)
    module = importlib.util.module_from_spec(spec)
    exec(compile(raw, str(LIFECYCLE), 'exec'), module.__dict__)
    check(fact(LIFECYCLE, LIFECYCLE_SHA, source=True)['sha256'] == LIFECYCLE_SHA,
          'lifecycle-source-drift')
    return module


def lease_profile(row, name, mounts, expected_status='created'):
    h, c, s = row['HostConfig'], row['Config'], row['State']
    check(row['Image'] == IMAGE and c['User'] == '1000:1000'
          and c['Labels'].get('com.homelab.nfs.lease') == name
          and s['Status'] == expected_status and s['Running'] is (expected_status == 'running')
          and all(s.get(k, False) is False for k in ('Paused', 'Restarting', 'Dead', 'OOMKilled'))
          and type(s['Pid']) is int and (s['Pid'] > 0 if expected_status == 'running' else s['Pid'] == 0),
          'lease-container-state')
    check(h['ReadonlyRootfs'] is True and h['Privileged'] is False
          and h['NetworkMode'] == 'none' and h['PidMode'] == '' and h['IpcMode'] == 'private'
          and not h.get('CapAdd') and h['CapDrop'] == ['ALL']
          and h['SecurityOpt'] == ['no-new-privileges'] and h['PidsLimit'] == 32
          and not h.get('Devices') and not h.get('DeviceRequests')
          and not h.get('Binds') and not h.get('Tmpfs') and not h.get('PortBindings')
          and h.get('RestartPolicy', {}).get('Name') in ('', 'no'), 'lease-isolation')
    check(len(row['Mounts']) == len(mounts) and all(m['Type'] == 'bind' for m in row['Mounts'])
          and sorted((m['Source'], m['Destination'], m['RW']) for m in row['Mounts']) == sorted(mounts),
          'lease-exact-mounts')
    check(re.fullmatch('[a-f0-9]{64}', row['Id']), 'lease-container-id')
    return row['Id']


class WriterLease:
    """No live-media mount/socket. The raw lock remains held across all phases."""
    def __init__(self, output, engine=subprocess.run, launcher=subprocess.Popen):
        self.engine, self.launcher = engine, launcher
        self.output = output
        self.token = uuid.uuid4().hex + uuid.uuid4().hex
        self.name = 'comic-nfs-lease-' + uuid.uuid4().hex
        self.process = None
        self.cid = None
        self.released = False
        self.running_identity = None
        self.records = {}
        self.identity = stamp(WRITER_ROOT)[:2]
        self.ancestors = ancestry([WRITER_ROOT, LIFECYCLE, output])
        self.before = {p: fact(p) for p in WRITER_ROOT.iterdir()}
        check('writer-v1.lock' in {p.name for p in self.before}
              and {p.name for p in self.before} <= {'writer-v1.lock', 'normalizer-v1.pending',
                                                   'tagger-v2.pending', 'release-v1.pending',
                                                   'publication-v1.json'}, 'lease-writer-namespace')

    def call(self, argv):
        r = self.engine(argv, capture_output=True, timeout=900, check=False)
        check(r.returncode == 0 and len(r.stdout) <= 1024**2 and len(r.stderr) <= 1024**2,
              'lease-engine-ack')
        return r.stdout

    def start(self):
        empty = self.output / 'lease-empty-config'
        empty.mkdir(mode=0o700)
        self.mounts = [(str(LIFECYCLE), str(LIFECYCLE), False),
                       (str(WRITER_ROOT), '/writer', True), (str(empty), '/config', False)]
        argv = DOCKER + ['create', '--name', self.name, '--user', '1000:1000', '--read-only',
                         '--network', 'none', '--ipc', 'private', '--cap-drop', 'ALL',
                         '--security-opt', 'no-new-privileges', '--pids-limit', '32',
                         '--memory', '64m', '--cpus', '0.25', '--label', 'com.homelab.nfs.lease=' + self.name,
                         '--env', 'PYTHONDONTWRITEBYTECODE=1', '--interactive', '--entrypoint', '/lsiopy/bin/python3']
        for src, dst, rw in self.mounts:
            check(',' not in src and ',' not in dst, 'lease-mount-encoding')
            argv += ['--mount', 'type=bind,source=' + src + ',target=' + dst + ('' if rw else ',readonly')]
        command = [str(LIFECYCLE), '--lease-child', '--writer-source', '/app/mylar3/mylar/media_writer.py', '--writer-sha256', WRITER_SHA,
                   '--writer-root', '/writer', '--token', self.token]
        argv += [IMAGE] + command
        self.records[self.output / 'lease-intent.json'] = write(
            self.output / 'lease-intent.json', {'argv': argv, 'automatic_retry': False,
                                               'native_grant': False, 'publication_authority': False})
        self.call(argv)
        row = json.loads(self.call(DOCKER + ['inspect', self.name]))[0]
        check(row['Config']['Entrypoint'] == ['/lsiopy/bin/python3']
              and row['Config']['Cmd'] == command, 'lease-exact-command')
        self.cid = lease_profile(row, self.name, self.mounts)
        self.records[self.output / 'lease-created.json'] = write(
            self.output / 'lease-created.json', {'container_id': self.cid, 'name': self.name,
                                                'writer_identity': self.identity, 'profile_verified': True})
        self.process = self.launcher(DOCKER + ['start', '--attach', '--interactive', self.cid],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.receive('held')
        self.profile()

    def profile(self):
        check(self.process is not None and self.process.poll() is None, 'lease-interrupted')
        row = json.loads(self.call(DOCKER + ['inspect', self.cid]))[0]
        check(lease_profile(row, self.name, self.mounts, 'running') == self.cid, 'lease-identity-drift')
        current = (row['State']['Pid'], row['State']['StartedAt'])
        if self.running_identity is None:
            self.running_identity = current
        check(current == self.running_identity, 'lease-process-restarted')
        for p, f in self.before.items():
            check(fact(p) == f, 'lease-marker-drift')
        check(set(WRITER_ROOT.iterdir()) == set(self.before) and stamp(WRITER_ROOT)[:2] == self.identity,
              'lease-root-drift')
        check(ancestry([WRITER_ROOT, LIFECYCLE, self.output]) == self.ancestors, 'lease-ancestor-drift')

    def receive(self, expected):
        selector = selectors.DefaultSelector()
        try:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            check(selector.select(900), 'lease-ack-timeout')
            raw = self.process.stdout.readline(4097)
            check(0 < len(raw) <= 4096, 'lease-ack-bound')
        finally:
            selector.close()
        ack = json.loads(raw)
        check(set(ack) == {'version', 'kind', 'token', 'state', 'writer_identity', 'source_sha256',
                           'markers_unchanged', 'native_grant', 'publication_authority'}
              and ack['version'] == 1 and ack['kind'] == 'owned-nfs-existing-writer-lease'
              and ack['token'] == self.token and ack['state'] == expected
              and ack['writer_identity'] == self.identity
              and ack['source_sha256'] == WRITER_SHA
              and ack['markers_unchanged'] is True and ack['native_grant'] is False
              and ack['publication_authority'] is False, 'lease-unknown-ack')

    def send(self, action, absent):
        self.profile()
        raw = encode({'token': self.token, 'action': action, 'owned_absence_verified': absent}) + b'\n'
        check(self.process.stdin.write(raw) == len(raw), 'lease-channel-write')
        self.process.stdin.flush()

    def pulse(self):
        self.send('pulse', False)
        self.receive('held')
        self.profile()

    def release_after_absence(self, owned_paths, *, original_files=(), original_nodes=()):
        self.pulse()
        raw = encode({'token': self.token, 'action': 'release', 'owned_absence_verified': True}) + b'\n'
        self.profile()
        fd = self.process.stdin.fileno()
        self.process.stdin.flush()
        # Finish callbacks before complete original proof and direct release.
        for p,v in original_nodes:
            x=os.lstat(p)
            if (x.st_dev,x.st_ino,x.st_mode,x.st_uid,x.st_gid)!=v:raise Held('lease-release-original-ancestor')
        for p,v in original_files:
            x=os.lstat(p)
            if (x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode,x.st_uid,x.st_gid,x.st_nlink)!=v:raise Held('lease-release-original-file')
        for p in owned_paths:
            try:
                os.lstat(p)
            except FileNotFoundError:
                continue
            raise Held('lease-release-owned-path-present')
        check(os.write(fd, raw) == len(raw), 'lease-release-channel-write')
        self.receive('release-reviewed')
        check(self.process.wait(timeout=30) == 0, 'lease-release-exit')
        stopped = json.loads(self.call(DOCKER + ['inspect', self.cid]))[0]
        check(lease_profile(stopped, self.name, self.mounts, 'exited') == self.cid
              and stopped['State']['ExitCode'] == 0, 'lease-stopped-profile')
        self.records[self.output / 'lease-stopped.json'] = write(
            self.output / 'lease-stopped.json', {'container_id': self.cid, 'exit_code': 0,
                                               'native_grant': False, 'publication_authority': False})
        for p in owned_paths:
            try:
                os.lstat(p)
            except FileNotFoundError:
                continue
            raise Held('terminal-post-release-owned-path-present')
        self.released = True


class SourceCohort:
    """Original-bound source/test evidence, never operational permission."""
    def __init__(self, ref):
        exact(ref, ('path','sha256'))
        self._nodes={}
        self._initial_files={}
        self._capture_originals((Path(ref['path']),Path(__file__).absolute()))
        value, original = read(ref['path'],ref['sha256'])
        self._check_original_file(ref['path'],original)
        exact(value, ('version','kind','images','sources','writer_root','writer_sha256',
                      'native_map_count','selected_module_count','parent','receipt','logs',
                      'effective_jar_sha256','effective_commit'))
        check(type(value['version']) is int and value['version']==1 and value['kind']=='approved-disposable-nfs-current-source-cohort','source-cohort-schema')
        exact(value['images'],('native','selected','reader','worker'))
        check(all(type(v) is str and re.fullmatch('sha256:[a-f0-9]{64}',v) for v in value['images'].values()),'source-image-pins')
        roles=('probe','hardlink_kernel','scope_projection','lifecycle','readiness','readiness_input','parity','native_map','selected_sdk','writer','tests','effective_helper','effective_parent','core_parent','core_tests','writer_fixture')
        exact(value['sources'],roles)
        self._facts={canonical(ref['path']):original}
        self.images=tuple((k,value['images'][k]) for k in ('native','selected','reader','worker'))
        self.sources={}
        # Admit the complete decoded source/receipt/writer namespace BEFORE
        # the first expensive source fact, JSON read, copy or log callback.
        source_items=[]
        for role in roles:
            item=value['sources'][role];exact(item,('path','sha256'))
            source_items.append((role,str(item['path']),str(item['sha256'])))
        source_items=tuple(source_items)
        exact(value['parent'],('path','sha256'));exact(value['receipt'],('path','sha256'))
        exact(value['logs'],('stdout','stderr'))
        log_items=[]
        for role in ('stdout','stderr'):
            item=value['logs'][role];exact(item,('path','sha256'))
            log_items.append((role,str(item['path']),str(item['sha256'])))
        log_items=tuple(log_items)
        self._capture_originals(tuple(Path(path) for _,path,_ in (*source_items,*log_items))+(Path(value['parent']['path']),Path(value['receipt']['path']),Path(value['writer_root'])))
        receipt_ref=dict(value['receipt'])
        receipt,receipt_fact=read(receipt_ref['path'],receipt_ref['sha256'])
        self._check_original_file(receipt_ref['path'],receipt_fact)
        for role,path,sha in log_items:
            if receipt[role]!=dict(path=path,sha256=sha):raise Held('cohort-original-log-ref')
        for role,original_path,original_sha in source_items:
            item=dict(path=original_path,sha256=original_sha)
            path=canonical(original_path);f=fact(path,original_sha,source=role not in ('native_map','selected_sdk','readiness_input'))
            self._check_original_file(path,f)
            if path in self._facts and self._facts[path]!=f:raise Held('cohort-source-conflict')
            self._facts[path]=f;self.sources[role]=(path,item['sha256'])
            for node,v in ancestry([path]).items():
                if node in self._nodes and tuple(self._nodes[node])!=tuple(v):raise Held('cohort-ancestor-conflict')
                self._nodes[node]=tuple(v)
        for node,v in ancestry([Path(ref['path'])]).items():
            if node in self._nodes and tuple(self._nodes[node])!=tuple(v):raise Held('cohort-ancestor-conflict')
            self._nodes[node]=tuple(v)
        exact(value['parent'],('path','sha256'))
        self.parent_sha=value['parent']['sha256']
        check(canonical(value['parent']['path'])==Path(__file__).absolute(),'cohort-parent-path')
        self._facts[Path(__file__).absolute()]=fact(__file__,self.parent_sha,source=True)
        self._check_original_file(__file__,self._facts[Path(__file__).absolute()])
        exact(value['receipt'],('path','sha256'));self.receipt_ref=dict(value['receipt'])
        self._facts[canonical(self.receipt_ref['path'])]=receipt_fact
        check(receipt.get('kind')=='owned-nfs-current-source-fixture-readiness'
              and receipt.get('images')==dict(self.images) and receipt.get('parent_sha256')==self.parent_sha
              and receipt.get('source_pins')=={role:sha for role,(_,sha) in self.sources.items()}
              and receipt.get('exit_code')==0 and receipt.get('zero_skips') is True
              and type(receipt.get('count')) is int and receipt['count']>0
              and all(receipt.get(k) is False for k in ('actual_nfs_verified','native_grant','publication_authority','library_support_verified')),'current-source-readiness')
        for role,path,sha in log_items:
            f=fact(path,sha);self._check_original_file(path,f)
            self._facts[canonical(path)]=f
        check(type(value['native_map_count']) is int and value['native_map_count']>0
              and type(value['selected_module_count']) is int and value['selected_module_count']==25,'explicit-distinct-sdk-counts')
        native,_=read(*self.sources['native_map'])
        selected,_=read(*self.sources['selected_sdk'])
        check(type(native) is dict and len(native)==value['native_map_count']
              and type(selected.get('modules')) is dict and len(selected['modules'])==value['selected_module_count']
              and selected.get('parent_sha256') is None,'distinct-original-sdk-maps')
        check(self.sources['scope_projection'][1]==SCOPE_SHA,'checked-native-scope-projection')
        check(self.sources['hardlink_kernel'][1]==HARDLINK_KERNEL_SHA,'checked-hardlink-kernel-source')
        check(self.sources['readiness'][1]==CHECKED_PROBE_SHA,'checked-native-probe-source')
        request,_=read(*self.sources['readiness_input'])
        exact(request,('version','nonce','source_sha256','seconds','module_pins','scope_source'))
        check(request['version']==1 and request['source_sha256']==CHECKED_PROBE_SHA
              and type(request['nonce']) is str and re.fullmatch('[a-f0-9]{64}',request['nonce'])
              and type(request['seconds']) is int and 1<=request['seconds']<=120,'checked-native-probe-input')
        check(value['writer_sha256']==self.sources['writer'][1],'writer-source-join')
        self.writer_root=canonical(value['writer_root'])
        check(self.writer_root.is_dir(),'existing-writer-root')
        self.settings=tuple((k,value[k]) for k in ('writer_sha256','native_map_count','selected_module_count','effective_jar_sha256','effective_commit'))
        for path in (*self._facts,self.writer_root):
            for node,v in ancestry([path]).items():
                if node in self._nodes and tuple(self._nodes[node])!=tuple(v):raise Held('cohort-ancestor-conflict')
                self._nodes[node]=tuple(v)
        self._file_items=tuple((str(p),tuple(f['signature'])) for p,f in self._facts.items())
        self._directory_items=tuple((p,v) for p,v in self._initial_files.items() if stat.S_ISDIR(v[5]))
        self._node_items=tuple((str(p),tuple(v)) for p,v in self._nodes.items())
        self.close()

    def _capture_originals(self,paths):
        for p in paths:
            if not p.is_absolute() or '..' in p.parts:raise Held('cohort-original-path')
            x=os.lstat(p)
            v=(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode,x.st_uid,x.st_gid,x.st_nlink)
            old=self._initial_files.setdefault(str(p),v)
            if old!=v:raise Held('cohort-original-file-conflict')
            for q in ([p,*p.parents] if stat.S_ISDIR(x.st_mode) else p.parents):
                z=os.lstat(q)
                if not stat.S_ISDIR(z.st_mode):raise Held('cohort-original-ancestor-type')
                node=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
                previous=self._nodes.setdefault(str(q),node)
                if tuple(previous)!=node:raise Held('cohort-original-ancestor-conflict')

    def _check_original_file(self,path,fact):
        if tuple(fact['signature'])!=self._initial_files[str(path)]:raise Held('cohort-original-file-CAS')

    def close(self):
        for p,v in self._node_items:
            x=os.lstat(p)
            if (x.st_dev,x.st_ino,x.st_mode,x.st_uid,x.st_gid)!=v:raise Held('cohort-ancestor-CAS')
        for p,v in (*self._file_items,*self._directory_items):
            x=os.lstat(p)
            if (x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode,x.st_uid,x.st_gid,x.st_nlink)!=v:raise Held('cohort-source-CAS')

    def facts(self):
        result={Path(p):dict(signature=list(v),sha256=self._facts[Path(p)]['sha256']) for p,v in self._file_items}
        self.close();return result

    def readiness(self):
        return self.facts()


def bind_cohort(ref):
    global _COHORT, IMAGE, NATIVE_IMAGE, KOMGA, WORKER, WRITER_ROOT, WRITER_SHA, NATIVE_MAP_COUNT
    if _COHORT is not None:raise Held('source-cohort-no-rebind')
    cohort=SourceCohort(ref)
    images=dict(cohort.images);settings=dict(cohort.settings)
    IMAGE=images['selected'];NATIVE_IMAGE=images['native'];KOMGA=images['reader'];WORKER=images['worker']
    WRITER_ROOT=cohort.writer_root;WRITER_SHA=settings['writer_sha256'];NATIVE_MAP_COUNT=settings['native_map_count']
    roles={'probe':'PROBE','hardlink_kernel':'HARDLINK_KERNEL','lifecycle':'LIFECYCLE','readiness':'READY','readiness_input':'READY_INPUT','parity':'PARITY','native_map':'MAP','selected_sdk':'SELECTED_SDK','tests':'ACTIVE_TESTS','core_parent':'CORE_PARENT','core_tests':'CORE_TESTS','writer_fixture':'WRITER_FIXTURE'}
    for role,name in roles.items():
        path,sha=cohort.sources[role];globals()[name]=path;globals()[name+'_SHA']=sha
    globals()['EFFECTIVE_HELPER_SHA']=cohort.sources['effective_helper'][1]
    globals()['EFFECTIVE_PARENT_SHA']=cohort.sources['effective_parent'][1]
    globals()['JAR_SHA']=settings['effective_jar_sha256'];globals()['KOMGA_COMMIT']=settings['effective_commit']
    NATIVE_RECEIPT=canonical(cohort.receipt_ref['path'])
    globals()['NATIVE_RECEIPT']=NATIVE_RECEIPT;globals()['NATIVE_RECEIPT_SHA']=cohort.receipt_ref['sha256']
    path,sha=cohort.sources['scope_projection'];raw,_=checked_buffer(path,sha,source=True)
    scope_module=__import__('types').ModuleType('checked_nfs_native_projection');scope_module.__file__=str(path);exec(compile(raw,str(path),'exec'),scope_module.__dict__)
    globals()['_NATIVE_PROJECTOR']=scope_module.observed_native
    cohort.close();_COHORT=cohort;return cohort


_ACTIVE_KEY=object()
_ACTIVE_SEALS=weakref.WeakKeyDictionary()

class ActiveNFSCanaryObservation:
    """Owning completed canary facts only; no action lock or publication right."""
    __slots__=('files','nodes','names','absent','result','rows','native','mount','device','_observe','thread','__weakref__')
    def __init__(self,key,files,nodes,names,absent,result,rows,native,mount,device,observe):
        if key is not _ACTIVE_KEY:raise Held('active-owning-invocation-required')
        self.files=tuple(files);self.nodes=tuple(nodes);self.names=tuple(names);self.absent=tuple(absent)
        self.result=json.loads(encode(result));self.rows=json.loads(encode(rows));self.native=json.loads(encode(native))
        self.mount=json.loads(encode(mount));self.device=device;self._observe=observe;self.thread=threading.get_ident()
        _ACTIVE_SEALS[self]=self._seal()
    def _seal(self):
        return encode(dict(files=self.files,nodes=self.nodes,names=[(p,sorted(v)) for p,v in self.names],absent=self.absent,
                           result=self.result,rows=self.rows,native=self.native,mount=self.mount,device=self.device,
                           thread=self.thread,observe=id(self._observe)))
    def close(self):
        files=tuple(self.files);nodes=tuple(self.nodes);names=tuple(self.names);absent=tuple(self.absent)
        admitted=_ACTIVE_SEALS.get(self)
        if self.thread!=threading.get_ident() or admitted is None or self._seal()!=admitted:raise Held('active-factual-lifetime')
        for p,v in names:
            if frozenset(os.listdir(p))!=v:raise Held('active-factual-census')
        for p,v in nodes:
            z=os.lstat(p)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('active-factual-ancestor')
        for p,v in files:
            z=os.lstat(p)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('active-factual-file')
        for p in absent:
            try:os.lstat(p)
            except FileNotFoundError:continue
            raise Held('active-factual-owned-path-returned')
    def current(self,*,stopped):
        self.close();rows,native,mount,device=self._observe()
        if native!=self.native or mount!=self.mount or device!=self.device:raise Held('active-factual-native-export-drift')
        original={r['Name']:r for r in self.rows};current={r['Name']:r for r in rows}
        if set(original)!=set(current):raise Held('active-factual-runtime-set')
        for name in original:
            keys=('Id','Image','Mounts','Config','HostConfig','NetworkSettings')
            if any(current[name].get(k)!=original[name].get(k) for k in keys):raise Held('active-factual-static-drift')
        state=current['/komga']['State'];old=original['/komga']['State']
        if stopped:
            if not (state['Status']=='exited' and state['Running'] is False and type(state['Pid']) is int and state['Pid']==0 and state['StartedAt']==old['StartedAt']
                    and all(state.get(k) is False for k in ('Paused','Restarting','Dead','OOMKilled'))):raise Held('active-factual-not-stopped')
        elif {k:v for k,v in state.items() if k!='Health'}!={k:v for k,v in old.items() if k!='Health'}:raise Held('active-factual-reader-incarnation')
        result=json.loads(encode(rows));self.close();return result
    @property
    def binding(self):
        result=json.loads(encode(self.result));self.close();return result

def _execute_factual(a, engine=subprocess.run, lease_type=WriterLease):
    if not a.execute:
        return dict(executable=False, native_grant=False, publication_authority=False, actual_library_platform_verified=False)
    original_input_nodes = ancestry([Path(a.input),Path(__file__)])
    preliminary, preliminary_fact = read(a.input, a.input_sha256)
    cohort = bind_cohort(preliminary.get('source_cohort'))
    cohort.close()
    check(os.geteuid() == 1000, 'caller-uid')
    os.umask(0o077)
    initial_ancestors = ancestry([Path(__file__), Path(a.input), LIFECYCLE, ACTIVE_TESTS,
                                 CORE_PARENT, CORE_TESTS, WRITER_FIXTURE, READY, PARITY, MAP, NATIVE_RECEIPT])
    for p,v in original_input_nodes.items():
        if initial_ancestors.get(p)!=v:raise Held('source-cohort-initial-ancestor-drift')
    outer, of = read(a.input, a.input_sha256)
    if of != preliminary_fact:raise Held('source-cohort-input-drift')
    exact(outer, ('version', 'kind', 'active_scope', 'parent_admission', 'probe_plan', 'operation_output',
                  'native_controls', 'effective_observer_review', 'source_cohort'))
    check(outer['version'] == 1 and outer['kind'] == 'approved-active-nfs-owned-lifecycle', 'active-outer-plan')
    known = [Path(__file__), Path(a.input), LIFECYCLE, ACTIVE_TESTS, CORE_PARENT, CORE_TESTS,
             WRITER_FIXTURE, READY, PARITY, MAP, NATIVE_RECEIPT, Path(outer['active_scope']['path'])]
    entry = ancestry(known)
    check(all(entry.get(p) == v for p, v in initial_ancestors.items()), 'first-input-ancestor-drift')
    scope, sf = read(outer['active_scope']['path'], outer['active_scope']['sha256'])
    check(scope.get('future_mylar_destination_verified') is False
          and scope.get('future_mylar_destination') is None
          and scope.get('writer_lifecycle_resume_authorized') is False, 'unknown-future-no-resume-grant')
    own = fact(__file__, a.source_sha256, source=True)
    helper = fact(LIFECYCLE, LIFECYCLE_SHA, source=True)
    # Default-off remains truthful while the independent observer is held.
    if not a.execute:
        return {'executable': False, 'active_scope_dependency_required': True,
                'future_mylar_destination_verified': False, 'native_grant': False,
                'publication_authority': False, 'writer_lifecycle_resume_authorized': False}
    check(outer['native_controls'] is not None and outer['effective_observer_review'] is not None,
          'explicit-actual-native-and-reviewed-effective-evidence-required')
    try:
        return _run_owned_lifecycle(a, outer, of, scope, sf, own, helper, engine, lease_type, entry)
    except ValueError as error:
        raise Held(str(error)) from None


def execute(a,engine=subprocess.run,lease_type=WriterLease):
    result=_execute_factual(a,engine,lease_type)
    return result.binding if type(result) is ActiveNFSCanaryObservation else result

def run_active_factual(a,engine=subprocess.run):
    check(a.execute is True,'active-factual-execute-required')
    result=_execute_factual(a,engine,WriterLease)
    check(type(result) is ActiveNFSCanaryObservation,'active-factual-owning-result')
    result.close();return result

def _run_owned_lifecycle(a, outer, of, scope, sf, own, helper, engine, lease_type, entry):
    """Checked operational adapter. Missing actual proof refuses before writes."""
    module = lifecycle_module()
    exact(scope, ('version', 'kind', 'approved_disposable_diagnostic', 'observed',
                  'current_active_scanner_publication_paths_reviewed', 'future_mylar_destination_verified',
                  'future_mylar_destination', 'writer_lifecycle_resume_authorized', 'forbidden_roots', 'sources'))
    check(type(scope['version']) is int and scope['version'] == 2
          and scope['kind'] == 'root-reviewed-nfs-active-disposable-scope'
          and scope['approved_disposable_diagnostic'] is True
          and scope['current_active_scanner_publication_paths_reviewed'] is True
          and scope['future_mylar_destination_verified'] is False and scope['future_mylar_destination'] is None
          and scope['writer_lifecycle_resume_authorized'] is False, 'exact-active-scope-admission')
    check(type(scope['forbidden_roots']) is list and 1 <= len(scope['forbidden_roots']) <= 32
          and len(set(scope['forbidden_roots'])) == len(scope['forbidden_roots']), 'active-root-census')
    exact(scope['sources'], ('current_runtime_bracket', 'current_mylar_hold', 'current_worker_created',
                             'current_komga_libraries', 'current_komga_effective_scope',
                             'protected_catalog_cache_recovery_scope', 'continuous_raw_writer_lease'))
    roots = [canonical(p) for p in scope['forbidden_roots']]
    check(all(p.is_dir() for p in roots), 'all-live-media-roots-protected')
    output = canonical(outer['operation_output'])
    private_parent(output.parent)
    check(not os.path.lexists(output) and outside(output, roots), 'new-operation-output')
    discovered = ancestry([Path(a.input), Path(__file__), LIFECYCLE, output, *roots,
                           Path(outer['parent_admission']['path']),
                           *[Path(ref['path']) for ref in scope['sources'].values()]])
    check(all(discovered.get(p) == v for p, v in entry.items() if p in discovered), 'scope-input-ancestor-drift')
    admission = {**entry, **discovered}
    rootstates = {r: stamp(r) for r in roots}
    controls = {**_COHORT.facts(), Path(a.input): of, canonical(outer['active_scope']['path']): sf,
                Path(__file__): own, LIFECYCLE: helper}
    for ref in scope['sources'].values():
        controls[canonical(ref['path'])] = fact(ref['path'], ref['sha256'])
    controls.update(active_native_controls(outer['native_controls'], a.source_sha256))
    effective_controls, runtime, report = active_effective_controls(outer['effective_observer_review'], roots)
    controls.update(effective_controls)
    effective_absent = tuple(Path(p) for p in report.get('optional_absent_scopes', {}))
    effective_absent_parents = {canonical(p.parent): stamp(canonical(p.parent)) for p in effective_absent}
    controls.update(native_gate())
    controls[READY] = fact(READY, READY_SHA, source=True)
    controls[PARITY] = fact(PARITY, PARITY_SHA, source=True)
    controls[MAP] = fact(MAP, MAP_SHA)
    check(scope['sources']['current_komga_effective_scope'] == outer['effective_observer_review']['report'],
          'exact-effective-scope-source')
    query_plan, _ = read(scope['sources']['current_komga_libraries']['path'],
                         scope['sources']['current_komga_libraries']['sha256'])
    protected, _ = read(scope['sources']['protected_catalog_cache_recovery_scope']['path'],
                        scope['sources']['protected_catalog_cache_recovery_scope']['sha256'])
    check(protected.get('kind') == 'reviewed-nfs-protected-catalog-cache-recovery-scope'
          and type(protected.get('roots')) is list and protected['roots']
          and all(canonical(p) in roots for p in protected['roots']), 'complete-known-protected-roots')
    fresh_scope(scope)

    def call(argv, data=None):
        r = engine(argv, input=data, capture_output=True, timeout=900, check=False)
        check(r.returncode == 0 and len(r.stdout) <= 8 * 1024**2 and len(r.stderr) <= 4 * 1024**2,
              'active-observer-engine-ack')
        return r.stdout

    active_lease = None
    def observe_active():
        rows = json.loads(call(DOCKER + ['inspect', 'mylar3', 'komga-comic-normalizer-1', 'komga']))
        mapping = live_mapping(rows, roots)
        native = next(row for row in rows if row['Name'] == '/mylar3')
        mounts = [m for m in native['Mounts'] if m['Destination'] == '/config']
        check(len(mounts) == 1 and mounts[0]['Type'] in ('bind', 'volume') and mounts[0]['RW'] is True,
              'same-actual-native-config-writer-mapping')
        reader = next(row for row in rows if row['Name'] == '/komga')
        check(reader['Id'] == report['container_id'] and reader['State']['Pid'] == report['pid']
              and process_start(reader['State']['Pid']) == report['start_time']
              and all(reader[k] == runtime['container'][k] for k in ('Config', 'HostConfig', 'Mounts', 'NetworkSettings')),
              'same-current-effective-process-profile')
        health = fresh_native(call, next(r["Id"] for r in rows if r["Name"]=="/mylar3"))
        configured_writer_mapping(native['Mounts'],health['config'],WRITER_ROOT)
        publication = health['publication']
        if active_lease is None:
            check(publication['state'] == 'held' and publication['reason'] == 'startup-restart-required'
                  and publication['census']['revision'] == 13 and len(publication['census']['keys']) == 13,
                  'current-held-census')
        else:
            active_lease.pulse()
            check(publication['state'] == 'held' and publication['reason'] == 'writer-busy'
                  and publication['census'] is None, 'current-exclusive-writer-held')
        parity = json.loads(call(DOCKER + ['exec', '-i', '--user', '1000', native['Id'],
                                          '/lsiopy/bin/python3', '-'], PARITY.read_bytes()))
        check(parity == read(MAP, MAP_SHA)[0] and len(parity) == NATIVE_MAP_COUNT, 'current-native-loaded-parity')
        return {'mapping': mapping, 'publication': publication, 'native_process':health['process'], 'native_config':health['config']}, rows

    initial, rows = observe_active()
    def same_active(observed):
        return observed['mapping'] == initial['mapping'] and observed['native_process']==initial['native_process'] and observed['native_config']==initial['native_config'] and (
            observed['publication'] == initial['publication'] if active_lease is None else
            observed['publication']['state'] == 'held'
            and observed['publication']['reason'] == 'writer-busy'
            and observed['publication']['census'] is None)
    libraries = fresh_libraries(query_plan, rows, controls, roots)
    check(same_active(observe_active()[0]), 'active-library-query-bracket')
    ancestors = ancestry([*controls, output, *roots])
    check(all(ancestors.get(p) == v for p, v in admission.items() if p in ancestors), 'active-evidence-ancestor-drift')
    ancestors = {**admission, **ancestors}
    output.mkdir(mode=0o700)
    ancestors.update(ancestry([*controls, output / 'derived-probe-plan.json', *roots]))
    def emit(name, value):
        p = output / name
        controls[p] = write(p, value)
        return p
    emit('active-preflight.json', {'current_runtime': initial, 'future_mylar_destination_verified': False,
                                  'writer_lifecycle_resume_authorized': False})
    emit('library-settings.json', libraries)
    lease = lease_type(output, engine)
    lease.start()
    active_lease = lease
    controls.update(getattr(lease, 'records', {}))
    lease.pulse()
    check(same_active(observe_active()[0]), 'pre-staging-held-bracket')
    fresh_scope(scope)

    def observe_mount(path):
        r = engine(['findmnt', '--json', '--target', str(path), '--output',
                    'SOURCE,TARGET,FSTYPE,FSROOT,OPTIONS,MAJ:MIN'], capture_output=True, timeout=30, check=False)
        check(r.returncode == 0, 'staging-findmnt')
        return mount_identity(json.loads(r.stdout))

    core = dict(outer['probe_plan'])
    check(canonical(core['library_root']) == canonical(next(m['source'] for m in initial['mapping']['media_mounts'] if m['destination']=='/data/comics'))
          and core['expected_device'] == outer['parent_admission']['expected_device']
          and stamp(canonical(core['library_root']))[0] == core['expected_device']
          and core['mount_identity'] == outer['parent_admission']['mount_identity']
          and observe_mount(core['library_root']) == core['mount_identity'], 'precreation-same-actual-library-nfs')
    check(not output.is_relative_to(canonical(core['mount_identity']['target'])), 'metadata-output-outside-nfs-target')
    parent = module.admit_parent(outer['parent_admission'], roots, lease, observe_mount)
    admitted_parent=(str(parent['path']),tuple(parent['signature']),tuple(parent['grandparent_identity']),tuple(parent['grandparent_node5']))
    admitted_grandparent=Path(admitted_parent[0]).parent
    check(admitted_grandparent not in ancestors or tuple(ancestors[admitted_grandparent])==admitted_parent[3],'original-grandparent-conflict')
    ancestors[admitted_grandparent]=admitted_parent[3]
    emit('staging-record.json', {'parent': parent, 'native_grant': False, 'publication_authority': False})
    check(core['fixture_parent'] == parent['path'] and core['fixture_parent_signature'] is None
          and core['scope'] == outer['active_scope'] and core['output_root'] == str(output / 'probe'),
          'derived-probe-exact-parent')
    core['fixture_parent_signature'] = parent['signature']
    derived = output / 'derived-probe-plan.json'
    controls[derived] = write(derived, core)
    core_args = argparse.Namespace(input=str(derived), input_sha256=controls[derived]['sha256'],
                                   source_sha256=a.source_sha256, execute=True)
    lease.pulse()
    result = probe_existing_parent(core_args, engine, lease)
    check(result['probe_verified'] is True and result['fixture_retained'] is True, 'owned-probe-verified')
    lease.pulse()
    check(same_active(observe_active()[0]), 'post-probe-active-bracket')
    check(fresh_libraries(query_plan, observe_active()[1], controls, roots) == libraries,
          'post-probe-library-scopes-unchanged')
    fixture = canonical(parent['path']) / core['fixture_name']
    accepted, af = read(output / 'probe' / 'acceptance.json', result['acceptance_sha256'])
    controls[output / 'probe' / 'acceptance.json'] = af
    probe_output = output / 'probe'
    private_parent(probe_output)
    probe_census = set(os.listdir(probe_output))
    for p in probe_output.iterdir():
        controls[p] = fact(p)
    new_ancestors = ancestry([*controls, output, *roots])
    check(all(new_ancestors.get(p) == v for p, v in ancestors.items() if p in new_ancestors),
          'owned-output-ancestor-drift')
    ancestors = {**ancestors, **new_ancestors}
    check(accepted['fixture'] == str(fixture), 'accepted-own-fixture')
    fixture_sig = accepted['fixture_signature']
    ff = {canonical(p).relative_to(fixture).as_posix():f for p,f in accepted['fixture_facts'].items()}
    check(all(canonical(p).is_relative_to(fixture) for p in accepted['fixture_facts']),'accepted-hardlink-leaf-parent')
    # Original stopped child was verified by the core, never a caller bypass.
    original_parent=dict(path=admitted_parent[0],signature=list(admitted_parent[1]),grandparent_identity=list(admitted_parent[2]),grandparent_node5=list(admitted_parent[3]))
    cleaned = module.cleanup_hardlink_owned(original_parent, {'path':str(fixture),'signature':fixture_sig},
                                            ff,accepted['fixture_directories'],roots,lease)
    check(cleaned['owned_fixture_absence_verified'] is True, 'owned-cleanup-required')
    emit('cleanup-result.json', cleaned)
    check(same_active(observe_active()[0]), 'post-cleanup-active-bracket')
    release_files = tuple((str(p),tuple(f['signature'])) for p,f in controls.items()) + tuple((str(p),tuple(v)) for p,v in rootstates.items())
    release_nodes = tuple((str(p),tuple(v)) for p,v in ancestors.items())
    for p, f in controls.items():
        check(fact(p, source=p in (Path(__file__), LIFECYCLE) or stat.S_IMODE(f['signature'][5]) == 0o644) == f,
              'active-source-closure')
    current_ancestors = ancestry([*controls, output, *roots])
    check(all(ancestors.get(p) == v for p, v in current_ancestors.items()), 'active-ancestor-closure')
    for p, s in rootstates.items():
        check(stamp(p) == s, 'active-root-closure')
    lease.release_after_absence((fixture, canonical(parent['path'])), original_files=release_files, original_nodes=release_nodes)
    controls.update(getattr(lease, 'records', {}))
    accepted_operation = emit('active-acceptance.json', {
        'version': 1, 'kind': 'active-owned-disposable-nfs-acceptance',
        'disposable_probe_verified': False, 'final_ack_required': True,
        'owned_fixture_absence_verified': False, 'canary_acceptance_sha256': result['acceptance_sha256'],
        'active_scope_sha256': sf['sha256'], 'cleanup_sha256': controls[output / 'cleanup-result.json']['sha256'],
        'platform_supported': result['platform_supported'], 'future_mylar_destination_verified': False,
        'actual_library_platform_verified': False, 'native_grant': False,
        'publication_authority': False, 'writer_lifecycle_resume_authorized': False})
    owned_directories = {p: stamp(p) for p in (output, probe_output, output / 'lease-empty-config')}
    final_ancestors = ancestry([*controls, output, *roots])
    check(all(ancestors.get(p) == v for p, v in final_ancestors.items() if p in ancestors),
          'post-release-source-ancestor-drift')
    ancestors.update(final_ancestors)
    expected_output = {'lease-empty-config', 'derived-probe-plan.json', 'probe',
                       'active-preflight.json', 'library-settings.json', 'staging-record.json',
                       'cleanup-result.json', 'active-acceptance.json'}
    expected_output.update(p.name for p in getattr(lease, 'records', {}))
    for p, f in controls.items():
        check(fact(p, source=stat.S_IMODE(f['signature'][5]) == 0o644) == f, 'final-active-control-closure')
    for p in effective_absent:
        try:
            os.lstat(p)
        except FileNotFoundError:
            continue
        raise Held('terminal-effective-fonts-present')
    terminal_result = {'disposable_probe_verified': True, 'platform_supported': result['platform_supported'],
            'acceptance_sha256': controls[accepted_operation]['sha256'],
            'owned_fixture_absence_verified': True, 'actual_library_platform_verified': False,
            'future_mylar_destination_verified': False, 'native_grant': False,
            'publication_authority': False, 'writer_lifecycle_resume_authorized': False}
    ack_fd=getattr(a,'ack_fd',None)
    terminal_ack=encode(terminal_result)+b'\n' if ack_fd is not None else None
    terminal_files = {p: f['signature'] for p, f in controls.items()} | rootstates | owned_directories | effective_absent_parents
    terminal_nodes = {Path(p): v for p,v in ancestors.items()}
    terminal_names = {output: expected_output, output / 'lease-empty-config': set(), probe_output: probe_census}
    file_items = tuple((str(p),tuple(v)) for p,v in terminal_files.items())
    node_items = tuple((str(p),tuple(v)) for p,v in terminal_nodes.items())
    name_items = tuple((str(p),frozenset(v)) for p,v in terminal_names.items())
    missing_items = tuple(str(p) for p in (*effective_absent, fixture, canonical(parent['path'])))
    # Helper result is never the last proof: original immutable tuples close
    # again after the helper returns, including post-release owned absences.
    initial_projection=_NATIVE_PROJECTOR(dict(inspect=next(r for r in rows if r['Name']=='/mylar3'),process=initial['native_process'],publication=initial['publication']))
    def native_after_release():
        current=json.loads(call(DOCKER+['inspect','mylar3','komga-comic-normalizer-1','komga']))
        native_row=next(r for r in current if r['Name']=='/mylar3')
        live=identities([r for r in current if r['Name']!='/komga'])
        health=fresh_native(call,native_row['Id'])
        projection=_NATIVE_PROJECTOR(dict(inspect=native_row,process=health['process'],publication=health['publication']))
        observed=dict(mapping=live,native_process=health['process'],native_config=health['config'],projection=projection)
        # Lease has ended. Original startup hold/census must return, not writer-busy.
        check(observed['native_process']==initial['native_process'] and observed['native_config']==initial['native_config']
              and projection==initial_projection,'post-release-original-native-census')
        actual_mount=observe_mount(core['library_root']);actual_device=stamp(canonical(core['library_root']))[0]
        return current,observed,actual_mount,actual_device
    current_rows,current_native,current_mount,current_device=native_after_release()
    factual=ActiveNFSCanaryObservation(_ACTIVE_KEY,file_items,node_items,name_items,missing_items,terminal_result,
                                     current_rows,current_native,current_mount,current_device,native_after_release)
    module.close_vector(terminal_files,terminal_nodes,terminal_names,absent=missing_items)
    for p,v in name_items:
        if frozenset(os.listdir(p)) != v:raise Held('terminal-census')
    for p,v in node_items:
        x=os.lstat(p)
        if (x.st_dev,x.st_ino,x.st_mode,x.st_uid,x.st_gid)!=v:raise Held('terminal-ancestor')
    for p,v in file_items:
        x=os.lstat(p)
        if (x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode,x.st_uid,x.st_gid,x.st_nlink)!=v:raise Held('terminal-leaf')
    for p in missing_items:
        try:os.lstat(p)
        except FileNotFoundError:continue
        raise Held('terminal-owned-absence')
    if ack_fd is not None:
        if os.write(ack_fd,terminal_ack)!=len(terminal_ack):raise Held('terminal-ack-short-write')
    return factual



def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute", action="store_true")
    for key in ("input", "input-sha256", "source-sha256"):
        p.add_argument("--" + key)
    a = p.parse_args()
    if not all((a.input, a.input_sha256, a.source_sha256)):
        print(
            json.dumps(
                dict(
                    executable=False,
                    scope_evidence_required=True,
                    actual_library_platform_verified=False,
                    publication_authority=False,
                )
            )
        )
        return
    try:
        if a.execute:
            a.ack_fd=sys.stdout.fileno();sys.stdout.flush()
            execute(a)
        else:
            print(json.dumps(execute(a),sort_keys=True))
    except (Held, OSError, KeyError, TypeError, ValueError, urllib.error.URLError):
        print(
            json.dumps(
                dict(
                    held=True,
                    probe_verified=False,
                    disposable_probe_verified=False,
                    platform_supported=False,
                    owned_fixture_absence_verified=False,
                    actual_library_platform_verified=False,
                    native_grant=False,
                    fixtures_retained=True,
                    automatic_retry=False,
                    automatic_delete=False,
                    publication_authority=False,
                )
            )
        )
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
