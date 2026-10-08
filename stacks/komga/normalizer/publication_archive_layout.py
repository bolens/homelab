"""Bounded exact ZIP32 header layout. No file writes or admission."""
import hashlib
import stat
import struct

class Held(ValueError):
    pass


def check(v, reason):
    if not v:
        raise Held(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def exact_entry(value):
    keys = {
        "index",
        "name",
        "external_attr",
        "create_system",
        "flag_bits",
        "compression",
        "bytes",
        "compressed_bytes",
        "stored_crc32",
        "header_offset",
    }
    check(
        type(value) is dict and set(value) == keys and type(value["name"]) is str,
        "one-entry-fields",
    )
    for k in keys - {"name"}:
        check(type(value[k]) is int and 0 <= value[k] <= 0xFFFFFFFF, "entry-integer")
    check(
        value["index"] < 4096
        and value["create_system"] == 3
        and value["flag_bits"] == 0
        and value["compression"] == 0
        and value["bytes"] == value["compressed_bytes"] == value["stored_crc32"] == 0
        and stat.S_IFMT(value["external_attr"] >> 16) == stat.S_IFDIR
        and value["external_attr"] & 0x10
        and not value["name"].endswith("/"),
        "one-malformed-empty-directory",
    )
    return value


def extras(raw):
    pos = 0
    while pos < len(raw):
        check(pos + 4 <= len(raw), "extra-header")
        kind, size = struct.unpack_from("<HH", raw, pos)
        pos += 4
        check(
            pos + size <= len(raw) and kind in (0x5455, 0x7875, 0x000A),
            "unsupported-extra-semantics",
        )
        pos += size


def layout(stream, size):
    stream.seek(max(0, size - 65557))
    tail = stream.read()
    at = tail.rfind(b"PK\x05\x06")
    check(at >= 0 and at + 22 <= len(tail), "eocd")
    e = struct.unpack_from("<4s4H2LH", tail, at)
    eocd = max(0, size - 65557) + at
    check(
        e[1] == e[2] == 0
        and e[3] == e[4]
        and 0 < e[4] <= 4096
        and e[5] <= 8 * 1024**2
        and e[6] + e[5] == eocd
        and at + 22 + e[7] == len(tail),
        "closed-zip32-directory",
    )
    stream.seek(e[6])
    central = stream.read(e[5])
    pos = 0
    rows = []
    for index in range(e[4]):
        check(pos + 46 <= len(central), "central-header-bound")
        h = struct.unpack_from("<4s6H3L5H2L", central, pos)
        check(
            h[0] == b"PK\x01\x02"
            and h[13] == 0
            and h[8] != 0xFFFFFFFF
            and h[9] != 0xFFFFFFFF
            and h[16] != 0xFFFFFFFF,
            "central-zip32",
        )
        length = 46 + h[10] + h[11] + h[12]
        check(pos + length <= len(central), "central-record-bound")
        name = central[pos + 46 : pos + 46 + h[10]]
        extra = central[pos + 46 + h[10] : pos + 46 + h[10] + h[11]]
        extras(extra)
        check(h[3] in (0, 0x800) and h[4] in (0, 8), "unsupported-flags-compression")
        decoded = name.decode("utf-8" if h[3] & 0x800 else "cp437")
        check("\0" not in decoded, "nul-name")
        stream.seek(h[16])
        local = stream.read(30)
        check(len(local) == 30, "local-bound")
        local_fields = struct.unpack("<4s5H3L2H", local)
        check(
            local_fields[0] == b"PK\x03\x04"
            and tuple(local_fields[1:9]) == tuple(h[2:10]),
            "central-local-fields",
        )
        rawname = stream.read(local_fields[9])
        rawextra = stream.read(local_fields[10])
        check(
            len(rawname) == local_fields[9]
            and len(rawextra) == local_fields[10]
            and rawname == name,
            "central-local-name",
        )
        extras(rawextra)
        end = h[16] + 30 + local_fields[9] + local_fields[10] + h[8]
        check(end <= e[6], "local-data-bound")
        rows.append(
            {
                "index": index,
                "name": decoded,
                "external_attr": h[15],
                "create_system": h[1] >> 8,
                "flag_bits": h[3],
                "compression": h[4],
                "bytes": h[9],
                "compressed_bytes": h[8],
                "stored_crc32": h[7],
                "header_offset": h[16],
                "local_end": end,
                "local_header_sha256": sha(local + rawname + rawextra),
                "central_header_sha256": sha(central[pos : pos + length]),
                "raw_name_sha256": sha(name),
            }
        )
        pos += length
    check(pos == len(central), "central-complete")
    physical = sorted(rows, key=lambda r: r["header_offset"])
    check(physical[0]["header_offset"] == 0, "no-prefix")
    for left, right in zip(physical, physical[1:]):
        check(left["local_end"] == right["header_offset"], "local-gap-overlap")
    check(physical[-1]["local_end"] == e[6], "local-closed")
    return rows, {
        "central_offset": e[6],
        "central_bytes": e[5],
        "eocd_offset": eocd,
        "comment_sha256": sha(tail[at + 22 :]),
    }
