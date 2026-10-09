"""Explicit, append-only nested metadata relations and one typed native producer."""

from contextlib import closing
import os
from pathlib import Path, PurePosixPath
import sqlite3
import time
import shutil
import stat
import threading
from contextlib import contextmanager

if __package__:
    from . import publication_guard as guard, publication_lineage as lineage
else:
    import publication_guard as guard
    import publication_lineage as lineage


def core(value):
    result = {key: value[key] for key in ("version", "members", "pages", "payload")}
    guard.validate(result)
    return result


def stamp(value):
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 9
        or any(type(number) is not int or number < 0 for number in value)
    ):
        raise guard.Unavailable("Exact derivative file signature required")


def pathname(value):
    if (
        not isinstance(value, str)
        or not value
        or not Path(value).is_absolute()
        or ".." in Path(value).parts
    ):
        raise guard.Unavailable("Exact derivative evidence path required")


def file_fact(value):
    if (
        not isinstance(value, dict)
        or set(value) != {"path", "signature", "sha256"}
        or not guard.digest_value(value["sha256"])
    ):
        raise guard.Unavailable("Exact derivative file evidence required")
    pathname(value["path"])
    stamp(value["signature"])


def inventory_fact(value):
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "version",
            "members",
            "pages",
            "payload",
            "source_sha256",
            "source_signature",
        }
        or not guard.digest_value(value["source_sha256"])
    ):
        raise guard.Unavailable("Complete derivative inventory wrapper required")
    stamp(value["source_signature"])
    return core(value)


def private_fact(value):
    file_fact(value)
    signature = value["signature"]
    if (
        not stat.S_ISREG(signature[5])
        or stat.S_IMODE(signature[5]) != 0o600
        or signature[8] != 1
    ):
        raise guard.Unavailable(
            "Private exclusive derivative evidence signature required"
        )


def observed_fact(value):
    if not isinstance(value, list) or len(value) > 8:
        raise guard.Unavailable("Bounded derivative owner observations required")
    seen = set()
    for item in value:
        if (
            not isinstance(item, dict)
            or set(item) != {"owner", "source_sha256", "signature", "catalog"}
            or not guard.digest_value(item["source_sha256"])
        ):
            raise guard.Unavailable("Exact derivative owner observation required")
        owner = guard.exact_owner(item["owner"])
        key = guard.canonical_digest(owner)
        if key in seen:
            raise guard.Unavailable("Duplicate derivative owner observation")
        seen.add(key)
        stamp(item["signature"])
        guard.catalog_fact(item["catalog"], owner)


def certificate_facts(request, facts):
    writer = facts["writer"]
    if (
        not isinstance(writer, list)
        or len(writer) != 4
        or any(type(n) is not int or n < 0 for n in writer)
    ):
        raise guard.Unavailable("Exact derivative Writer identity required")
    source = facts["source"]
    if (
        not isinstance(source, dict)
        or set(source) != {"path", "inventory", "decision", "owner", "observed"}
        or source["path"] != request["source"]
        or source["decision"] not in ("unknown", "allowed")
    ):
        raise guard.Unavailable("Exact derivative source admission required")
    guard.exact_owner(source["owner"])
    observed_fact(source["observed"])
    observed_fact(facts["observed"])
    if (source["decision"] == "unknown" and source["observed"]) or (
        source["decision"] == "allowed"
        and request["owner"] not in [row["owner"] for row in source["observed"]]
    ):
        raise guard.Unavailable("Derivative source decision observations changed")
    if (
        len(facts["observed"]) != 1
        or facts["observed"][0]["owner"] != request["owner"]
        or facts["observed"][0]["catalog"]["path"] != request["source"]
        or facts["observed"][0]["source_sha256"] != request["source_sha256"]
    ):
        raise guard.Unavailable("Current selected derivative owner evidence required")
    old, new = inventory_fact(source["inventory"]), inventory_fact(facts["derivative"])
    private_fact(facts["prepared"])
    private_fact(facts["review"])
    if (
        facts["review"]["path"] != request["review"]["path"]
        or facts["review"]["sha256"] != request["review"]["sha256"]
        or not guard.same_json(
            facts["prepared"]["signature"], facts["derivative"]["source_signature"]
        )
        or not guard.same_json(
            facts["observed"][0]["signature"], source["inventory"]["source_signature"]
        )
    ):
        raise guard.Unavailable("Derivative reviewed file evidence changed")
    backup = facts["backup"]
    if (
        not isinstance(backup, dict)
        or set(backup) != {"manifest", "restore", "files"}
        or not isinstance(backup["files"], list)
        or len(backup["files"]) != 4
    ):
        raise guard.Unavailable("Complete derivative backup evidence required")
    for key in ("manifest", "restore"):
        private_fact(backup[key])
        if (
            backup[key]["path"] != request["backup"][key]
            or backup[key]["sha256"] != request["backup"][key + "_sha256"]
        ):
            raise guard.Unavailable("Derivative backup document binding changed")
    roles, identities = set(), set()
    for row in backup["files"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"role", "source", "copies"}
            or row["role"] not in {"source", "catalog", "workflow", "marker"}
            or row["role"] in roles
            or not isinstance(row["copies"], list)
            or len(row["copies"]) != 2
        ):
            raise guard.Unavailable("Exact derivative backup role evidence required")
        roles.add(row["role"])
        file_fact(row["source"])
        for copy in row["copies"]:
            private_fact(copy)
            if copy["sha256"] != row["source"]["sha256"]:
                raise guard.Unavailable("Derivative backup restore digest changed")
        for copy in [row["source"], *row["copies"]]:
            identity = tuple(copy["signature"][:2])
            if identity in identities:
                raise guard.Unavailable("Aliased derivative backup evidence")
            identities.add(identity)
        if row["role"] == "source" and (
            row["source"]["path"] != request["source"]
            or row["source"]["sha256"] != request["source_sha256"]
            or not guard.same_json(
                row["source"]["signature"], source["inventory"]["source_signature"]
            )
        ):
            raise guard.Unavailable("Derivative source backup binding changed")
    migration = facts["migration"]
    if (
        not isinstance(migration, dict)
        or set(migration)
        != {"mapping", "root_sha256", "member_order", "derivative_order"}
        or not guard.digest_value(migration["root_sha256"])
    ):
        raise guard.Unavailable("Exact derivative migration evidence required")
    for key, inventory in (("member_order", old), ("derivative_order", new)):
        names = migration[key]
        if (
            not isinstance(names, list)
            or any(not isinstance(name, str) for name in names)
            or len(names) != len(set(names))
            or {name.rstrip("/") for name in names}
            != {row["name"] for row in inventory["members"]}
            or len(names) != len(inventory["members"])
            or any(
                name.endswith("/")
                and not next(
                    row
                    for row in inventory["members"]
                    if row["name"] == name.rstrip("/")
                )["directory"]
                for name in names
            )
        ):
            raise guard.Unavailable("Incomplete derivative archive order evidence")
    return old, new


def stage_token(request):
    return guard.canonical_digest(
        {
            key: request[key]
            for key in (
                "source",
                "source_sha256",
                "prepared_sha256",
                "owner",
                "mapping",
            )
        }
    )


def prepared_scope(request):
    import mylar

    cache = lineage.path(mylar.CONFIG.CACHE_DIR)
    if not cache.is_dir():
        raise guard.Unavailable("Existing configured derivative cache required")
    expected = cache / "nested-derivatives" / stage_token(request) / "prepared.cbz"
    if lineage.path(request["prepared"]) != expected:
        raise guard.Unavailable(
            "Derivative prepared archive has no exact configured-cache binding"
        )
    lineage.private(str(expected))


@guard.state_errors
def plan_value(plan):
    fields = {"version", "kind", "executable", "readiness", "request", "facts", "token"}
    if (
        not isinstance(plan, dict)
        or set(plan) != fields
        or type(plan["version"]) is not int
        or plan["version"] != 1
        or plan["kind"] != "reviewed-nested-lineage"
        or plan["executable"] is not False
        or plan["readiness"] != "explicit-adoption-required"
        or not guard.digest_value(plan["token"])
        or plan["token"]
        != guard.canonical_digest({k: v for k, v in plan.items() if k != "token"})
    ):
        raise guard.Unavailable("Exact immutable nested lineage certificate required")
    request = lineage.validate(plan["request"])
    facts = plan["facts"]
    if (
        not isinstance(facts, dict)
        or set(facts)
        != {
            "writer",
            "source",
            "observed",
            "derivative",
            "migration",
            "prepared",
            "review",
            "backup",
        }
        or not guard.same_json(facts["source"]["owner"], request["owner"])
        or facts["source"]["inventory"]["source_sha256"] != request["source_sha256"]
        or facts["derivative"]["source_sha256"] != request["prepared_sha256"]
        or facts["prepared"]["path"] != request["prepared"]
        or facts["prepared"]["sha256"] != request["prepared_sha256"]
    ):
        raise guard.Unavailable("Nested lineage certificate facts changed")
    old, new = certificate_facts(request, facts)
    before, after = request["mapping"][0]["from"], request["mapping"][0]["to"]
    if (
        not isinstance(before, str)
        or not isinstance(after, str)
        or "/" not in before
        or PurePosixPath(before).name.casefold() != "comicinfo.xml"
        or after != str(PurePosixPath(before).with_name("SourceMetadata.xml"))
        or old["payload"] == new["payload"]
        or old["pages"] != new["pages"]
    ):
        raise guard.Unavailable("Unsupported derivative mapping or page lineage")
    oldrows = {row["name"]: row for row in old["members"]}
    newrows = {row["name"]: row for row in new["members"]}
    if (
        before not in oldrows
        or after in oldrows
        or before in newrows
        or after not in newrows
    ):
        raise guard.Unavailable("Incomplete derivative member bijection")
    mapped = {after if name == before else name for name in oldrows}
    if "ComicInfo.xml" not in oldrows:
        mapped.add("ComicInfo.xml")
    if mapped != set(newrows):
        raise guard.Unavailable("Derivative adds or removes unrelated members")
    root = newrows.get("ComicInfo.xml")
    if (
        root is None
        or root["directory"]
        or root["bytes"] > guard.MAX_METADATA
        or root["sha256"] != facts["migration"]["root_sha256"]
    ):
        raise guard.Unavailable("Derivative root migration digest or shape changed")
    for name, row in oldrows.items():
        target = after if name == before else name
        if name == "ComicInfo.xml":
            if newrows[name]["sha256"] != facts["migration"]["root_sha256"]:
                raise guard.Unavailable("Derivative root migration digest changed")
        elif not guard.same_json(dict(row, name=target), newrows[target]):
            raise guard.Unavailable("Derivative changed preserved member bytes")
    expected_order = [
        after if name == before else name for name in facts["migration"]["member_order"]
    ]
    if "ComicInfo.xml" not in oldrows:
        expected_order.append("ComicInfo.xml")
    if (
        facts["migration"]["mapping"] != request["mapping"]
        or expected_order != facts["migration"]["derivative_order"]
    ):
        raise guard.Unavailable("Derivative archive order lineage changed")
    return old, new


@guard.state_errors
def attestation(value):
    fields = {
        "version",
        "epoch",
        "prior_revision",
        "inventory",
        "allowed",
        "rejected",
        "evidence",
        "observed",
        "intent",
        "created",
        "lineage",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or type(value["version"]) is not int
        or value["version"] != 2
        or not guard.digest_value(value["epoch"])
        or not guard.digest_value(value["intent"])
        or type(value["prior_revision"]) is not int
        or value["prior_revision"] < 0
        or type(value["created"]) is not int
        or value["created"] < 0
    ):
        raise guard.Unavailable("Exact derivative attestation required")
    relation = value["lineage"]
    if (
        not isinstance(relation, dict)
        or set(relation) != {"version", "plan", "parents"}
        or type(relation["version"]) is not int
        or relation["version"] != 1
        or not isinstance(relation["parents"], list)
        or len(relation["parents"]) > guard.REGISTRY_LIMIT
        or relation["parents"] != sorted(set(relation["parents"]))
        or any(not guard.digest_value(key) for key in relation["parents"])
    ):
        raise guard.Unavailable("Exact derivative ancestry required")
    guard.validate(value["inventory"])
    old, new = plan_value(relation["plan"])
    request = relation["plan"]["request"]
    if (
        not guard.same_json(core(value["inventory"]), new)
        or request["census"]["epoch"] != value["epoch"]
        or request["census"]["revision"] != value["prior_revision"]
    ):
        raise guard.Unavailable("Derivative census or actual new inventory changed")
    owners = []
    for kind in ("allowed", "rejected"):
        group = value[kind]
        if (
            not isinstance(group, list)
            or not (1 if kind == "allowed" else 0) <= len(group) <= 8
        ):
            raise guard.Unavailable("Explicit bounded derivative owners required")
        owners.extend(
            guard.canonical_digest(guard.exact_owner(owner)) for owner in group
        )
    if (
        len(owners) > 8
        or len(owners) != len(set(owners))
        or request["owner"] not in value["allowed"]
    ):
        raise guard.Unavailable("Contradictory derivative owners")
    if (
        not isinstance(value["evidence"], dict)
        or set(value["evidence"]) != {"sha256", "description"}
        or value["evidence"]["sha256"] != relation["plan"]["token"]
        or value["evidence"]["description"]
        != "Reviewed exact nested metadata migration"
        or not isinstance(value["observed"], list)
        or len(value["observed"]) != len(value["allowed"])
    ):
        raise guard.Unavailable("Missing explicit derivative evidence")
    for owner, facts in zip(value["allowed"], value["observed"]):
        if (
            not isinstance(facts, dict)
            or set(facts) != {"owner", "source_sha256", "signature", "catalog"}
            or facts["owner"] != owner
            or not guard.digest_value(facts["source_sha256"])
            or not isinstance(facts["signature"], list)
            or len(facts["signature"]) != 9
            or any(
                type(number) is not int or number < 0 for number in facts["signature"]
            )
        ):
            raise guard.Unavailable("Exact derivative current-owner facts required")
        guard.catalog_fact(facts["catalog"], owner)
    return guard.canonical_digest(value)


@guard.state_errors
def families(records):
    """Exact bounded relations; no filenames, fuzzy matching or arbitrary joins."""
    groups = {}
    indexed = {}
    for key, value in sorted(
        records.items(), key=lambda item: item[1]["prior_revision"]
    ):
        payload = value["inventory"]["payload"]
        if value["version"] == 1:
            group = indexed.get(payload, payload)
            groups.setdefault(group, {})[key] = value
            indexed[payload] = group
        else:
            old, new = plan_value(value["lineage"]["plan"])
            before = old["payload"]
            after = new["payload"]
            group = indexed.get(before, before)
            prior = groups.setdefault(group, {})
            if value["lineage"]["parents"] != sorted(prior):
                raise guard.Unavailable(
                    "Derivative has missing, foreign or stale ancestors"
                )
            if after in indexed:
                raise guard.Unavailable(
                    "Derivative cannot merge existing payload families"
                )
            if prior:
                allowed = {
                    guard.canonical_digest(owner): owner
                    for record in prior.values()
                    for owner in record["allowed"]
                }
                rejected = {
                    guard.canonical_digest(owner): owner
                    for record in prior.values()
                    for owner in record["rejected"]
                }
                if {guard.canonical_digest(owner) for owner in value["allowed"]} != set(
                    allowed
                ) or {
                    guard.canonical_digest(owner) for owner in value["rejected"]
                } != set(rejected):
                    raise guard.Unavailable(
                        "Derivative failed to inherit exact correction owners"
                    )
            elif (
                value["allowed"] != [value["lineage"]["plan"]["request"]["owner"]]
                or value["rejected"]
            ):
                raise guard.Unavailable(
                    "Unknown derivative cannot fabricate correction owners"
                )
            prior[key] = value
            indexed[before] = group
            indexed[after] = group
        allowed = {
            guard.canonical_digest(owner)
            for record in groups[indexed[payload]].values()
            for owner in record["allowed"]
        }
        rejected = {
            guard.canonical_digest(owner)
            for record in groups[indexed[payload]].values()
            for owner in record["rejected"]
        }
        if allowed & rejected:
            raise guard.Unavailable("Contradictory derivative family owners")
    return indexed, groups


def matches(records, payload):
    index, groups = families(records)
    return groups.get(index.get(payload), {})


def semantic(database):
    if __package__:
        from .workflow_store import protected_snapshot
    else:
        from workflow_store import protected_snapshot
    lineage.database(database)
    with closing(
        sqlite3.connect(Path(database).as_uri() + "?mode=ro&immutable=1", uri=True)
    ) as db:
        deadline = time.monotonic() + guard.TIMEOUT
        db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        db.execute("BEGIN")
        return dict(schema=guard.workflow_schema(db), protected=protected_snapshot(db))


@guard.state_errors
def registration_observe(writer, body):
    """Fresh exact proof allows only registration-intent envelope changes."""
    import mylar

    attestation(dict(body, intent="0" * 64))
    plan = body["lineage"]["plan"]
    request = plan["request"]
    facts = plan["facts"]
    prepared_scope(request)
    if guard.writer_identity(writer) != facts["writer"]:
        raise guard.Unavailable("Derivative writer incarnation changed")
    # This observer also runs with a strictly prepared registration marker;
    # RegistryState independently validates the exact old/new census protocol.
    current = guard.observe_owners(
        Path(mylar.DATA_DIR) / "mylar.db",
        writer,
        body["allowed"],
        [mylar.CONFIG.DESTINATION_DIR],
    )
    old, new = plan_value(plan)
    if (
        not guard.same_json(current["inventory"], old)
        or not guard.same_json(current["observed"], body["observed"])
        or current["observed"][body["allowed"].index(request["owner"])]["catalog"][
            "path"
        ]
        != request["source"]
    ):
        raise guard.Unavailable("Derivative source, correct owner or payload changed")
    lineage.migration(
        Path(request["source"]), Path(request["prepared"]), request["mapping"]
    )
    if not guard.same_json(core(guard.inventory(request["prepared"])), new):
        raise guard.Unavailable("Reviewed derivative current inventory changed")
    from_plan = facts["backup"]
    for item in (
        from_plan["manifest"],
        from_plan["restore"],
        facts["review"],
        facts["prepared"],
    ):
        if not guard.same_json(lineage.private(item["path"]), item):
            raise guard.Unavailable("Derivative private evidence incarnation changed")
    if __package__:
        from .publication_transaction import preserved_pair
    else:
        from publication_transaction import preserved_pair
    preserved_pair(request["preservation"], request["source_sha256"])
    for row in from_plan["files"]:
        for copy in row["copies"]:
            if not guard.same_json(lineage.private(copy["path"]), copy):
                raise guard.Unavailable(
                    "Derivative independently verified restore changed"
                )
        source = row["source"]
        if row["role"] == "workflow":
            if guard.signature(Path(source["path"]).lstat())[:2] != source["signature"][
                :2
            ] or not guard.same_json(
                semantic(source["path"]), semantic(row["copies"][1]["path"])
            ):
                raise guard.Unavailable("Derivative protected workflow state changed")
        elif row["role"] == "marker":
            marker = guard.private_json(Path(source["path"]))
            if marker.get("phase") == "prepared":
                if not guard.same_json(marker.get("old"), request["census"]):
                    raise guard.Unavailable(
                        "Derivative registration marker has a foreign predecessor"
                    )
            else:
                signature, sha = guard.file_hash(source["path"])
                if (
                    not guard.same_json(signature, source["signature"])
                    or sha != source["sha256"]
                ):
                    raise guard.Unavailable(
                        "Derivative restored marker baseline changed"
                    )
        else:
            signature, sha = guard.file_hash(source["path"])
            if (
                not guard.same_json(signature, source["signature"])
                or sha != source["sha256"]
            ):
                raise guard.Unavailable(
                    "Derivative restore-verified source baseline changed"
                )
    # Every potentially expensive archive, backup and database read precedes a
    # fresh complete owner observation. A retained plan never refreshes its
    # reviewed source incarnation or its catalog facts.
    final = guard.observe_owners(
        Path(mylar.DATA_DIR) / "mylar.db",
        writer,
        body["allowed"],
        [mylar.CONFIG.DESTINATION_DIR],
    )
    if not guard.same_json(final, current):
        raise guard.Unavailable("Derivative current owners changed during registration")
    for row in from_plan["files"]:
        if row["role"] in ("source", "catalog"):
            signature, sha = guard.file_hash(row["source"]["path"])
            if (
                not guard.same_json(signature, row["source"]["signature"])
                or sha != row["source"]["sha256"]
            ):
                raise guard.Unavailable("Derivative final source baseline changed")
    # Recheck private facts after the final current inventory and catalog calls.
    preserved_pair(request["preservation"], request["source_sha256"])
    for item in (
        facts["prepared"],
        facts["review"],
        from_plan["manifest"],
        from_plan["restore"],
        *[copy for row in from_plan["files"] for copy in row["copies"]],
    ):
        if not guard.same_json(lineage.private(item["path"]), item):
            raise guard.Unavailable(
                "Derivative private evidence changed during admission"
            )
    for role in ("catalog", "source"):
        item = next(row["source"] for row in from_plan["files"] if row["role"] == role)
        signature, sha = guard.file_hash(item["path"])
        if not guard.same_json(signature, item["signature"]) or sha != item["sha256"]:
            raise guard.Unavailable(
                "Derivative current source baseline changed after final private reads"
            )
    return dict(inventory=new, observed=current["observed"])


@guard.state_errors
def prepare(writer, plan, created, database):
    if type(created) is not int or created < 0:
        raise guard.Unavailable("Exact derivative review time required")
    prepared_scope(plan["request"])
    lineage.verify(writer, plan)
    census, records = guard.registry_snapshot(
        database, writer.root / "publication-v1.json"
    )
    if not guard.same_json(census, plan["request"]["census"]):
        raise guard.Unavailable("Derivative reviewed census changed")
    old, new = plan_value(plan)
    parents = matches(records, old["payload"])
    if matches(records, new["payload"]):
        raise guard.Unavailable("Derivative already belongs to a registered family")
    if parents:
        allowed = {
            guard.canonical_digest(owner): owner
            for record in parents.values()
            for owner in record["allowed"]
        }
        rejected = {
            guard.canonical_digest(owner): owner
            for record in parents.values()
            for owner in record["rejected"]
        }
        allowed = [allowed[key] for key in sorted(allowed)]
        rejected = [rejected[key] for key in sorted(rejected)]
    else:
        allowed = [plan["request"]["owner"]]
        rejected = []
    import mylar

    current = guard.observe_owners(
        Path(mylar.DATA_DIR) / "mylar.db",
        writer,
        allowed,
        [mylar.CONFIG.DESTINATION_DIR],
    )
    body = dict(
        version=2,
        epoch=census["epoch"],
        prior_revision=census["revision"],
        inventory=new,
        allowed=allowed,
        rejected=rejected,
        evidence=dict(
            sha256=plan["token"], description="Reviewed exact nested metadata migration"
        ),
        observed=current["observed"],
        created=created,
        lineage=dict(version=1, plan=plan, parents=sorted(parents)),
    )
    state = guard.RegistrationState(database, writer)
    token = state.prepare_registration(
        body, observe=lambda value: registration_observe(writer, value)
    )
    return token


NAME = "nested-derivative-v1.json"
_LOCAL = threading.local()


def file_state(value):
    if __package__:
        from . import tagger_attributes
    else:
        import tagger_attributes
    value = lineage.path(str(value))
    signature, sha = guard.file_hash(value)
    if signature[8] != 1:
        raise guard.Unavailable("Derivative physical alias")
    attributes = tagger_attributes.capture(value)
    if guard.signature(value.lstat()) != signature:
        raise guard.Unavailable("Derivative archive changed during reading")
    return dict(signature=signature, sha256=sha, attributes=attributes)


def packs(request):
    from mylar import native_writers
    import mylar

    if __package__:
        from . import pack_bindings
    else:
        import pack_bindings
    return pack_bindings.capture(
        native_writers.existing_store(mylar.DATA_DIR),
        request["source"],
        request["source"],
        catalog_owner={
            "issueid": request["owner"]["issueid"],
            "comicid": request["owner"]["parentcomicid"],
        },
    )


def packed_after(before, current, request):
    if before is None:
        if current is not None:
            raise guard.Unavailable(
                "Derivative uncaptured pack publication requires review"
            )
        return
    if current is None:
        raise guard.Unavailable("Derivative confirmed pack publication disappeared")
    if (
        before["owner"] != current["owner"]
        or before["source"] != current["source"]
        or before["destination"] != current["destination"]
    ):
        raise guard.Unavailable("Derivative pack publication owner or path changed")
    indexed = {(row["pack"], row["member"]): row for row in current["bindings"]}
    for binding in before["bindings"]:
        row = indexed.get((binding["pack"], binding["member"]))
        if row is None:
            raise guard.Unavailable("Derivative captured pack member disappeared")
        expected = dict(
            binding["before"],
            destination_sha256=request["prepared_sha256"],
            signature=row["before"]["signature"],
        )
        if not guard.same_json(row["before"], expected):
            raise guard.Unavailable(
                "Derivative captured pack publication facts changed"
            )


def adoption(writer, token):
    import mylar

    if __package__:
        from .workflow_store import LOCK
    else:
        from workflow_store import LOCK
    database = Path(mylar.DATA_DIR) / "workflow.sqlite"
    with LOCK:
        before = guard.database_stamp(database)
        census, records = guard.registry_snapshot(
            database, writer.root / "publication-v1.json"
        )
        with closing(
            sqlite3.connect(database.as_uri() + "?mode=ro&immutable=1", uri=True)
        ) as db:
            row = db.execute(
                "SELECT value FROM records WHERE kind='publication_intent' AND key=? AND typeof(value)='text' "
                "AND length(CAST(value AS BLOB))<=?",
                (token, guard.REGISTRATION_BYTES),
            ).fetchone()
        if row is None or guard.database_stamp(database) != before:
            raise guard.Unavailable("Derivative adoption journal changed")
        record = guard.decode_json(row[0])
        plan = guard.intent_record(token, record)
        if (
            plan["action"] != "register"
            or plan["binding"]["database_identity"] != before[:2]
            or plan["binding"]["writer_identity"] != guard.writer_identity(writer)
        ):
            raise guard.Unavailable("Derivative adoption journal is foreign")
    body = record["plan"]["body"]
    if record["outcome"] != "committed" or body.get("version") != 2:
        raise guard.Unavailable("Committed exact derivative adoption required")
    _, expected = guard.registration_effect(token, record["plan"])
    if not guard.same_json(census, expected):
        raise guard.Unavailable("Derivative adopted census cannot be refreshed")
    value = dict(body, intent=token)
    if not guard.same_json(records.get(guard.attestation(value)), value):
        raise guard.Unavailable("Committed derivative relation is missing")
    return record, expected


def catalog_row(database, owner):
    with closing(
        sqlite3.connect(Path(database).as_uri() + "?mode=ro&immutable=1", uri=True)
    ) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT * FROM " + owner["table"] + " WHERE IssueID=?", (owner["issueid"],)
        ).fetchmany(2)
    if len(rows) != 1:
        raise guard.Unavailable("Exact derivative catalog row required")
    return dict(rows[0])


def admitted(value, writer):
    if type(value) is not Derivative or getattr(_LOCAL, "value", None) is not value:
        raise guard.Unavailable("Exact active derivative producer required")
    value.check(writer)


class Derivative:
    """A fresh typed invocation, never reconstructed from a stored receipt."""

    def __init__(self, writer, token):
        import mylar
        from mylar import native_writers

        if (
            not native_writers.active()
            or native_writers.owner() is not writer
            or getattr(_LOCAL, "value", None) is not None
            or not guard.digest_value(token)
        ):
            raise guard.Unavailable("Fresh exact native derivative operation required")
        native_writers.admission(writer)
        self.writer = writer
        self.token = token
        self.fd = None
        self.deadline = time.monotonic() + guard.TIMEOUT
        self.path = writer.root / NAME
        self.phase = "prepared"
        if os.path.lexists(self.path):
            raise guard.Unavailable("Interrupted derivative requires retained review")
        self.record, self.census = adoption(writer, token)
        self.body = self.record["plan"]["body"]
        self.plan = self.body["lineage"]["plan"]
        self.request = self.plan["request"]
        prepared_scope(self.request)
        self.source = Path(self.request["source"])
        self.prepared = Path(self.request["prepared"])
        self.owner = self.request["owner"]
        self.database = Path(mylar.DATA_DIR) / "mylar.db"
        self.row = catalog_row(self.database, self.owner)
        if "ComicSize" not in self.row:
            raise guard.Unavailable("Derivative catalog needs complete size column")
        from mylar import publication_native

        proof = publication_native.require(
            self.source,
            issueid=self.owner["issueid"],
            comicid=self.owner["parentcomicid"],
        )
        if (
            not guard.same_json(
                core(proof["inventory"]),
                core(self.plan["facts"]["source"]["inventory"]),
            )
            or not guard.same_json(
                proof["inventory"]["source_signature"],
                self.plan["facts"]["source"]["inventory"]["source_signature"],
            )
            or proof["inventory"]["source_sha256"] != self.request["source_sha256"]
        ):
            raise guard.Unavailable("Adopted derivative original changed")
        if not guard.same_json(
            lineage.private(str(self.prepared)), self.plan["facts"]["prepared"]
        ):
            raise guard.Unavailable("Adopted derivative prepared incarnation changed")
        lineage.migration(self.source, self.prepared, self.request["mapping"])
        if __package__:
            from .publication_transaction import preserved_pair, _write
        else:
            from publication_transaction import preserved_pair, _write
        preserved_pair(self.request["preservation"], self.request["source_sha256"])
        self.source_state = file_state(self.source)
        if not guard.same_json(
            self.source_state["signature"], proof["inventory"]["source_signature"]
        ):
            raise guard.Unavailable("Derivative source changed before captured intent")
        self.pack_bindings = packs(self.request)
        self.history = writer.root / "nested-derivative-completed-v1"
        if not self.history.exists():
            self.history.mkdir(mode=0o700)
        directory = self.history.lstat()
        if (
            directory.st_uid != os.geteuid()
            or stat.S_IMODE(directory.st_mode) != 0o700
            or self.history.is_symlink()
        ):
            raise guard.Unavailable("Private derivative terminal directory required")
        self.value = dict(
            version=1,
            kind="nested-derivative",
            token=token,
            writer=guard.writer_identity(writer),
            adoption=self.record,
            census=self.census,
            source=str(self.source),
            prepared=str(self.prepared),
            source_state=self.source_state,
            row=self.row,
            database=str(self.database),
            output_state=None,
            history=guard.signature(directory)[:2],
            phase="prepared",
            fence=None,
            pack_bindings=self.pack_bindings,
        )
        self._intent_digest = guard.canonical_digest(
            {
                key: value
                for key, value in self.value.items()
                if key not in ("phase", "fence", "output_state")
            }
        )
        _write(self.path, self.value, exclusive=True)
        writer.mark_tagger_pending()
        if __package__:
            from .media_writer import checked_file
        else:
            from media_writer import checked_file
        self.fd = checked_file(writer.tagger_pending)
        self.value.update(fence=guard.signature(os.fstat(self.fd)))
        _write(self.path, self.value, exclusive=False)
        self.evidence = guard.private_evidence(self.path)

    def check(self, writer):
        captured = self.value["adoption"]["plan"]["body"]
        frozen_request = captured["lineage"]["plan"]["request"]
        if (
            self._intent_digest
            != guard.canonical_digest(
                {
                    key: value
                    for key, value in self.value.items()
                    if key not in ("phase", "fence", "output_state")
                }
            )
            or str(self.source) != frozen_request["source"]
            or str(self.prepared) != frozen_request["prepared"]
            or str(self.source) != self.value["source"]
            or str(self.prepared) != self.value["prepared"]
            or str(self.database) != self.value["database"]
            or self.path != writer.root / NAME
            or self.history != writer.root / "nested-derivative-completed-v1"
            or self.phase != self.value["phase"]
            or self.token != self.value["token"]
            or not guard.same_json(self.record, self.value["adoption"])
            or not guard.same_json(self.body, captured)
            or not guard.same_json(self.plan, captured["lineage"]["plan"])
            or not guard.same_json(self.request, frozen_request)
            or not guard.same_json(self.owner, frozen_request["owner"])
            or not guard.same_json(self.census, self.value["census"])
            or not guard.same_json(self.row, self.value["row"])
            or not guard.same_json(self.pack_bindings, self.value["pack_bindings"])
            or not guard.same_json(self.source_state, self.value["source_state"])
            or not guard.same_json(
                getattr(self, "output_state", None), self.value["output_state"]
            )
        ):
            raise guard.Unavailable(
                "Derivative operation facts differ from captured intent"
            )
        if (
            writer is not self.writer
            or not writer.local[1].depth
            or type(self.fd) is not int
            or time.monotonic() >= self.deadline
            or not writer.fenced(tagger=True)
            or writer.fenced()
            or writer.fenced(release=True)
            or guard.writer_identity(writer) != self.value["writer"]
            or guard.signature(os.fstat(self.fd)) != self.value["fence"]
            or guard.signature(writer.tagger_pending.lstat()) != self.value["fence"]
            or guard.private_evidence(self.path) != self.evidence
            or not guard.same_json(guard.private_json(self.path), self.value)
            or guard.signature(self.history.lstat())[:2] != self.value["history"]
        ):
            raise guard.Unavailable("Derivative active capability changed")
        record, census = adoption(writer, self.token)
        if not guard.same_json(record, self.record) or not guard.same_json(
            census, self.census
        ):
            raise guard.Unavailable("Derivative adoption or expected census changed")

    def observation_path(self, path):
        return Path(path)

    @contextmanager
    def owned(self):
        if getattr(_LOCAL, "value", None) is not None:
            raise guard.Unavailable("Nested derivative capability")
        _LOCAL.value = self
        try:
            yield self
        finally:
            _LOCAL.value = None
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None

    def checkpoint(self):
        import mylar
        from mylar import publication_native

        if __package__:
            from .publication_transaction import preserved_pair
        else:
            from publication_transaction import preserved_pair
        admitted(self, self.writer)
        preserved_pair(self.request["preservation"], self.request["source_sha256"])
        if not guard.same_json(
            lineage.private(str(self.prepared)), self.plan["facts"]["prepared"]
        ):
            raise guard.Unavailable("Derivative prepared archive changed")
        state = file_state(self.source)
        expected = self.source_state if self.phase == "prepared" else self.output_state
        required_sha = (
            self.request["source_sha256"]
            if self.phase == "prepared"
            else self.request["prepared_sha256"]
        )
        original = self.source_state["signature"]
        if (
            state["sha256"] != required_sha
            or state["attributes"] != self.source_state["attributes"]
            or state["signature"][3] != original[3]
            or state["signature"][5:8] != original[5:8]
            or not guard.same_json(state, expected)
        ):
            raise guard.Unavailable("Derivative current archive changed")
        inventory = guard.inventory(self.source)
        required = (
            core(self.plan["facts"]["source"]["inventory"])
            if self.phase == "prepared"
            else core(self.plan["facts"]["derivative"])
        )
        if not guard.same_json(core(inventory), required):
            raise guard.Unavailable("Derivative exact member lineage changed")
        proof = publication_native.require(
            self.source,
            issueid=self.owner["issueid"],
            comicid=self.owner["parentcomicid"],
            transaction=self,
        )
        selected = guard.observe_owners(
            self.database,
            self.writer,
            [self.owner],
            [mylar.CONFIG.DESTINATION_DIR],
            transaction=self,
        )["observed"]
        if proof["owner"] != self.owner or selected[0]["catalog"]["path"] != str(
            self.source
        ):
            raise guard.Unavailable("Derivative current catalog ownership changed")
        expected_row = dict(self.row)
        if self.phase in ("cataloged", "committed"):
            expected_row["ComicSize"] = state["signature"][2]
        if not guard.same_json(catalog_row(self.database, self.owner), expected_row):
            raise guard.Unavailable("Derivative full catalog row changed")
        preserved_pair(self.request["preservation"], self.request["source_sha256"])
        if not guard.same_json(file_state(self.source), state):
            raise guard.Unavailable(
                "Derivative source changed during final owner proof"
            )
        admitted(self, self.writer)
        if self.phase == "prepared" and not guard.same_json(
            packs(self.request), self.pack_bindings
        ):
            raise guard.Unavailable(
                "Derivative confirmed pack bindings changed before publication"
            )
        return selected

    def phase_to(self, phase, *, output_state=None):
        if __package__:
            from .publication_transaction import _write
        else:
            from publication_transaction import _write
        admitted(self, self.writer)
        transitions = {
            "prepared": "published",
            "published": "cataloged",
            "cataloged": "committed",
        }
        if (
            transitions.get(self.phase) != phase
            or ((output_state is not None) != (phase == "published"))
            or (
                phase == "published"
                and (
                    self.value["output_state"] is not None
                    or output_state["sha256"] != self.request["prepared_sha256"]
                    or output_state["attributes"] != self.source_state["attributes"]
                )
            )
        ):
            raise guard.Unavailable(
                "Derivative phase and output capture cannot be resealed"
            )
        self.phase = phase
        self.value = dict(self.value, phase=phase)
        if output_state is not None:
            self.output_state = guard.decode_json(guard.compact(output_state))
            self.value["output_state"] = self.output_state
        _write(self.path, self.value, exclusive=False)
        self.evidence = guard.private_evidence(self.path)

    def publish(self, boundary):
        if __package__:
            from . import tagger_attributes
            from .media_writer import sync
            from .publication_transaction import _write
        else:
            import tagger_attributes
            from media_writer import sync
            from publication_transaction import _write
        self.checkpoint()
        boundary("prepared")
        self.checkpoint()
        temporary = self.source.parent / (".nested-derivative-" + self.token + ".tmp")
        if (
            shutil.disk_usage(self.source.parent).free
            < self.prepared.stat().st_size + 128 * 1024**2
        ):
            raise guard.Unavailable("Insufficient derivative preservation space")
        with guard.regular(self.prepared) as incoming, temporary.open("xb") as out:
            shutil.copyfileobj(incoming, out, 1024**2)
            out.flush()
            os.fsync(out.fileno())
        original = self.source_state["signature"]
        os.chown(temporary, original[6], original[7])
        os.chmod(temporary, stat.S_IMODE(original[5]))
        tagger_attributes.apply(temporary, self.source_state["attributes"])
        os.utime(temporary, ns=(self.source.stat().st_atime_ns, original[3]))
        with guard.regular(temporary) as stage:
            os.fsync(stage.fileno())
        staged = file_state(temporary)
        if staged["sha256"] != self.request["prepared_sha256"]:
            raise guard.Unavailable("Derivative staged bytes changed")
        self.checkpoint()
        boundary("copy")
        self.checkpoint()
        if not guard.same_json(file_state(temporary), staged):
            raise guard.Unavailable(
                "Derivative staged archive changed before publication"
            )
        os.replace(temporary, self.source)
        sync(self.source.parent)
        output_state = file_state(self.source)
        if (
            output_state["sha256"] != self.request["prepared_sha256"]
            or output_state["attributes"] != self.source_state["attributes"]
            or output_state["signature"][3] != original[3]
            or output_state["signature"][5:8] != original[5:8]
        ):
            raise guard.Unavailable("Derivative access attributes changed")
        self.phase_to("published", output_state=output_state)
        self.checkpoint()
        boundary("published")
        self.checkpoint()
        with closing(sqlite3.connect(self.database)) as db:
            db.execute("BEGIN IMMEDIATE")
            db.row_factory = sqlite3.Row
            actual = db.execute(
                "SELECT * FROM " + self.owner["table"] + " WHERE IssueID=?",
                (self.owner["issueid"],),
            ).fetchone()
            if actual is None or not guard.same_json(dict(actual), self.row):
                raise guard.Unavailable("Derivative catalog CAS changed")
            changed = db.execute(
                "UPDATE "
                + self.owner["table"]
                + " SET ComicSize=? WHERE IssueID=? AND ComicID=? AND Location=? AND Status=?",
                (
                    self.output_state["signature"][2],
                    self.owner["issueid"],
                    self.owner["parentcomicid"],
                    self.row["Location"],
                    self.row["Status"],
                ),
            )
            if changed.rowcount != 1:
                raise guard.Unavailable("Derivative catalog CAS failed")
            db.commit()
        self.phase_to("cataloged")
        self.checkpoint()
        boundary("cataloged")
        self.checkpoint()
        if __package__:
            from . import pack_bindings
        else:
            import pack_bindings
        import mylar
        from mylar import native_writers

        pack_bindings.finalize(
            native_writers.existing_store(mylar.DATA_DIR),
            self.pack_bindings,
            self.request["prepared_sha256"],
            catalog_owner={
                "issueid": self.owner["issueid"],
                "comicid": self.owner["parentcomicid"],
            },
        )
        self.checkpoint()
        current_packs = packs(self.request)
        packed_after(self.pack_bindings, current_packs, self.request)
        self.phase_to("committed")
        observed = self.checkpoint()
        witness = dict(
            version=1,
            kind="nested-derivative-terminal",
            token=self.token,
            intent=self.value,
            output=self.output_state,
            observed=observed,
            preservation=self.request["preservation"],
            pack_publication=current_packs,
        )
        _write(self.history / (self.token + ".json"), witness, exclusive=True)
        terminal_evidence = guard.private_evidence(
            self.history / (self.token + ".json")
        )
        import mylar
        from mylar import native_writers

        store = native_writers.existing_store(mylar.DATA_DIR)
        terminal = dict(
            version=1,
            token=self.token,
            witness=guard.canonical_digest(witness),
            phase="committed",
        )
        if store.get("nested_derivative", self.token) is not None:
            raise guard.Unavailable("Derivative terminal journal collision")
        store.set("nested_derivative", self.token, terminal)
        boundary("witness")
        self.checkpoint()
        catalog_evidence = guard.file_hash(self.database)
        final_terminal = store.get("nested_derivative", self.token)
        if __package__:
            from .publication_transaction import preserved_pair
        else:
            from publication_transaction import preserved_pair
        preserved_pair(self.request["preservation"], self.request["source_sha256"])
        if (
            guard.private_evidence(self.history / (self.token + ".json"))
            != terminal_evidence
            or not guard.same_json(
                guard.private_json(self.history / (self.token + ".json")), witness
            )
            or not guard.same_json(final_terminal, terminal)
            or not guard.same_json(packs(self.request), current_packs)
            or not guard.same_json(guard.file_hash(self.database), catalog_evidence)
            or not guard.same_json(file_state(self.source), self.output_state)
        ):
            raise guard.Unavailable("Derivative terminal witness changed")
        try:
            self.writer.clear_tagger_pending()
            self.path.unlink()
            sync(self.writer.root)
        except BaseException:
            # Restore exclusion after an uncertain final removal/fsync. These
            # receipts are recovery evidence, never a recreated capability.
            if not self.writer.fenced(tagger=True):
                self.writer.mark_tagger_pending()
            if not os.path.lexists(self.path):
                _write(self.path, self.value, exclusive=True)
            raise
        return dict(
            version=1,
            token=self.token,
            phase="committed",
            source=str(self.source),
            before=self.request["source_sha256"],
            after=self.request["prepared_sha256"],
            witness=terminal["witness"],
            census=self.census,
        )


@guard.state_errors
def publish(writer, token, *, boundary=lambda _: None):
    capability = Derivative(writer, token)
    with capability.owned():
        return capability.publish(boundary)


@guard.state_errors
def status(writer, token):
    import mylar
    from mylar import native_writers

    native_writers.admission(writer)
    if os.path.lexists(writer.root / NAME):
        raise guard.Unavailable("Derivative pending receipt requires review")
    record, census = adoption(writer, token)
    request = record["plan"]["body"]["lineage"]["plan"]["request"]
    target = writer.root / "nested-derivative-completed-v1" / (token + ".json")
    evidence = guard.private_evidence(target)
    witness = guard.private_json(target)
    terminal = native_writers.existing_store(mylar.DATA_DIR).get(
        "nested_derivative", token
    )
    if not isinstance(witness, dict):
        raise guard.Unavailable("Exact derivative terminal witness required")
    intent = witness.get("intent")
    output = witness.get("output")
    if (
        not isinstance(witness, dict)
        or set(witness)
        != {
            "version",
            "kind",
            "token",
            "intent",
            "output",
            "observed",
            "preservation",
            "pack_publication",
        }
        or type(witness["version"]) is not int
        or witness["version"] != 1
        or not isinstance(intent, dict)
        or set(intent)
        != {
            "version",
            "kind",
            "token",
            "writer",
            "adoption",
            "census",
            "source",
            "prepared",
            "source_state",
            "row",
            "database",
            "output_state",
            "history",
            "phase",
            "fence",
            "pack_bindings",
        }
        or type(intent["version"]) is not int
        or intent["version"] != 1
        or intent["kind"] != "nested-derivative"
        or intent["token"] != token
        or intent["source"] != request["source"]
        or intent["prepared"] != request["prepared"]
        or intent["database"] != str(Path(mylar.DATA_DIR) / "mylar.db")
        or not guard.same_json(intent["writer"], guard.writer_identity(writer))
        or not guard.same_json(
            intent["history"], guard.signature(target.parent.lstat())[:2]
        )
        or not guard.same_json(intent["census"], census)
        or not guard.same_json(witness["preservation"], request["preservation"])
        or not isinstance(output, dict)
        or set(output) != {"signature", "sha256", "attributes"}
        or output["sha256"] != request["prepared_sha256"]
        or not guard.same_json(output, intent["output_state"])
        or not isinstance(intent["source_state"], dict)
        or set(intent["source_state"]) != {"signature", "sha256", "attributes"}
        or intent["source_state"]["sha256"] != request["source_sha256"]
        or not guard.same_json(
            intent["source_state"]["signature"],
            record["plan"]["body"]["lineage"]["plan"]["facts"]["source"]["inventory"][
                "source_signature"
            ],
        )
        or not guard.same_json(
            output["attributes"], intent["source_state"]["attributes"]
        )
    ):
        raise guard.Unavailable(
            "Exact derivative terminal output and intent binding required"
        )
    stamp(output["signature"])
    stamp(intent["fence"])
    original_signature = intent["source_state"]["signature"]
    if (
        output["signature"][3] != original_signature[3]
        or output["signature"][5:8] != original_signature[5:8]
        or output["signature"][8] != 1
    ):
        raise guard.Unavailable("Derivative terminal original attributes changed")
    if __package__:
        from . import tagger_attributes
    else:
        import tagger_attributes
    tagger_attributes.validate(output["attributes"])
    if __package__:
        from . import pack_bindings
    else:
        import pack_bindings
    pack_bindings.validate(intent["pack_bindings"])
    pack_bindings.validate(witness["pack_publication"])
    packed_after(intent["pack_bindings"], witness["pack_publication"], request)
    observed_fact(witness["observed"])
    if (
        len(witness["observed"]) != 1
        or witness["observed"][0]["owner"] != request["owner"]
        or witness["observed"][0]["catalog"]["path"] != request["source"]
        or witness["observed"][0]["source_sha256"] != request["prepared_sha256"]
        or not guard.same_json(witness["observed"][0]["signature"], output["signature"])
    ):
        raise guard.Unavailable(
            "Exact derivative terminal current owner binding required"
        )
    if (
        terminal
        != dict(
            version=1,
            token=token,
            witness=guard.canonical_digest(witness),
            phase="committed",
        )
        or witness.get("kind") != "nested-derivative-terminal"
        or witness.get("token") != token
        or not guard.same_json(witness["intent"]["adoption"], record)
        or witness["intent"]["phase"] != "committed"
    ):
        raise guard.Unavailable("Derivative terminal lineage requires review")
    from mylar import publication_native

    publication_native.require(
        request["source"],
        issueid=request["owner"]["issueid"],
        comicid=request["owner"]["parentcomicid"],
    )
    current = guard.observe_owners(
        Path(mylar.DATA_DIR) / "mylar.db",
        writer,
        [request["owner"]],
        [mylar.CONFIG.DESTINATION_DIR],
    )["observed"]
    native_writers.admission(writer)
    final_record, final_census = adoption(writer, token)
    if not guard.same_json(final_record, record) or not guard.same_json(
        final_census, census
    ):
        raise guard.Unavailable("Derivative terminal expected census changed")
    final_terminal = native_writers.existing_store(mylar.DATA_DIR).get(
        "nested_derivative", token
    )
    final_row = catalog_row(Path(mylar.DATA_DIR) / "mylar.db", request["owner"])
    if __package__:
        from .publication_transaction import preserved_pair
    else:
        from publication_transaction import preserved_pair
    preserved_pair(request["preservation"], request["source_sha256"])
    expected_row = dict(
        witness["intent"]["row"], ComicSize=witness["output"]["signature"][2]
    )
    if (
        guard.private_evidence(target) != evidence
        or not guard.same_json(guard.private_json(target), witness)
        or not guard.same_json(current, witness["observed"])
        or not guard.same_json(final_row, expected_row)
        or final_terminal != terminal
        or not guard.same_json(packs(request), witness["pack_publication"])
        or not guard.same_json(file_state(request["source"]), witness["output"])
    ):
        raise guard.Unavailable(
            "Derivative terminal evidence changed during final admission"
        )
    return dict(
        version=1,
        token=token,
        phase="committed",
        source=request["source"],
        before=request["source_sha256"],
        after=request["prepared_sha256"],
        witness=terminal["witness"],
        census=census,
    )
