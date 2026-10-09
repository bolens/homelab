"""Pure projection of accepted detached eleven-row evidence; no I/O or grants."""
import base64
import hashlib
import json
import math
import re
import struct

SOURCE = "ebac3228fa3c6055b86e3636fb33368f4ccf21950b452e7d6c10070af4a2c99a"
SCHEMAS = {"database.sqlite": "f17a186b24d6b4b35473d9dc23bbecffae260adeee5e04fe31dcc786bed322ad", "tasks.sqlite": "98905e11edcba01c7c83caf89f36f6036261035318039576651e2c447c58df22"}
MAX = 64 * 1024**2
class Held(ValueError):
    pass

def check(v, why):
    if not v:
        raise Held(why)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def decode(raw):
    check(type(raw) is bytes and 0 < len(raw) <= MAX, "bounded-bytes")
    def pairs(xs):
        out = {}
        for key, value in xs:
            check(key not in out, "duplicate")
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(Held("nonfinite")))

def cell(v):
    check(type(v) is list and len(v) in (1, 2), "typed-cell")
    if v == ["null"]:
        return "null"
    check(len(v) == 2 and type(v[1]) is str and len(v[1].encode()) <= 1024**2, "typed-value")
    tag, value = v
    if tag == "integer":
        check(re.fullmatch(r"-?(0|[1-9][0-9]*)", value) is not None and str(int(value)) == value, "integer")
    elif tag == "real":
        check(re.fullmatch(r"[0-9a-f]{16}", value) is not None and math.isfinite(struct.unpack(">d", bytes.fromhex(value))[0]), "real")
    elif tag == "blob":
        try:
            check(base64.b64encode(base64.b64decode(value, validate=True)).decode() == value, "blob")
        except ValueError:
            raise Held("blob") from None
    else:
        check(tag == "text", "typed-tag")
    return tag

def project(rows_raw, rows_sha256, ack_raw, ack_sha256):
    check(digest(rows_raw) == rows_sha256 and digest(ack_raw) == ack_sha256, "accepted-digests")
    report, ack = decode(rows_raw), decode(ack_raw)
    check(ack.get("backup_verified") is True and ack.get("targeted_eleven_row_observation_verified") is True and ack.get("rows_report_sha256") == rows_sha256 and ack.get("mutation_authority") is False and ack.get("publication_acceptance") is False, "root-terminal-ack")
    check(type(report.get("version")) is int and report["version"] == 1 and report.get("kind") == "reader-restored-eleven-row-observation" and report.get("source_sha256") == SOURCE and report.get("observation_verified") is False and report.get("final_ack_required") is True and report.get("timestamp_encoding_approved") is False and report.get("mutation_authority") is False and report.get("publication_acceptance") is False, "rows-envelope")
    ids = report.get("selected_ids")
    check(type(ids) is list and len(ids) == 11 and all(type(x) is str and 0 < len(x) <= 128 for x in ids) and len(set(ids)) == 11, "exact-eleven")
    databases = report.get("databases")
    check(type(databases) is dict and set(databases) == set(SCHEMAS) and all(databases[k].get("schema_sha256") == v for k, v in SCHEMAS.items()), "actual-schemas")
    main = databases["database.sqlite"]
    rows, observed = main.get("selected_rows"), main.get("timestamp_observations")
    check(type(rows) is dict and type(observed) is dict and set(rows) == set(ids) == set(observed), "selected-census")
    summaries = []
    counts = {name: {} for name in ("LAST_MODIFIED_DATE", "DELETED_DATE")}
    for book_id in ids:
        row = rows[book_id]
        check(type(row) is list and len(row) == 14 and row[0] == ["text", book_id], "row-owner")
        entry = {"book_id": book_id}
        for name, index in (("LAST_MODIFIED_DATE", 2), ("DELETED_DATE", 11)):
            value = row[index]
            storage = cell(value)
            check(observed[book_id].get(name) == storage, "storage-cross-binding")
            counts[name][storage] = counts[name].get(storage, 0) + 1
            entry[name] = {"sqlite_storage": storage, "typed_value": value, "utc_text_syntax": storage == "text" and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,9})?", value[1]) is not None}
        summaries.append(entry)
    return {"version": 1, "kind": "detached-eleven-book-timestamp-summary", "rows_report_sha256": rows_sha256, "root_terminal_ack_sha256": ack_sha256, "restore_source_sha256": SOURCE, "schema_sha256": SCHEMAS, "selected_count": 11, "timestamps": summaries, "storage_counts": counts, "timestamp_encoding_approved": False, "chosen_mutation_timestamp": None, "mutation_authority": False, "publication_acceptance": False, "live_source_current": False}

if __name__ == "__main__":
    print(json.dumps({"execute": False, "mutation_authority": False, "timestamp_encoding_approved": False}))
