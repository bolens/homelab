"""New genuine installed ordinary pipeline cases; no historical-suite claim."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).absolute().parent))

from runtime_state import COMIC, ISSUE, DELIVERY, State, close_installed, digest, installed

CASES = ('discovery', 'first-import', 'lost-reply', 'rename-metadata')


def acknowledgement(state, destination):
    from mylar import ordinary_import_history as history
    token, attempt, ack, serialized = state.completion()
    owner = dict(table='issues', issueid=ISSUE, parentcomicid=COMIC, releasecomicid=COMIC)
    assert attempt['owner'] == ack['owner'] == owner
    assert history.confirmed_token(token, owner, str(destination))
    assert history.confirmed_ddl(DELIVERY, owner, str(destination))
    return token, owner, serialized


def case(state, name):
    terminal = state.run(discovery=name == 'discovery', lost_reply=name == 'lost-reply')
    destination = state.destination()
    token, owner, original_ack = acknowledgement(state, destination)
    assert digest(destination) == state.original_sha
    if name == 'lost-reply':
        assert any(row.get('mode') == 'review' for row in terminal)
        assert state.source.is_file() and digest(state.source) == state.original_sha
        assert acknowledgement(state, destination)[2] == original_ack
        assert state.completion()[3] == original_ack
        return dict(source_retained=True, passive_exact_ack_reconciled=True,
                    processing_replayed=False)
    assert not any(row.get('mode') in ('review', 'fail') for row in terminal)
    assert not state.source.exists(), 'ordinary source cleanup did not follow durable completion'
    if name != 'rename-metadata':
        return dict(source_retired_after_fresh_ack=True, complete_discovery=name == 'discovery')
    from mylar import release_naming, tagger_native, tagger_supplement
    from mylar import native_writers, ordinary_import_history as history
    before = digest(destination)
    renamed = release_naming.rename(dict(version=1, source=str(destination),
        target='Runtime.Fixture.Series.001.(2024)-Fixture.cbz', sha256=before,
        issueid=ISSUE, comicid=COMIC))
    assert renamed['phase'] == 'committed'
    renamed_path = Path(renamed['destination'])
    assert renamed_path != destination and not destination.exists()
    assert digest(renamed_path) == before
    assert history.confirmed_token(token, owner, str(renamed_path))
    copies = state.root / 'preservation'
    copies.mkdir(mode=0o700)
    original, restored = copies / 'original.cbz', copies / 'restore.cbz'
    for path in (original, restored):
        shutil.copy2(renamed_path, path)
        assert digest(path) == before
    with zipfile.ZipFile(renamed_path) as archive:
        members = {n: archive.read(n) for n in archive.namelist() if n != 'ComicInfo.xml'}
    with native_writers.operation() as writer:
        publisher, _ = tagger_native.state(writer)
    policy = {'AgeRating': 'Teen'}
    old_snapshot = tagger_supplement.snapshot(renamed_path)
    old_security = publisher.security(renamed_path)
    try:
        result = tagger_supplement.apply_preserved(renamed_path, policy,
            state.writer, publisher, original, restored, before, secrets.token_hex(16))
    except BaseException:
        # Read only the new disposable fixture before State's cleanup. Retain
        # the original exception; diagnostics never authorize a terminal result.
        try:
            new_snapshot = tagger_supplement.snapshot(renamed_path)
            fields = ('members', 'comment', 'mode', 'uid', 'gid', 'attributes')
            equal = {field: getattr(old_snapshot, field) == getattr(new_snapshot, field)
                     for field in fields}
            attribute_fields = ('name', 'date_time', 'compress_type', 'comment',
                                'extra', 'create_system', 'create_version',
                                'extract_version', 'internal_attr', 'external_attr', 'flag_bits')
            old_attributes = {row[0]: row for row in old_snapshot.attributes}
            new_attributes = {row[0]: row for row in new_snapshot.attributes}
            changed = {
                name: [attribute_fields[index] for index, (left, right) in
                       enumerate(zip(old_attributes[name], new_attributes[name])) if left != right]
                for name in sorted(old_attributes.keys() & new_attributes.keys())
                if old_attributes[name] != new_attributes[name]}
            report = dict(preservation_equal=equal,
                          old_mode=old_snapshot.mode, new_mode=new_snapshot.mode,
                          old_uid=old_snapshot.uid, new_uid=new_snapshot.uid,
                          old_gid=old_snapshot.gid, new_gid=new_snapshot.gid,
                          attributes_changed=changed,
                          old_attribute_order=[row[0] for row in old_snapshot.attributes],
                          new_attribute_order=[row[0] for row in new_snapshot.attributes],
                          attributes_added=sorted(new_attributes.keys() - old_attributes.keys()),
                          attributes_removed=sorted(old_attributes.keys() - new_attributes.keys()),
                          security_equal=publisher.security(renamed_path) == old_security,
                          additions_before=tagger_supplement.supplements(old_snapshot.xml, policy),
                          additions_after=tagger_supplement.supplements(new_snapshot.xml, policy),
                          original_copy_unchanged=digest(original) == before,
                          restored_copy_unchanged=digest(restored) == before,
                          current_sha256=digest(renamed_path),
                          metadata_sha256=__import__('hashlib').sha256(new_snapshot.xml or b'').hexdigest())
            encoded = json.dumps(report, sort_keys=True)
            assert len(encoded.encode()) <= 65536, 'fixture diagnostic bound'
            print('GENUINE_METADATA_REFUSAL=' + encoded, file=sys.stderr, flush=True)
        except Exception:
            print('GENUINE_METADATA_REFUSAL=diagnostic-unavailable', file=sys.stderr, flush=True)
        raise
    assert result['before'] == before and result['after'] == digest(renamed_path)
    assert result['after'] != before
    with zipfile.ZipFile(renamed_path) as archive:
        assert {n: archive.read(n) for n in archive.namelist() if n != 'ComicInfo.xml'} == members
        assert b'<AgeRating>Teen</AgeRating>' in archive.read('ComicInfo.xml')
    assert digest(original) == digest(restored) == before
    assert history.confirmed_token(token, owner, str(renamed_path))
    assert state.completion()[3] == original_ack
    return dict(rename_committed=True, preserved_metadata_committed=True,
                original_ack_unchanged=True, preserved_copies=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=CASES, required=True)
    parser.add_argument('--expected-map', type=Path, required=True)
    parser.add_argument('--expected-map-sha256', required=True)
    args = parser.parse_args()
    assert os.geteuid() != 0 and os.getuid() == os.geteuid(), 'non-root fixture runtime required'
    assert not any(k.startswith('MYLAR_') and k.endswith('DATA') for k in os.environ)
    app, frames = installed(args.expected_map, args.expected_map_sha256)
    state = State(app)
    try:
        facts = case(state, args.case)
        with sqlite3.connect(state.catalog) as db:
            assert db.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
        state.preserved_unrelated()
        close_installed(frames)
        print('GENUINE_PIPELINE_CASE=' + json.dumps(dict(case=args.case, passed=True,
            new_maintained_batch=True, installed_package=True, simulated_live_data=False,
            configured_acceptance=False, **facts), sort_keys=True), flush=True)
    finally:
        state.temp.cleanup()


if __name__ == '__main__':
    main()
