"""Native exact derivative registry and typed producer controls."""

import copy
import json
from contextlib import contextmanager
from pathlib import Path
import unittest
import shutil
import zipfile
import importlib.util
import media_writer
import pack_bindings
from unittest.mock import patch
import publication_native as native

import publication_api as api
import publication_derivative as derivative
import publication_guard as guard
import test_publication_lineage as fixtures


class DerivativeTests(unittest.TestCase):
    def setUp(self):
        fixtures.LineageTests.setUp(self)
        cache = self.root / "cache"
        cache.mkdir(mode=0o700)
        self.mylar.CONFIG.CACHE_DIR = str(cache)
        staging = cache / "nested-derivatives"
        staging.mkdir(mode=0o700)
        stage = staging / derivative.stage_token(self.request)
        stage.mkdir(mode=0o700)
        target = stage / "prepared.cbz"
        self.derivative.rename(target)
        self.derivative = target
        self.request["prepared"] = str(target)
        self.refresh_review()

        @contextmanager
        def operation():
            with self.writer.hold(
                allow_pending=True,
                allow_tagger_pending=True,
                allow_release_pending=True,
            ):
                self.runtime.admission(self.writer)
                yield self.writer

        self.runtime.operation = operation

    connection = fixtures.LineageTests.connection
    call = fixtures.LineageTests.call
    bootstrap = fixtures.LineageTests.bootstrap
    prepare = fixtures.LineageTests.prepare
    registered = fixtures.LineageTests.registered
    document = fixtures.LineageTests.document
    refresh_review = fixtures.LineageTests.refresh_review
    capture_backup = fixtures.LineageTests.capture_backup
    plan = fixtures.LineageTests.plan

    def api_controller(self):
        return api.Controller(self.root, [self.library])

    def adoption(self, plan=None):
        plan = plan or self.plan()
        controller = self.api_controller()
        prepared = controller.dispatch(
            api.request(
                json.dumps(
                    dict(
                        version=1, action="prepare-derivative", lineage=plan, created=1
                    )
                )
            )
        )
        adopted = controller.dispatch(
            api.request(
                json.dumps(
                    dict(version=1, action="adopt-derivative", token=prepared["token"])
                )
            )
        )
        return prepared, adopted

    def confirmed_packs(self):
        for key in ("a" * 64, "b" * 64, "c" * 64):
            self.store.set(
                "pack",
                key,
                dict(
                    id=key,
                    phase="confirmed",
                    inventory_complete=True,
                    cleanup_complete=True,
                    members=[
                        dict(
                            id="d" * 64,
                            kind="issue",
                            phase="confirmed",
                            issueid=self.owner["issueid"],
                            comicid=self.owner["parentcomicid"],
                            destination=str(self.source),
                            destination_sha256=self.request["source_sha256"],
                            signature=pack_bindings.signature(self.source),
                        ),
                        dict(
                            id="e" * 64,
                            kind="sidecar",
                            phase="preserved",
                            sidecar="retained release evidence",
                        ),
                    ],
                ),
            )
        self.backupdir.rename(self.root / "prior-pack-backup")
        self.restoredir.rename(self.root / "prior-pack-restore")
        self.capture_backup()

    def test_three_confirmed_pack_members_rebound_before_terminal_ack(self):
        self.confirmed_packs()
        before = self.store.get("pack", "a" * 64)
        self.runtime.existing_store = lambda _: self.store
        prepared, _ = self.adoption()
        with self.runtime.operation() as writer:
            result = derivative.publish(writer, prepared["token"])
        for key in ("a" * 64, "b" * 64, "c" * 64):
            record = self.store.get("pack", key)
            self.assertEqual(
                record["members"][0]["destination_sha256"],
                self.request["prepared_sha256"],
            )
            self.assertEqual(
                record["members"][0]["signature"], pack_bindings.signature(self.source)
            )
            self.assertEqual(record["members"][1], before["members"][1])
            self.assertTrue(record["inventory_complete"] and record["cleanup_complete"])
        with self.runtime.operation() as writer:
            self.assertEqual(derivative.status(writer, prepared["token"]), result)

    def test_foreign_confirmed_pack_member_holds_before_media_mutation(self):
        self.confirmed_packs()
        record = self.store.get("pack", "a" * 64)
        record["members"][0]["issueid"] = "999"
        self.store.set("pack", "a" * 64, record)
        self.backupdir.rename(self.root / "prior-foreign-backup")
        self.restoredir.rename(self.root / "prior-foreign-restore")
        self.capture_backup()
        self.runtime.existing_store = lambda _: self.store
        prepared, _ = self.adoption()
        before = self.source.read_bytes()
        with self.runtime.operation() as writer, self.assertRaises(guard.Unavailable):
            derivative.publish(writer, prepared["token"])
        self.assertEqual(self.source.read_bytes(), before)
        self.assertFalse((self.writer.root / derivative.NAME).exists())

    def test_confirmed_pack_member_change_during_publication_retains_fence(self):
        self.confirmed_packs()
        self.runtime.existing_store = lambda _: self.store
        prepared, _ = self.adoption()

        def change(phase):
            if phase == "cataloged":
                record = self.store.get("pack", "a" * 64)
                record["members"][0]["destination_sha256"] = "a" * 64
                self.store.set("pack", "a" * 64, record)

        with self.runtime.operation() as writer, self.assertRaises(guard.Unavailable):
            derivative.publish(writer, prepared["token"], boundary=change)
        self.assertTrue(self.writer.fenced(tagger=True))
        self.assertEqual(
            self.store.get("pack", "a" * 64)["members"][0]["destination_sha256"],
            "a" * 64,
        )

    def test_passive_ack_rechecks_confirmed_pack_bindings(self):
        self.confirmed_packs()
        self.runtime.existing_store = lambda _: self.store
        prepared, _ = self.adoption()
        with self.runtime.operation() as writer:
            derivative.publish(writer, prepared["token"])
        record = self.store.get("pack", "a" * 64)
        record["members"][0]["signature"] = [0] * 5
        self.store.set("pack", "a" * 64, record)
        with self.runtime.operation() as writer, self.assertRaises(guard.Unavailable):
            derivative.status(writer, prepared["token"])

    def test_unknown_exact_relation_allows_only_owner_before_any_media_publication(
        self,
    ):
        before = self.source.read_bytes()
        prepared, adopted = self.adoption()
        self.assertEqual(adopted["outcome"], "committed")
        self.assertEqual(adopted["census"]["revision"], 1)
        self.assertEqual(self.source.read_bytes(), before)
        controller = self.api_controller()
        payload = guard.inventory(self.derivative)["payload"]
        for candidate, decision in (
            (self.owner, "allowed"),
            (dict(self.owner, issueid="999"), "held"),
        ):
            with self.writer.hold():
                result = controller._check(
                    dict(payload=payload, owner=candidate), self.writer
                )
            self.assertEqual(result["decision"], decision)
        self.assertEqual(
            controller.dispatch(
                dict(version=1, action="adopt-derivative", token=prepared["token"])
            )["outcome"],
            "committed",
        )

    def test_actual_reviewed_lineage_route_through_adoption_and_publication(self):
        before = (self.source.read_bytes(), self.store.path.read_bytes())
        response = self.api_controller().dispatch(
            api.request(
                json.dumps(
                    dict(version=1, action="prepare-lineage", request=self.request)
                )
            )
        )
        self.assertEqual(response["outcome"], "reviewed")
        self.assertFalse(response["executable"])
        self.assertEqual(
            before, (self.source.read_bytes(), self.store.path.read_bytes())
        )
        prepared, _ = self.adoption(response["lineage"])
        self.runtime.existing_store = lambda _: self.store
        with self.runtime.operation() as writer:
            derivative.publish(writer, prepared["token"])
        self.assertEqual(self.source.read_bytes(), self.derivative.read_bytes())

    def test_lineage_route_refuses_unconfigured_stage_and_sanitizes_actual_owner_review(
        self,
    ):
        request = copy.deepcopy(self.request)
        request["prepared"] = str(self.private / "unconfigured.cbz")
        with self.assertRaises(guard.Unavailable):
            self.api_controller().dispatch(
                api.request(
                    json.dumps(
                        dict(version=1, action="prepare-lineage", request=request)
                    )
                )
            )
        with self.connection() as db:
            db.execute(
                "UPDATE issues SET ComicID='different' WHERE IssueID=?",
                (self.owner["issueid"],),
            )
        with self.assertRaisesRegex(
            guard.Unavailable, "requires current-source review"
        ):
            self.api_controller().dispatch(
                api.request(
                    json.dumps(
                        dict(version=1, action="prepare-lineage", request=self.request)
                    )
                )
            )

    def test_v1_registration_route_cannot_adopt_derivative_token(self):
        plan = self.plan()
        controller = self.api_controller()
        prepared = controller.dispatch(
            dict(version=1, action="prepare-derivative", lineage=plan, created=1)
        )
        with self.assertRaises(guard.Unavailable):
            controller.dispatch(
                dict(version=1, action="register", token=prepared["token"])
            )

    def test_prepared_relation_never_refreshes_source_owner_or_census(self):
        controller = self.api_controller()
        plan = self.plan()
        prepared = controller.dispatch(
            dict(version=1, action="prepare-derivative", lineage=plan, created=1)
        )
        self.source.write_bytes(b"changed protected source")
        with self.assertRaises(guard.Unavailable):
            controller.dispatch(
                dict(version=1, action="adopt-derivative", token=prepared["token"])
            )
        self.assertEqual(
            guard.registry_snapshot(
                self.store.path, self.writer.root / "publication-v1.json"
            )[0]["revision"],
            0,
        )

    def test_incomplete_mapping_inventory_or_plan_facts_are_not_relations(self):
        plan = self.plan()
        controller = self.api_controller()
        bad = copy.deepcopy(plan)
        bad["facts"]["derivative"]["members"].pop()
        bad["token"] = guard.canonical_digest(
            {key: value for key, value in bad.items() if key != "token"}
        )
        with self.assertRaises(guard.Unavailable):
            controller.dispatch(
                api.request(
                    json.dumps(
                        dict(
                            version=1,
                            action="prepare-derivative",
                            lineage=bad,
                            created=1,
                        )
                    )
                )
            )
        self.assertEqual(
            self.source.read_bytes(),
            Path(self.request["preservation"]["original"]["path"]).read_bytes(),
        )

    def test_actual_typed_unknown_producer_and_passive_ack_preserve_originals(self):
        prepared, _ = self.adoption()
        before = self.source.read_bytes()
        self.runtime.existing_store = lambda _: self.store
        with self.runtime.operation() as writer:
            result = derivative.publish(writer, prepared["token"])
        self.assertEqual(self.source.read_bytes(), self.derivative.read_bytes())
        self.assertEqual(
            Path(self.request["preservation"]["original"]["path"]).read_bytes(), before
        )
        self.assertFalse(self.writer.fenced(tagger=True))
        with self.runtime.operation() as writer:
            self.assertEqual(derivative.status(writer, prepared["token"]), result)

    def test_producer_boundary_drift_retains_changed_source_and_fence(self):
        prepared, _ = self.adoption()
        self.runtime.existing_store = lambda _: self.store

        def change(phase):
            if phase == "copy":
                self.source.write_bytes(b"changed protected original")

        with (
            self.runtime.operation() as writer,
            self.assertRaises((guard.Unavailable, native.Review)),
        ):
            derivative.publish(writer, prepared["token"], boundary=change)
        self.assertEqual(self.source.read_bytes(), b"changed protected original")
        self.assertTrue(self.writer.fenced(tagger=True))
        self.assertTrue((self.writer.root / derivative.NAME).exists())

    def test_copy_boundary_replaced_stage_cannot_overwrite_protected_source(self):
        prepared, _ = self.adoption()
        self.runtime.existing_store = lambda _: self.store
        before = self.source.read_bytes()

        def replace(phase):
            if phase == "copy":
                stage = self.source.parent / (
                    ".nested-derivative-" + prepared["token"] + ".tmp"
                )
                stage.write_bytes(b"changed untrusted staged archive")

        with (
            self.runtime.operation() as writer,
            self.assertRaisesRegex(guard.Unavailable, "staged archive"),
        ):
            derivative.publish(writer, prepared["token"], boundary=replace)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertTrue(self.writer.fenced(tagger=True))

    def test_published_capability_cannot_reseal_changed_same_payload_output(self):
        prepared, _ = self.adoption()
        self.runtime.existing_store = lambda _: self.store

        def reseal(phase):
            if phase == "published":
                with zipfile.ZipFile(self.source, "a") as archive:
                    archive.comment = b"changed archive envelope"
                capability = derivative._LOCAL.value
                capability.phase_to(
                    "published", output_state=derivative.file_state(self.source)
                )

        with (
            self.runtime.operation() as writer,
            self.assertRaisesRegex(guard.Unavailable, "cannot be resealed"),
        ):
            derivative.publish(writer, prepared["token"], boundary=reseal)
        self.assertNotEqual(
            guard.file_hash(self.source)[1], self.request["prepared_sha256"]
        )
        self.assertTrue(self.writer.fenced(tagger=True))
        self.assertTrue((self.writer.root / derivative.NAME).exists())

    def test_passive_final_read_cannot_ack_replaced_retained_original(self):
        prepared, _ = self.adoption()
        self.runtime.existing_store = lambda _: self.store
        with self.runtime.operation() as writer:
            derivative.publish(writer, prepared["token"])
        actual = native.require

        def change(*args, **kwargs):
            result = actual(*args, **kwargs)
            Path(self.request["preservation"]["original"]["path"]).write_bytes(
                b"changed private original"
            )
            return result

        with (
            self.runtime.operation() as writer,
            patch.object(native, "require", side_effect=change),
            self.assertRaises(guard.Unavailable),
        ):
            derivative.status(writer, prepared["token"])

    def test_passive_final_journal_read_source_change_cannot_get_ack(self):
        prepared, _ = self.adoption()
        self.runtime.existing_store = lambda _: self.store
        with self.runtime.operation() as writer:
            derivative.publish(writer, prepared["token"])
        real = self.store.get
        count = 0

        def change(kind, key, default=None):
            nonlocal count
            result = real(kind, key, default)
            if kind == "nested_derivative":
                count += 1
                if count == 2:
                    self.source.write_bytes(
                        b"changed during final independent journal read"
                    )
            return result

        with (
            self.runtime.operation() as writer,
            patch.object(self.store, "get", side_effect=change),
            self.assertRaisesRegex(guard.Unavailable, "final admission"),
        ):
            derivative.status(writer, prepared["token"])
        self.assertEqual(count, 2)
        self.assertEqual(
            self.source.read_bytes(), b"changed during final independent journal read"
        )

    def test_producer_final_journal_read_source_change_retains_fence(self):
        prepared, _ = self.adoption()
        self.runtime.existing_store = lambda _: self.store
        real = self.store.get
        count = 0

        def change(kind, key, default=None):
            nonlocal count
            result = real(kind, key, default)
            if kind == "nested_derivative":
                count += 1
                if count == 2:
                    self.source.write_bytes(
                        b"changed during producer final journal read"
                    )
            return result

        with (
            self.runtime.operation() as writer,
            patch.object(self.store, "get", side_effect=change),
            self.assertRaisesRegex(guard.Unavailable, "terminal witness"),
        ):
            derivative.publish(writer, prepared["token"])
        self.assertEqual(count, 2)
        self.assertEqual(
            self.source.read_bytes(), b"changed during producer final journal read"
        )
        self.assertTrue(self.writer.fenced(tagger=True))
        self.assertTrue((self.writer.root / derivative.NAME).exists())

    def test_mutable_capability_source_cannot_redirect_a_protected_copy(self):
        prepared, _ = self.adoption()
        self.runtime.existing_store = lambda _: self.store
        protected = Path(self.request["preservation"]["original"]["path"])
        before = protected.read_bytes()

        def redirect(phase):
            if phase == "copy":
                capability = derivative._LOCAL.value
                capability.source = protected
                capability.source_state = derivative.file_state(protected)

        with (
            self.runtime.operation() as writer,
            self.assertRaisesRegex(guard.Unavailable, "operation facts"),
        ):
            derivative.publish(writer, prepared["token"], boundary=redirect)
        self.assertEqual(protected.read_bytes(), before)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertTrue(self.writer.fenced(tagger=True))

    def test_registered_relation_inherits_wrong_claims_before_and_after_publication(
        self,
    ):
        registered = self.prepare(census=self.request["census"])
        committed = self.call("register", token=registered["token"])
        self.request["census"] = committed["census"]
        self.refresh_review()
        self.backupdir.rename(self.root / "previous-backup")
        self.restoredir.rename(self.root / "previous-restore")
        self.capture_backup()
        prepared, _ = self.adoption()
        self.runtime.existing_store = lambda _: self.store
        rejected = dict(
            table="issues", issueid="999", parentcomicid="888", releasecomicid="888"
        )
        payloads = [
            guard.inventory(self.source)["payload"],
            guard.inventory(self.derivative)["payload"],
        ]
        controller = self.api_controller()
        for payload in payloads:
            with self.writer.hold():
                self.assertEqual(
                    controller._check(
                        dict(payload=payload, owner=rejected), self.writer
                    )["decision"],
                    "held",
                )
        with self.runtime.operation() as writer:
            derivative.publish(writer, prepared["token"])
        for payload in payloads:
            with self.writer.hold():
                self.assertEqual(
                    controller._check(
                        dict(payload=payload, owner=rejected), self.writer
                    )["decision"],
                    "held",
                )
                self.assertEqual(
                    controller._check(
                        dict(payload=payload, owner=self.owner), self.writer
                    )["decision"],
                    "allowed",
                )

    def test_prepared_old_adoption_recovers_only_exact_verified_derivative(self):
        controller = self.api_controller()
        plan = self.plan()
        prepared = controller.dispatch(
            dict(version=1, action="prepare-derivative", lineage=plan, created=1)
        )
        state = guard.RegistrationState(self.store.path, self.writer)

        def crash(phase):
            if phase == "prepared-marker":
                raise OSError("isolated crash")

        with self.assertRaises(guard.Unavailable):
            state.register(
                prepared["token"],
                accepted_token=prepared["token"],
                observe=lambda body: derivative.registration_observe(self.writer, body),
                boundary=crash,
            )
        with self.assertRaises(guard.Unavailable):
            guard.registry_snapshot(
                self.store.path, self.writer.root / "publication-v1.json"
            )
        recovered = controller.dispatch(
            dict(
                version=1,
                action="recover-derivative",
                token=prepared["token"],
                mode="finish",
            )
        )
        self.assertEqual(recovered["outcome"], "committed")
        self.assertEqual(recovered["census"]["revision"], 1)

    def test_committed_database_adoption_recovers_marker_without_media_replay(self):
        controller = self.api_controller()
        plan = self.plan()
        before = self.source.read_bytes()
        prepared = controller.dispatch(
            dict(version=1, action="prepare-derivative", lineage=plan, created=1)
        )
        state = guard.RegistrationState(self.store.path, self.writer)

        def crash(phase):
            if phase == "sqlite-committed":
                raise OSError("isolated crash")

        with self.assertRaises(guard.Unavailable):
            state.register(
                prepared["token"],
                accepted_token=prepared["token"],
                observe=lambda body: derivative.registration_observe(self.writer, body),
                boundary=crash,
            )
        recovered = controller.dispatch(
            dict(
                version=1,
                action="recover-derivative",
                token=prepared["token"],
                mode="finish",
            )
        )
        self.assertEqual(recovered["outcome"], "committed")
        self.assertEqual(self.source.read_bytes(), before)

    def test_rootless_nested_metadata_adds_only_exact_verified_root(self):
        import metadata_repair

        with zipfile.ZipFile(self.source) as archive:
            rows = [
                (info, archive.read(info))
                for info in archive.infolist()
                if info.filename != "ComicInfo.xml"
            ]
            comment = archive.comment
        with zipfile.ZipFile(self.source, "w") as archive:
            archive.comment = comment
            for info, data in rows:
                archive.writestr(info, data)
        output = self.private / "rootless-prepared.cbz"
        metadata_repair.prepare(self.source, output)
        output.chmod(0o600)
        self.request["source_sha256"] = guard.file_hash(self.source)[1]
        self.request["prepared_sha256"] = guard.file_hash(output)[1]
        stage = (
            Path(self.mylar.CONFIG.CACHE_DIR)
            / "nested-derivatives"
            / derivative.stage_token(self.request)
        )
        stage.mkdir(mode=0o700)
        self.derivative = stage / "prepared.cbz"
        output.rename(self.derivative)
        self.request["prepared"] = str(self.derivative)
        for row in self.request["preservation"].values():
            shutil.copyfile(self.source, row["path"])
            row["signature"] = guard.file_hash(row["path"])[0]
        self.refresh_review()
        self.backupdir.rename(self.root / "prior-backup")
        self.restoredir.rename(self.root / "prior-restore")
        self.capture_backup()
        plan = self.plan()
        self.assertNotIn(
            "ComicInfo.xml",
            [row["name"] for row in plan["facts"]["source"]["inventory"]["members"]],
        )
        prepared, _ = self.adoption(plan)
        self.runtime.existing_store = lambda _: self.store
        with self.runtime.operation() as writer:
            derivative.publish(writer, prepared["token"])
        with zipfile.ZipFile(self.source) as archive:
            self.assertEqual(
                archive.read("metadata/SourceMetadata.xml"),
                next(
                    data
                    for info, data in rows
                    if info.filename == "metadata/ComicInfo.xml"
                ),
            )
            self.assertIn(b"<Writer>Writer</Writer>", archive.read("ComicInfo.xml"))

    def test_retokened_incomplete_or_malformed_facts_cannot_enter_registry(self):
        original = self.plan()
        before = (self.source.read_bytes(), self.store.path.read_bytes())
        changes = [
            lambda p: p["facts"]["writer"].__setitem__(0, True),
            lambda p: p["facts"]["prepared"]["signature"].__setitem__(0, True),
            lambda p: p["facts"]["source"]["inventory"].__setitem__("extra", 1),
            lambda p: p["facts"]["migration"]["member_order"].pop(),
            lambda p: p["facts"]["migration"]["derivative_order"].pop(),
            lambda p: p["facts"]["backup"]["files"].pop(),
            lambda p: p["facts"]["observed"].__setitem__(0, {}),
            lambda p: p["facts"]["review"].__setitem__("path", "../review.json"),
            lambda p: p["request"]["preservation"]["original"]["signature"].__setitem__(
                0, True
            ),
        ]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                plan = copy.deepcopy(original)
                change(plan)
                plan["token"] = guard.canonical_digest(
                    {k: v for k, v in plan.items() if k != "token"}
                )
                with self.assertRaises(guard.Unavailable):
                    api.request(
                        json.dumps(
                            dict(
                                version=1,
                                action="prepare-derivative",
                                lineage=plan,
                                created=1,
                            )
                        )
                    )
                self.assertEqual(
                    before, (self.source.read_bytes(), self.store.path.read_bytes())
                )

    def test_owner_changed_after_adoption_cannot_publish(self):
        prepared, _ = self.adoption()
        before = self.source.read_bytes()
        with self.connection() as db:
            db.execute(
                "UPDATE issues SET ComicID='different' WHERE IssueID=?",
                (self.owner["issueid"],),
            )
        with (
            self.runtime.operation() as writer,
            self.assertRaises((guard.Unavailable, native.Review)),
        ):
            derivative.publish(writer, prepared["token"])
        self.assertEqual(before, self.source.read_bytes())

    def test_prepare_api_sanitizes_actual_current_owner_review(self):
        plan = self.plan()
        with self.connection() as db:
            db.execute(
                "UPDATE issues SET ComicID='different' WHERE IssueID=?",
                (self.owner["issueid"],),
            )
        before = self.source.read_bytes()
        with self.assertRaisesRegex(
            guard.Unavailable, "requires current-source review"
        ):
            self.api_controller().dispatch(
                dict(version=1, action="prepare-derivative", lineage=plan, created=1)
            )
        self.assertEqual(before, self.source.read_bytes())

    def test_later_census_cannot_refresh_an_adopted_producer(self):
        prepared, adopted = self.adoption()
        before = self.source.read_bytes()
        later = self.prepare(census=adopted["census"])
        self.call("register", token=later["token"])
        with (
            self.runtime.operation() as writer,
            self.assertRaisesRegex(guard.Unavailable, "cannot be refreshed"),
        ):
            derivative.publish(writer, prepared["token"])
        self.assertEqual(before, self.source.read_bytes())
        self.assertFalse((self.writer.root / derivative.NAME).exists())

    def test_missing_or_foreign_parent_cannot_flatten_registered_family(self):
        registered = self.prepare(census=self.request["census"])
        committed = self.call("register", token=registered["token"])
        self.request["census"] = committed["census"]
        self.refresh_review()
        self.backupdir.rename(self.root / "previous-backup")
        self.restoredir.rename(self.root / "previous-restore")
        self.capture_backup()
        self.adoption()
        with self.writer.hold():
            _, records = guard.registry_snapshot(
                self.store.path, self.writer.root / "publication-v1.json"
            )
        newkey = next(key for key, record in records.items() if record["version"] == 2)
        for parents in ([], ["d" * 64]):
            with self.subTest(parents=parents):
                changed = copy.deepcopy(records)
                record = changed.pop(newkey)
                record["lineage"]["parents"] = parents
                changed[guard.attestation(record)] = record
                with self.assertRaisesRegex(guard.Unavailable, "ancestors"):
                    derivative.families(changed)

    def test_complete_native_census_rejects_rehashed_foreign_reviewed_predecessor(self):
        registered = self.prepare(census=self.request["census"])
        committed = self.call("register", token=registered["token"])
        self.request["census"] = committed["census"]
        self.refresh_review()
        self.backupdir.rename(self.root / "previous-backup")
        self.restoredir.rename(self.root / "previous-restore")
        self.capture_backup()
        prepared, adopted = self.adoption()
        receipt = self.store.get("publication_intent", prepared["token"])
        with self.writer.hold():
            _, records = guard.registry_snapshot(
                self.store.path, self.writer.root / "publication-v1.json"
            )
        oldkey = next(key for key, row in records.items() if row["version"] == 2)
        certificate = receipt["plan"]["body"]["lineage"]["plan"]
        old = certificate["request"]["census"]
        certificate["request"]["census"] = dict(
            old, keys=["a" * 64], digest=guard.canonical_digest(["a" * 64])
        )
        certificate["token"] = guard.canonical_digest(
            {k: v for k, v in certificate.items() if k != "token"}
        )
        receipt["plan"]["body"]["evidence"]["sha256"] = certificate["token"]
        token = guard.canonical_digest(receipt["plan"])
        attestation = dict(receipt["plan"]["body"], intent=token)
        key = guard.attestation(attestation)
        census = dict(
            adopted["census"],
            keys=sorted(
                [row for row in adopted["census"]["keys"] if row != oldkey] + [key]
            ),
        )
        census["digest"] = guard.canonical_digest(census["keys"])
        self.store.delete("publication_intent", prepared["token"])
        self.store.delete("publication_attestation", oldkey)
        self.store.set("publication_intent", token, receipt)
        self.store.set("publication_attestation", key, attestation)
        self.store.set("publication_census", "v1", census)
        marker = guard.private_json(self.writer.root / "publication-v1.json")
        self.document(
            self.writer.root / "publication-v1.json", dict(marker, census=census)
        )
        before = self.source.read_bytes()
        with self.assertRaisesRegex(guard.Unavailable, "reviewed census"):
            guard.registration_effect(token, receipt["plan"])
        with self.writer.hold(), self.assertRaises(guard.Unavailable):
            guard.registry_snapshot(
                self.store.path, self.writer.root / "publication-v1.json"
            )
        self.assertEqual(self.source.read_bytes(), before)

    def test_source_change_during_last_workflow_backup_read_cannot_register(self):
        plan = self.plan()
        real = derivative.semantic
        changed = False

        def change(path):
            nonlocal changed
            result = real(path)
            if not changed:
                changed = True
                self.source.write_bytes(b"externally changed archive retained")
            return result

        with (
            patch.object(derivative, "semantic", side_effect=change),
            self.assertRaises((guard.Unavailable, native.Review)),
        ):
            self.api_controller().dispatch(
                dict(version=1, action="prepare-derivative", lineage=plan, created=1)
            )
        self.assertTrue(changed)
        self.assertEqual(
            self.source.read_bytes(), b"externally changed archive retained"
        )
        with self.writer.hold():
            self.assertEqual(
                guard.registry_snapshot(
                    self.store.path, self.writer.root / "publication-v1.json"
                )[0]["revision"],
                0,
            )

    def test_rehashed_terminal_cannot_claim_old_allowed_payload_was_published(self):
        prepared, _ = self.adoption()
        self.runtime.existing_store = lambda _: self.store
        with self.runtime.operation() as writer:
            derivative.publish(writer, prepared["token"])
        token = prepared["token"]
        path = self.writer.root / "nested-derivative-completed-v1" / (token + ".json")
        witness = guard.private_json(path)
        shutil.copyfile(self.request["preservation"]["original"]["path"], self.source)
        with self.connection() as db:
            db.execute(
                "UPDATE issues SET ComicSize=? WHERE IssueID=?",
                (self.source.stat().st_size, self.owner["issueid"]),
            )
        output = derivative.file_state(self.source)
        witness["output"] = output
        witness["intent"]["output_state"] = output
        with self.writer.hold():
            witness["observed"] = guard.observe_owners(
                self.root / "mylar.db", self.writer, [self.owner], [self.library]
            )["observed"]
        self.document(path, witness)
        self.store.set(
            "nested_derivative",
            token,
            dict(
                version=1,
                token=token,
                phase="committed",
                witness=guard.canonical_digest(witness),
            ),
        )
        before = self.source.read_bytes()
        with (
            self.runtime.operation() as writer,
            self.assertRaisesRegex(guard.Unavailable, "output and intent"),
        ):
            derivative.status(writer, token)
        self.assertEqual(before, self.source.read_bytes())

    def test_retained_intent_without_fence_holds_passive_status_and_native_startup(
        self,
    ):
        self.document(
            self.writer.root / derivative.NAME, dict(version=1, phase="uncertain")
        )
        self.assertFalse(self.writer.fenced(tagger=True))
        status = guard.authority_status(self.store.path, self.writer.root)
        self.assertEqual((status["state"], status["reason"]), ("held", "media-pending"))
        spec = importlib.util.spec_from_file_location(
            "mylar.derivative_test_native_writers",
            Path(__file__).with_name("native_writers.py"),
        )
        actual_native = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(actual_native)
        with self.writer.hold(), self.assertRaises(guard.Unavailable):
            actual_native.admission(self.writer, startup=True)

    def test_final_fsync_failure_restores_fence_and_receipt_without_replay(self):
        prepared, _ = self.adoption()
        self.runtime.existing_store = lambda _: self.store
        real_sync = media_writer.sync

        def fail_final(path):
            if (
                Path(path) == self.writer.root
                and not (self.writer.root / derivative.NAME).exists()
                and not self.writer.fenced(tagger=True)
            ):
                raise OSError("isolated durability fault")
            return real_sync(path)

        with (
            self.runtime.operation() as writer,
            patch.object(media_writer, "sync", side_effect=fail_final),
            self.assertRaises(guard.Unavailable),
        ):
            derivative.publish(writer, prepared["token"])
        self.assertTrue(self.writer.fenced(tagger=True))
        self.assertTrue((self.writer.root / derivative.NAME).is_file())
        self.assertEqual(self.source.read_bytes(), self.derivative.read_bytes())
        self.assertEqual(
            Path(self.request["preservation"]["original"]["path"]).read_bytes(),
            Path(self.request["preservation"]["restore"]["path"]).read_bytes(),
        )
        with self.assertRaises(guard.Unavailable):
            with self.runtime.operation() as writer:
                derivative.publish(writer, prepared["token"])


if __name__ == "__main__":
    unittest.main()
