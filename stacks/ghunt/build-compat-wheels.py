"""Build reproducible, explicitly versioned compatibility wheels from pinned inputs.

Application bytes and licenses stay unchanged. Only the tested dependency metadata
changes. The resulting wheels have their own versions, RECORDs and lock hashes.
"""
import base64
import csv
import hashlib
import io
from pathlib import Path
import sys
import zipfile

RECIPES = {
    "ghunt-2.3.4-py3-none-any.whl": (
        "7b880072131b7a064e6500b9db2f64bd33eb3b396702825330c507243b617f4d",
        "ghunt-2.3.4", "ghunt-2.3.4+homelab.2", {
            "Version: 2.3.4": "Version: 2.3.4+homelab.2",
            "Requires-Dist: httpx[http2] (>=0.27.2,<0.28.0)": "Requires-Dist: httpx[http2] (==0.28.1)",
            "Requires-Dist: jsonpickle (>=3.3.0,<4.0.0)": "Requires-Dist: jsonpickle (==4.1.4)",
            "Requires-Dist: pillow (>=10.4.0,<11.0.0)": "Requires-Dist: pillow (==13.0.0)",
        }),
    "alive_progress-3.3.0-py3-none-any.whl": (
        "63dd33bb94cde15ad9e5b666dbba8fedf71b72a4935d6fb9a92931e69402c9ff",
        "alive_progress-3.3.0", "alive_progress-3.3.0+homelab.1", {
            "Version: 3.3.0": "Version: 3.3.0+homelab.1",
            "Requires-Dist: graphemeu==0.7.2": "Requires-Dist: graphemeu==0.11.0",
        }),
}


def build(source, output):
    digest, old, new, replacements = RECIPES[source.name]
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("upstream wheel digest mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.namelist()
        if len(set(members)) != len(members):
            raise ValueError("duplicate wheel member")
        files = {name.replace(old + ".dist-info/", new + ".dist-info/", 1): archive.read(name)
                 for name in members if not name.endswith("/RECORD")}
    metadata = new + ".dist-info/METADATA"
    lines = files[metadata].decode().splitlines()
    for before, after in replacements.items():
        if lines.count(before) != 1:
            raise ValueError("upstream metadata changed: " + before)
        lines[lines.index(before)] = after
    files[metadata] = ("\n".join(lines) + "\n").encode()
    record = new + ".dist-info/RECORD"
    rows = []
    for name, data in sorted(files.items()):
        encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        rows.append((name, "sha256=" + encoded, str(len(data))))
    rows.append((record, "", ""))
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\n").writerows(rows)
    files[record] = stream.getvalue().encode()
    destination = output / (new + "-py3-none-any.whl")
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return destination


if __name__ == "__main__":
    inputs, output = map(Path, sys.argv[1:])
    output.mkdir(parents=True, exist_ok=True)
    for filename in RECIPES:
        wheel = build(inputs / filename, output)
        print(hashlib.sha256(wheel.read_bytes()).hexdigest(), wheel.name)
