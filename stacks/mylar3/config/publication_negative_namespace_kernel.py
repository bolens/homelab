"""Private transition mechanics. Only local fixture adapter is implemented."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import threading
import time


class Held(ValueError):
    pass


def _check(v, reason):
    if not v:
        raise Held(reason)


def _encode(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _sig(path):
    s = os.lstat(path)
    return [
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


def _stable(path):
    s = _sig(path)
    return [s[i] for i in (0, 1, 5, 6, 7)]


def _canonical(path):
    p = Path(path)
    _check(
        p.is_absolute() and ".." not in p.parts and p.resolve(strict=True) == p,
        "canonical",
    )
    return p


def _attrs(path):
    names = sorted(os.listxattr(path, follow_symlinks=False))
    _check(len(names) <= 64, "xattr-count")
    values = {n: os.getxattr(path, n, follow_symlinks=False).hex() for n in names}
    _check(
        sum(len(os.fsencode(n)) + len(bytes.fromhex(v)) for n, v in values.items())
        <= 1024**2,
        "xattr-bytes",
    )
    return values


def _fact(path, links, max_bytes=4 * 1024**3):
    p = _canonical(path)
    before = _sig(p)
    _check(
        stat.S_ISREG(before[5]) and before[8] == links and 0 < before[2] <= max_bytes,
        "exact-link-file",
    )
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        h = hashlib.sha256()
        n = 0
        deadline = time.monotonic() + 120
        while True:
            _check(time.monotonic() < deadline, "hash-deadline")
            b = os.read(fd, 1024**2)
            if not b:
                break
            n += len(b)
            _check(n <= before[2], "file-growth")
            h.update(b)
        attrs = _attrs(p)
        s = os.fstat(fd)
        _check(
            n == before[2]
            and [
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
            == before
            and _sig(p) == before,
            "hash-drift",
        )
        return {"signature9": before, "sha256": h.hexdigest(), "xattrs": attrs}
    finally:
        os.close(fd)


def _preserved(value, original, links):
    return (
        value["sha256"] == original["sha256"]
        and value["xattrs"] == original["xattrs"]
        and value["signature9"][8] == links
        and all(
            value["signature9"][i] == original["signature9"][i]
            for i in (0, 1, 2, 3, 5, 6, 7)
        )
        and value["signature9"][4] >= original["signature9"][4]
    )


def _namespace(path):
    before = _sig(path)
    names = sorted(os.listdir(path))
    _check(len(names) <= 10000, "namespace-bound")
    values = {name: _sig(path / name) for name in names}
    _check(_sig(path) == before, "namespace-capture-drift")
    return values


def _sync(path):
    fd = os.open(
        path,
        os.O_RDONLY | os.O_NOFOLLOW | (os.O_DIRECTORY if Path(path).is_dir() else 0),
    )
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write(path, raw):
    _check(len(raw) <= 8 * 1024**2, "journal-byte-bound")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    _sync(path.parent)


class _Kernel:
    """Private caller must hold owning scope fence. Does not manufacture authority."""

    def __init__(self, scope, source, target, journal):
        self.trusted_original = None
        self.trusted_receipt = None
        self.scope = scope
        self.source = Path(source)
        self.target = Path(target)
        self.journal = Path(journal)
        scope.check()
        _check(
            self.source != self.target and self.source.parent != self.target.parent,
            "distinct-private-sibling",
        )
        self.ancestors = {
            q: _stable(q)
            for p in (self.source, self.target, self.journal)
            for q in p.parents
        }
        self.parents = {
            p: _stable(p)
            for p in (self.source.parent, self.target.parent, self.journal)
        }
        self.base_namespaces = {
            p: _namespace(p) for p in (self.source.parent, self.target.parent)
        }
        _check(
            _sig(self.source.parent)[0] == _sig(self.target.parent)[0],
            "same-filesystem",
        )

    def _rows(self):
        self.scope.check()
        journal9 = _sig(self.journal)
        names = set(os.listdir(self.journal))
        _check(
            len(names) <= 16 and all(n.endswith(".json") for n in names),
            "journal-namespace",
        )
        rows = []
        previous = None
        for n in range(len(names)):
            path = self.journal / f"{n:02d}.json"
            _check(path.name in names, "journal-gap")
            f = _fact(path, 1, max_bytes=8 * 1024**2)
            _check(stat.S_IMODE(f['signature9'][5]) == 0o600 and f['signature9'][6] == os.geteuid(), 'private-journal-leaf')
            raw = path.read_bytes()
            _check(
                hashlib.sha256(raw).hexdigest() == f["sha256"]
                and _sig(path) == f["signature9"],
                "journal-read",
            )

            def pairs(values):
                out = {}
                for k, v in values:
                    _check(k not in out, "duplicate-journal")
                    out[k] = v
                return out

            value = json.loads(raw, object_pairs_hook=pairs)
            _check(
                value["version"] == 1
                and type(value["version"]) is int
                and value["index"] == n
                and value["previous"] == previous
                and value["source"] == str(self.source)
                and value["target"] == str(self.target)
                and value["native_grant"] is False
                and value["publication_acceptance"] is False,
                "journal-chain",
            )
            rows.append((value, f))
            previous = f["sha256"]
        if self.trusted_original is not None:
            _check(
                bool(rows)
                and rows[0][0]["original"] == self.trusted_original
                and rows[-1][1]["sha256"] == self.trusted_receipt,
                "owned-receipt-custody",
            )
        if rows:
            first = rows[0][0]
            _check(
                first["phase"] == "prepared"
                and first["parents"] == {str(p): v for p, v in self.parents.items()}
                and first["ancestors"]
                == {str(p): v for p, v in self.ancestors.items()},
                "durable-fenced-namespace",
            )
            self.base_namespaces = {
                Path(p): v for p, v in first["base_namespaces"].items()
            }
        _check(_sig(self.journal) == journal9, "journal-census-incarnation")
        return rows

    def _append(self, phase, **extra):
        rows = self._rows()
        value = {
            "version": 1,
            "index": len(rows),
            "phase": phase,
            "previous": rows[-1][1]["sha256"] if rows else None,
            "source": str(self.source),
            "target": str(self.target),
            "native_grant": False,
            "publication_acceptance": False,
            **extra,
        }
        raw = _encode(value)
        _write(self.journal / f"{len(rows):02d}.json", raw)
        self.trusted_receipt = hashlib.sha256(raw).hexdigest()
        return value

    def _proof(self, source, target, transition=False):
        self.scope.check()
        for path, expected in self.parents.items():
            _check(_stable(path) == expected, "parent-drift")
        journal9 = _sig(self.journal)
        rows = self._rows()
        original = rows[0][0]["original"]
        values = {}
        for path, exists in ((self.source, source), (self.target, target)):
            if exists:
                value = _fact(path, 2 if source and target else 1)
                _check(
                    _preserved(value, original, 2 if source and target else 1),
                    "immutable-content-custody",
                )
                values[path] = value
            else:
                _check(not os.path.lexists(path), "expected-absence")
        if source and target:
            _check(values[self.source] == values[self.target], "exact-owned-pair")
        phase = rows[-1][0]
        known = phase.get(
            "restored", phase.get("retained", phase.get("pair", original))
        )
        if not transition:
            _check(
                all(value == known for value in values.values()),
                "known-custody-incarnation",
            )
        namespace_expected = {}
        for parent, participant, present in (
            (self.source.parent, self.source, source),
            (self.target.parent, self.target, target),
        ):
            names = dict(self.base_namespaces[parent])
            names.pop(participant.name, None)
            if present:
                names[participant.name] = values[participant]["signature9"]
            _check(_namespace(parent) == names, "fenced-namespace")
            namespace_expected[parent] = names
        directory9 = {p: _sig(p) for p in self.parents}
        # Never admit a post-callback journal census as the original baseline.
        directory9[self.journal] = journal9
        self.scope.check()
        # All semantic callbacks have finished; final namespace and direct vectors.
        for path, expected in {**self.ancestors, **self.parents}.items():
            _check(_stable(path) == expected, "terminal-parent")
        for path, exists in ((self.source, source), (self.target, target)):
            if exists:
                _check(_sig(path) == values[path]["signature9"], "terminal-file")
            else:
                _check(not os.path.lexists(path), "terminal-absence")
        for value, file_fact in rows:
            _check(
                _sig(self.journal / f"{value['index']:02d}.json")
                == file_fact["signature9"],
                "terminal-journal-leaf",
            )
        for parent, names in namespace_expected.items():
            for name, signature in names.items():
                _check(_sig(parent / name) == signature, "terminal-coowned-leaf")
        for path, expected in directory9.items():
            _check(_sig(path) == expected, "terminal-directory9")
        return values

    def prepare(self):
        self.scope.check()
        _check(not self._rows(), "no-replay")
        _check(not os.path.lexists(self.target), "target-exists")
        original = _fact(self.source, 1)
        self._append(
            "prepared",
            original=original,
            parents={str(p): v for p, v in self.parents.items()},
            ancestors={str(p): v for p, v in self.ancestors.items()},
            base_namespaces={str(p): v for p, v in self.base_namespaces.items()},
        )
        self.trusted_original = original
        self._proof(True, False)
        return {
            "prepared": True,
            "native_grant": False,
            "publication_acceptance": False,
        }

    def _link(self, old, new, known):
        a = os.open(old.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        b = os.open(new.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            self.scope.check()
            _check(
                _stable(old.parent) == self.parents[old.parent]
                and _stable(new.parent) == self.parents[new.parent],
                "link-parent",
            )
            _check(_sig(old) == known["signature9"], "link-known-inode")
            os.link(
                old.name, new.name, src_dir_fd=a, dst_dir_fd=b, follow_symlinks=False
            )
        finally:
            os.close(a)
            os.close(b)
        _sync(old)
        _sync(old.parent)
        _sync(new.parent)

    def _unlink(self, path, known):
        self.scope.check()
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            _check(
                _stable(path.parent) == self.parents[path.parent]
                and _sig(path) == known["signature9"],
                "unlink-owned-only",
            )
            os.unlink(path.name, dir_fd=fd)
        finally:
            os.close(fd)
        _sync(path.parent)

    def apply(self):
        _check(self.trusted_original is not None, "fresh-owning-capability-required")
        rows = self._rows()
        _check([r[0]["phase"] for r in rows] == ["prepared"], "no-automatic-replay")
        self._proof(True, False)
        self._append("link-intent", pending=True)
        current = self._proof(True, False)[self.source]
        self._link(self.source, self.target, current)
        pair = self._proof(True, True, transition=True)
        self._append("linked", pair=pair[self.source], pending=True)
        pair = self._proof(True, True)
        self._append("unlink-intent", pair=pair[self.source], pending=True)
        pair = self._proof(True, True)
        self._unlink(self.source, pair[self.source])
        retained = self._proof(False, True, transition=True)[self.target]
        self._append("retained", retained=retained, pending=True)
        self._proof(False, True)
        return {
            "fixture_transition_verified": True,
            "native_grant": False,
            "publication_acceptance": False,
            "nfs_support_verified": False,
        }

    def rollback(self):
        _check(self.trusted_original is not None, "fresh-owning-capability-required")
        rows = self._rows()
        _check(
            [r[0]["phase"] for r in rows]
            == ["prepared", "link-intent", "linked", "unlink-intent", "retained"],
            "rollback-phase",
        )
        retained = self._proof(False, True)[self.target]
        _check(retained == rows[-1][0]["retained"], "rollback-owned-witness")
        self._append("rollback-link-intent", retained=retained, pending=True)
        current = self._proof(False, True)[self.target]
        self._link(self.target, self.source, current)
        pair = self._proof(True, True, transition=True)
        self._append("rollback-linked", pair=pair[self.source], pending=True)
        self._append("rollback-unlink-intent", pair=pair[self.source], pending=True)
        pair = self._proof(True, True)
        self._unlink(self.target, pair[self.target])
        restored = self._proof(True, False, transition=True)[self.source]
        self._append("rolled-back", restored=restored, pending=True)
        self._proof(True, False)
        return {
            "fixture_rollback_verified": True,
            "native_grant": False,
            "publication_acceptance": False,
        }

    def inspect_pending(self):
        rows = self._rows()
        _check(bool(rows), "missing-intent")
        source = os.path.lexists(self.source)
        target = os.path.lexists(self.target)
        _check(source or target, "missing-preserved-inode")
        witnesses = self._proof(source, target, transition=True)
        return {
            "phase": rows[-1][0]["phase"],
            "held": True,
            "automatic_replay": False,
            "mechanical_witnesses": {str(p): v for p, v in witnesses.items()},
            "native_grant": False,
            "publication_acceptance": False,
        }


class LocalFixtureAdapter:
    """Nonserializable local test lease; never a production/native capability."""

    def __init__(self, root):
        self.root = _canonical(root)
        s = _sig(self.root)
        _check(
            self.root.parent == Path("/tmp")
            and self.root.name.startswith("comic-hardlink-fixture-")
            and s[6] == os.geteuid() == 1000
            and stat.S_IMODE(s[5]) == 0o700,
            "fixture-scope",
        )
        _check(
            set(os.listdir(self.root))
            == {"library", "private", "journal", "lease.lock"},
            "fixture-only-namespace",
        )
        for name in ("library", "private", "journal"):
            p = _canonical(self.root / name)
            v = _sig(p)
            _check(
                v[6] == 1000 and stat.S_IMODE(v[5]) == 0o700,
                "fixture-private-directory",
            )
        self.deadline = time.monotonic() + 120
        self.thread = threading.get_ident()
        self.fd = os.open(self.root / "lease.lock", os.O_RDWR | os.O_NOFOLLOW)
        fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.lease = _sig(self.root / "lease.lock")
        self.identity = _stable(self.root)
        self.closed = False
        self.kernel = _Kernel(
            self,
            self.root / "library/source.bin",
            self.root / "private/retained.bin",
            self.root / "journal",
        )

    def check(self):
        fd = os.fstat(self.fd) if not self.closed else None
        _check(
            not self.closed
            and time.monotonic() < self.deadline
            and self.thread == threading.get_ident()
            and _stable(self.root) == self.identity
            and _sig(self.root / "lease.lock") == self.lease
            and [
                getattr(fd, k)
                for k in (
                    "st_dev",
                    "st_ino",
                    "st_size",
                    "st_mtime_ns",
                    "st_ctime_ns",
                    "st_mode",
                    "st_uid",
                    "st_gid",
                    "st_nlink",
                )
            ]
            == self.lease,
            "fixture-lease-lost",
        )

    def close(self):
        if not self.closed:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.closed = True

    def __enter__(self):
        return self.kernel

    def __exit__(self, *_):
        self.close()


def retire_native(capability=None):
    raise Held(
        "Legitimate owning native and reader negative-retirement consumer not installed"
    )


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(
        json.dumps(
            {
                "executable": False,
                "native_grant": False,
                "publication_acceptance": False,
                "nfs_support_verified": False,
            }
        )
    )


if __name__ == "__main__":
    main()
