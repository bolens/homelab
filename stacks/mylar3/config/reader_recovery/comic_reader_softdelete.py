"""Typed five-book soft-delete plan and in-memory fixtures only. Live apply disabled.
No database/media/API is opened by the CLI. Restored/live adapters require a
separately reviewed stopped-reader, rollback and native retirement admission.
"""

import argparse
import base64
import hashlib
import json
import math
import re
import sqlite3
import struct

IMAGE = "sha256:d8f772dce7b3dcd8baa0ce7481bd890e68446065ab6c8eb2cb5b24df62fb3c4f"
JAR_SHA = "f76aff7d31f2735ed902e3a004540e869568be42dc099a5560d72fd3d8f2c0fe"
COMMIT = "2ab7a5a61a8b8bb12a6edd576fed380b4b613c99"
MAIN_SCHEMA = "f17a186b24d6b4b35473d9dc23bbecffae260adeee5e04fe31dcc786bed322ad"
TASK_SCHEMA = "98905e11edcba01c7c83caf89f36f6036261035318039576651e2c447c58df22"
COLUMNS = (
    "ID",
    "CREATED_DATE",
    "LAST_MODIFIED_DATE",
    "FILE_LAST_MODIFIED",
    "NAME",
    "URL",
    "SERIES_ID",
    "FILE_SIZE",
    "NUMBER",
    "LIBRARY_ID",
    "FILE_HASH",
    "DELETED_DATE",
    "oneshot",
    "FILE_HASH_KOREADER",
)
BOOK_COLUMNS = [
    [0, "ID", "varchar", 1, None, 1, 0],
    [1, "CREATED_DATE", "datetime", 1, "CURRENT_TIMESTAMP", 0, 0],
    [2, "LAST_MODIFIED_DATE", "datetime", 1, "CURRENT_TIMESTAMP", 0, 0],
    [3, "FILE_LAST_MODIFIED", "datetime", 1, None, 0, 0],
    [4, "NAME", "varchar", 1, None, 0, 0],
    [5, "URL", "varchar", 1, None, 0, 0],
    [6, "SERIES_ID", "varchar", 1, None, 0, 0],
    [7, "FILE_SIZE", "int8", 1, "0", 0, 0],
    [8, "NUMBER", "INT", 1, "0", 0, 0],
    [9, "LIBRARY_ID", "varchar", 1, None, 0, 0],
    [10, "FILE_HASH", "varchar", 1, "''", 0, 0],
    [11, "DELETED_DATE", "datetime", 0, "NULL", 0, 0],
    [12, "oneshot", "boolean", 1, "0", 0, 0],
    [13, "FILE_HASH_KOREADER", "varchar", 1, "''", 0, 0],
]
SQL = 'UPDATE "BOOK" SET "DELETED_DATE"=?, "LAST_MODIFIED_DATE"=? WHERE "ID"=? AND "DELETED_DATE" IS NULL'
REQUIRED = (
    "fresh_stopped_reader_identity",
    "fresh_image_jar_schema",
    "full_reader_backup",
    "independent_isolated_restore",
    "eleven_current_typed_book_rows",
    "current_target_reference_preservation",
    "native_negative_retirement_commit",
    "correct_files_and_owners_preserved",
    "source_originals_and_rollback_retained",
    "current_task_and_scan_exclusion",
    "separate_derived_index_reconciliation",
)


class Held(ValueError):
    pass


def check(v, why):
    if not v:
        raise Held(why)


def encode(v):
    return json.dumps(
        v, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def sha(v):
    return hashlib.sha256(v).hexdigest()


def exact(v, keys):
    check(type(v) is dict and set(v) == set(keys), "schema")


def quote(v):
    check(type(v) is str and "\x00" not in v, "identifier")
    return '"' + v.replace('"', '""') + '"'


def typed(v):
    if v is None:
        return ["null"]
    if type(v) is int:
        return ["integer", str(v)]
    if type(v) is float:
        check(math.isfinite(v), "nonfinite")
        return ["real", struct.pack(">d", v).hex()]
    if type(v) is str:
        return ["text", v]
    if type(v) is bytes:
        return ["blob", base64.b64encode(v).decode("ascii")]
    raise Held("sqlite-type")


def untyped(v):
    check(type(v) is list and 1 <= len(v) <= 2 and type(v[0]) is str, "typed-cell")
    if v == ["null"]:
        return None
    check(len(v) == 2 and type(v[1]) is str, "typed-cell")
    t, s = v
    if t == "text":
        return s
    if t == "integer":
        check(re.fullmatch(r"0|-?[1-9][0-9]*", s) is not None, "integer")
        x = int(s)
        check(-(2**63) <= x < 2**63, "integer")
        return x
    if t == "real":
        check(re.fullmatch("[0-9a-f]{16}", s) is not None, "real")
        x = struct.unpack(">d", bytes.fromhex(s))[0]
        check(math.isfinite(x), "real")
        return x
    if t == "blob":
        try:
            x = base64.b64decode(s, validate=True)
        except ValueError:
            raise Held("blob") from None
        check(base64.b64encode(x).decode("ascii") == s, "blob")
        return x
    raise Held("typed-cell")


def row_encode(row):
    return [typed(v) for v in row]


def row_decode(row):
    check(type(row) is list and len(row) == 14, "book-row")
    return tuple(untyped(v) for v in row)


def schema_admission(document):
    check(
        type(document) is dict
        and set(document["databases"]) == {"database.sqlite", "tasks.sqlite"},
        "schema-databases",
    )
    result = {}
    for name, expected in (
        ("database.sqlite", MAIN_SCHEMA),
        ("tasks.sqlite", TASK_SCHEMA),
    ):
        objects = document["databases"][name]["objects"]
        check(
            type(objects) is list
            and sha(encode(objects)) == expected
            and document["databases"][name]["schema_sha256"] == expected,
            "actual-schema-pin",
        )
        result[name] = objects
    objects = result["database.sqlite"]
    book = [o for o in objects if o["type"] == "table" and o["name"] == "BOOK"]
    check(len(book) == 1 and book[0]["columns"] == BOOK_COLUMNS, "actual-book-shape")
    check(not any(o["type"] == "trigger" for o in objects), "no-trigger")
    return result


def compile_plan(document, manifest):
    schema_admission(document)
    exact(
        manifest,
        (
            "version",
            "kind",
            "image",
            "jar_sha256",
            "source_commit",
            "pairs",
            "before_rows",
            "timestamp",
            "timestamp_encoding",
            "timestamp_encoding_evidence_sha256",
        ),
    )
    check(
        type(manifest["version"]) is int
        and manifest["version"] == 1
        and manifest["kind"] == "reviewed-five-book-softdelete-input"
        and manifest["image"] == IMAGE
        and manifest["jar_sha256"] == JAR_SHA
        and manifest["source_commit"] == COMMIT,
        "runtime-contract",
    )
    stamp = manifest["timestamp"]
    check(
        type(stamp) is str
        and re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,9})?",
            stamp,
        )
        is not None
        and manifest["timestamp_encoding"] == "sqlite-jooq-utc-text-reviewed"
        and type(manifest["timestamp_encoding_evidence_sha256"]) is str
        and re.fullmatch(
            "[0-9a-f]{64}", manifest["timestamp_encoding_evidence_sha256"]
        ),
        "timestamp-admission",
    )
    # Encoding requires an actual reviewed reader/restore probe; syntax alone grants nothing.
    from datetime import datetime

    check(datetime.fromisoformat(stamp[:26]).year >= 1970, "timestamp-value")
    pairs = manifest["pairs"]
    check(type(pairs) is list and len(pairs) == 5, "five-pairs")
    source_ids = []
    target_ids = []
    paths = []
    active = []
    shadow = []
    check(type(manifest["before_rows"]) is dict, "before-rows")
    rows = {k: row_decode(v) for k, v in manifest["before_rows"].items()}
    for position, pair in enumerate(pairs):
        exact(pair, ("source_ids", "target_id", "wrong_url", "correct_url"))
        ids = pair["source_ids"]
        target = pair["target_id"]
        check(
            type(ids) is list
            and len(ids) == (2 if position == 4 else 1)
            and all(type(x) is str and 1 <= len(x) <= 128 for x in ids)
            and type(target) is str
            and 1 <= len(target) <= 128,
            "pair-cardinality",
        )
        check(
            type(pair["wrong_url"]) is str
            and type(pair["correct_url"]) is str
            and pair["wrong_url"] != pair["correct_url"]
            and pair["wrong_url"].startswith("file:")
            and pair["correct_url"].startswith("file:"),
            "exact-urls",
        )
        source_ids += ids
        target_ids.append(target)
        paths.extend((pair["wrong_url"], pair["correct_url"]))
        for book in ids:
            check(
                book in rows
                and rows[book][0] == book
                and rows[book][5] == pair["wrong_url"],
                "source-row-identity",
            )
            (active if rows[book][11] is None else shadow).append(book)
        check(
            target in rows
            and rows[target][0] == target
            and rows[target][5] == pair["correct_url"]
            and rows[target][11] is None,
            "correct-row-identity",
        )
    check(
        len(set(source_ids)) == 6
        and len(set(target_ids)) == 5
        and not set(source_ids) & set(target_ids)
        and len(set(paths)) == 10
        and set(rows) == set(source_ids + target_ids)
        and len(active) == 5
        and len(shadow) == 1
        and shadow[0] in pairs[4]["source_ids"],
        "exact-eleven-row-set",
    )
    for row in rows.values():
        check(
            type(row[0]) is str
            and type(row[2]) is str
            and type(row[6]) is str
            and type(row[9]) is str
            and type(row[7]) is int
            and row[7] >= 0
            and type(row[8]) is int
            and row[12] in (0, 1)
            and type(row[12]) is int,
            "book-value-types",
        )
        check(row[11] is None or type(row[11]) is str, "deleted-type")
    after = {k: list(v) for k, v in rows.items()}
    for k in active:
        after[k][2] = stamp
        after[k][11] = stamp
    return dict(
        version=1,
        kind="five-book-softdelete-plan",
        image=IMAGE,
        jar_sha256=JAR_SHA,
        source_commit=COMMIT,
        main_schema_sha256=MAIN_SCHEMA,
        tasks_schema_sha256=TASK_SCHEMA,
        columns=list(COLUMNS),
        active_wrong_ids=active,
        deleted_shadow_ids=shadow,
        correct_ids=target_ids,
        before_rows={k: row_encode(v) for k, v in rows.items()},
        after_rows={k: row_encode(v) for k, v in after.items()},
        sql=SQL,
        parameters=[[typed(stamp), typed(stamp), typed(k)] for k in active],
        required_operational_evidence=list(REQUIRED),
        live_apply_enabled=False,
        mutation_authority=False,
        reference_transfer_verified=False,
        publication_acceptance=False,
        derived_index_reconciled=False,
    )


def snapshot(conn, substitutions=None):
    result = {}
    substitutions = {} if substitutions is None else substitutions
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ):
        columns = [
            r[1]
            for r in conn.execute("PRAGMA table_xinfo(" + quote(name) + ")")
            if r[6] != 1
        ]
        hashes = []
        count = 0
        for row in conn.execute(
            "SELECT " + ",".join(quote(x) for x in columns) + " FROM " + quote(name)
        ):
            if name == "BOOK" and row[0] in substitutions:
                row = substitutions[row[0]]
            hashes.append(sha(encode(row_encode(row))))
            count += 1
            check(count <= 2000000, "fingerprint-bound")
        result[name] = dict(
            columns=columns,
            rows=count,
            typed_multiset_sha256=sha(encode(sorted(hashes))),
        )
    return result


def fixture_transaction(conn, document, manifest, hook=None):
    # This callable never accepts a disk-backed connection or an attached DB.
    check(
        type(conn) is sqlite3.Connection
        and list(conn.execute("PRAGMA database_list"))
        in ([(0, "main", "")], [(0, "main", ""), (1, "temp", "")]),
        "in-memory-fixture-only",
    )
    check(not conn.in_transaction, "fixture-transaction-already-active")
    plan = compile_plan(document, manifest)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA trusted_schema=OFF")
    check(
        list(conn.execute("PRAGMA integrity_check")) == [("ok",)],
        "fixture-integrity-before",
    )
    check(not list(conn.execute("PRAGMA foreign_key_check")), "fixture-fk-before")
    # Exact actual schema objects are verified in the owning helper before disk use.
    objects = schema_admission(document)["database.sqlite"]
    expected_master = [(o["type"], o["name"], o["table"], o["sql"]) for o in objects]
    check(
        list(
            conn.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
            )
        )
        == expected_master,
        "fixture-schema-mismatch",
    )
    before = {k: row_decode(v) for k, v in plan["before_rows"].items()}
    after = {k: row_decode(v) for k, v in plan["after_rows"].items()}
    query = (
        "SELECT "
        + ",".join(quote(x) for x in COLUMNS)
        + ' FROM "BOOK" WHERE "ID" IN ('
        + ",".join("?" for _ in before)
        + ")"
    )
    actual = {r[0]: tuple(r) for r in conn.execute(query, list(before))}
    check(
        {k: row_encode(v) for k, v in actual.items()}
        == {k: row_encode(v) for k, v in before.items()},
        "fixture-current-eleven-rows",
    )
    baseline_cells = {}
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ):
        columns = [
            r[1]
            for r in conn.execute("PRAGMA table_xinfo(" + quote(name) + ")")
            if r[6] != 1
        ]
        sql = "SELECT " + ",".join(quote(x) for x in columns) + " FROM " + quote(name)
        baseline_cells[sql] = sorted(
            tuple((type(v).__name__, repr(v)) for v in row) for row in conn.execute(sql)
        )
    base = snapshot(conn)
    expected = snapshot(conn, {k: after[k] for k in plan["active_wrong_ids"]})
    conn.execute("BEGIN IMMEDIATE")
    try:
        for parameters in plan["parameters"]:
            cur = conn.execute(SQL, [untyped(v) for v in parameters])
            check(cur.rowcount == 1, "exact-active-cas")
        if hook is not None:
            hook(conn)
        observed = {r[0]: tuple(r) for r in conn.execute(query, list(before))}
        check(
            {k: row_encode(v) for k, v in observed.items()}
            == {k: row_encode(v) for k, v in after.items()},
            "exact-five-field-delta",
        )
        post = snapshot(conn)
        check(post == expected, "all-table-preservation")
        check(
            not list(conn.execute("PRAGMA foreign_key_check"))
            and list(conn.execute("PRAGMA integrity_check")) == [("ok",)],
            "fixture-integrity-after",
        )
        conn.rollback()
    except BaseException:
        conn.rollback()
        raise
    check(
        snapshot(conn) == base
        and {r[0]: tuple(r) for r in conn.execute(query, list(before))} == before,
        "fixture-rollback-preserved",
    )
    # All semantic fingerprint callbacks have finished. Direct SQLite reads
    # close every original table after the last rollback/snapshot callback.
    check(
        not conn.in_transaction
        and list(conn.execute("PRAGMA database_list"))
        in ([(0, "main", "")], [(0, "main", ""), (1, "temp", "")]),
        "terminal-fixture-binding",
    )
    for sql, expected_cells in baseline_cells.items():
        actual_cells = sorted(
            tuple((type(v).__name__, repr(v)) for v in row) for row in conn.execute(sql)
        )
        check(actual_cells == expected_cells, "terminal-fixture-table-drift")
    return dict(
        fixture_verified=True,
        planned_updates=5,
        retained_source_ids=6,
        correct_ids_preserved=5,
        table_fingerprints_preserved=True,
        rollback_verified=True,
        live_apply_enabled=False,
        mutation_authority=False,
        reference_transfer_verified=False,
        publication_acceptance=False,
        derived_index_reconciled=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--plan-input")
    parser.add_argument("--schema-input")
    args = parser.parse_args()
    if args.apply:
        print(
            json.dumps(
                dict(
                    held=True,
                    reason="live-apply-disabled-requires-reviewed-owning-adapter",
                    mutation_authority=False,
                )
            )
        )
        return 2
    if not args.plan_input and not args.schema_input:
        print(
            json.dumps(
                dict(
                    executable=False, live_apply_enabled=False, mutation_authority=False
                )
            )
        )
        return 0
    parser.error(
        "CLI input publication is disabled; use checked caller-bound compile_plan for private review"
    )


if __name__ == "__main__":
    raise SystemExit(main())
