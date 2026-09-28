"""Publication tests use real archives/exchanges and injected child outcomes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

import tagger_adapter as subject
from tagger_archive import snapshot
from tagger_cli import TagResult

TOKEN = 'a' * 32


def saved(path, metadata, **kwargs):
    with zipfile.ZipFile(path, 'a') as archive:
        archive.writestr('ComicInfo.xml', b'<ComicInfo><Series>Fixture</Series><Number>1</Number></ComicInfo>')
    return TagResult('saved')


class PublicationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'comic.cbz'
        with zipfile.ZipFile(self.source, 'w') as archive:
            archive.writestr('001.png', b'preserved page')
            archive.writestr('credit.txt', b'preserved credit')
            archive.comment = b'legacy metadata'
        self.source.chmod(0o640)
        self.before = self.source.read_bytes()
        self.publisher = subject.Publisher(self.root / 'state')

    def tag(self, **kwargs):
        with patch.object(subject, 'save', side_effect=saved):
            return self.publisher.tag(self.source, {'series':'Fixture'}, token=TOKEN, **kwargs)

    def test_success_preserves_contents_and_permissions_and_replay(self):
        old = snapshot(self.source)
        result = self.tag()
        self.assertEqual((result.state, result.metadata), ('committed', 'added'))
        new = snapshot(self.source)
        self.assertEqual((old.members, old.comment, old.mode, old.uid, old.gid),
                         (new.members, new.comment, new.mode, new.uid, new.gid))
        with patch.object(subject, 'save', side_effect=AssertionError('Do not repeat CLI')):
            self.assertEqual(self.publisher.tag(self.source, {'series':'Fixture'}, token=TOKEN), result)
        self.assertFalse(list(self.root.glob('.mylar-tag-*')))
        self.assertEqual(self.publisher.receipt(TOKEN).stat().st_mode & 0o777, 0o600)

    def test_terminal_commit_rechecks_ownership_before_cleanup(self):
        for change in ('permissions', 'replacement', 'displaced'):
            with self.subTest(change=change):
                self.setUp()
                with patch.object(subject.shutil, 'rmtree', side_effect=SystemExit):
                    with self.assertRaises(SystemExit):
                        self.tag()
                folder = self.root/('.mylar-tag-'+TOKEN)
                if change == 'permissions':
                    self.source.chmod(0o644)
                elif change == 'replacement':
                    replacement = self.root/'replacement'
                    shutil.copyfile(self.source, replacement)
                    replacement.chmod(0o640)
                    os.replace(replacement, self.source)
                else:
                    (folder/'verified.cbz').write_bytes(b'another writer')
                self.assertEqual(self.publisher.recover(TOKEN).state, 'conflict')
                self.assertEqual((folder/'original.cbz').read_bytes(), self.before)

    def test_unknown_state_and_malformed_receipts_are_retained(self):
        self.crash('staged')
        original = self.publisher.read(TOKEN)
        for change in ({'state':'future_state'}, {'cleaned':'false'}, {'workspace':[]},
                       {'source':42}, {'source':str(self.source)+'\0'},
                       {'source':str(self.source)+'\ud800'}, {'source':'/'+str(self.source)},
                       {'before':'not a hash'}):
            record = dict(original, **change)
            raw = json.dumps(record)
            self.publisher.receipt(TOKEN).write_text(raw)
            with self.assertRaises(ValueError):
                self.publisher.recover(TOKEN)
            self.assertEqual(self.publisher.receipt(TOKEN).read_text(), raw)
            self.assertTrue((self.root/('.mylar-tag-'+TOKEN)/'original.cbz').exists())

    def test_failed_timeout_and_changed_page_keep_original(self):
        for state in ('failed', 'timed_out', 'invalid_result'):
            token = hashlib.md5(state.encode()).hexdigest()
            with patch.object(subject, 'save', return_value=TagResult(state)):
                result = self.publisher.tag(self.source, {'series':'Fixture'}, token=token)
            self.assertEqual(result.state, 'timed_out' if state == 'timed_out' else 'failed')
            self.assertEqual(self.source.read_bytes(), self.before)
        def corrupt(path, metadata, **kwargs):
            path.write_bytes(b'corrupt')
            return TagResult('saved')
        with patch.object(subject, 'save', side_effect=corrupt):
            self.assertEqual(self.publisher.tag(self.source, {'series':'Fixture'}, token=TOKEN).state, 'failed')
        self.assertEqual(self.source.read_bytes(), self.before)

    def test_failed_child_with_changed_source_retains_original_copy(self):
        def failed(path, metadata, **kwargs):
            self.source.write_bytes(b'concurrent update')
            return TagResult('failed')
        with patch.object(subject, 'save', side_effect=failed):
            self.assertEqual(self.publisher.tag(self.source, {'series':'Fixture'}, token=TOKEN).state, 'conflict')
        self.assertEqual(self.source.read_bytes(), b'concurrent update')
        self.assertEqual((self.root/('.mylar-tag-'+TOKEN)/'original.cbz').read_bytes(), self.before)

    def test_low_space_and_exchange_error_preserve_source(self):
        with patch.object(subject.shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(1, 1, 0)):
            self.assertEqual(self.tag().state, 'failed')
        with patch.object(subject, 'exchange', side_effect=OSError('unsupported filesystem')):
            self.assertEqual(self.tag().state, 'failed')
        self.assertEqual(self.source.read_bytes(), self.before)
        self.assertFalse(list(self.root.glob('.mylar-tag-*')))

    def test_symlink_hardlink_xattrs_and_wrong_format_rejected(self):
        link = self.root/'link.cbz'
        link.symlink_to(self.source)
        self.assertEqual(self.publisher.tag(link, {}, token=TOKEN).state, 'unsupported')
        link.unlink()
        os.link(self.source, link)
        self.assertEqual(self.tag().state, 'unsupported')
        link.unlink()
        with patch.object(subject.os, 'listxattr', return_value=['user.keep']):
            self.assertEqual(self.tag().state, 'unsupported')
        self.assertEqual(self.publisher.tag(self.root/'comic.cbr', {}, token=TOKEN).state, 'unsupported')
        self.assertEqual(self.source.read_bytes(), self.before)

    def test_source_change_before_exchange_is_conflict(self):
        changed = b'another writer'
        def checkpoint(stage):
            if stage == 'before_exchange':
                self.source.write_bytes(changed)
        with patch.object(subject, '_checkpoint', side_effect=checkpoint):
            self.assertEqual(self.tag().state, 'conflict')
        self.assertEqual(self.source.read_bytes(), changed)
        self.assertEqual((self.root/('.mylar-tag-'+TOKEN)/'original.cbz').read_bytes(), self.before)
        self.assertEqual(self.publisher.tag(self.source, {}, token='b'*32).state, 'conflict')

    def test_last_instant_race_retains_displaced_file_and_original(self):
        exchange = subject.exchange
        def racing(left, right):
            self.source.write_bytes(b'concurrent update')
            exchange(left, right)
        with patch.object(subject, 'exchange', side_effect=racing):
            self.assertEqual(self.tag().state, 'conflict')
        folder = self.root/('.mylar-tag-'+TOKEN)
        self.assertEqual((folder/'verified.cbz').read_bytes(), b'concurrent update')
        self.assertEqual((folder/'original.cbz').read_bytes(), self.before)
        self.assertEqual(self.publisher.recover(TOKEN).state, 'conflict')

    def crash(self, point):
        # A real process death bypasses Python cleanup/finally handlers.
        code = """
import os, sys, zipfile
import tagger_adapter as a
from tagger_cli import TagResult
def save(path, metadata, **kwargs):
    with zipfile.ZipFile(path, 'a') as z:z.writestr('ComicInfo.xml', b'<ComicInfo><Series>Fixture</Series></ComicInfo>')
    return TagResult('saved')
a.save = save
a._checkpoint = lambda stage: os._exit(77) if stage == sys.argv[3] else None
a.Publisher(sys.argv[1]).tag(sys.argv[2], {'series':'Fixture'}, token='a'*32)
"""
        result = subprocess.run([sys.executable, '-c', code, str(self.publisher.root), str(self.source), point],
                                env=dict(os.environ, PYTHONPATH=str(Path(subject.__file__).parent)),
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 77, result.stderr)

    def test_crash_before_exchange_aborts_without_repeating_cli(self):
        self.crash('before_exchange')
        self.assertEqual(self.publisher.recover(TOKEN).state, 'failed')
        self.assertEqual(self.source.read_bytes(), self.before)
        self.assertFalse(list(self.root.glob('.mylar-tag-*')))

    def test_crash_after_exchange_recovers_commit(self):
        self.crash('after_exchange')
        self.assertEqual(self.publisher.read(TOKEN)['state'], 'publishing')
        result = self.publisher.recover(TOKEN)
        self.assertEqual((result.state, result.metadata), ('committed', 'added'))
        self.assertIn(b'<Series>Fixture</Series>', snapshot(self.source).xml)
        self.assertEqual(self.publisher.recover(TOKEN), result)

    def test_crash_during_staging_aborts_without_repeating_cli(self):
        self.crash('staged')
        self.assertEqual(self.publisher.recover(TOKEN).state, 'failed')
        self.assertEqual(self.source.read_bytes(), self.before)

    def test_changed_committed_file_and_reused_token_do_not_repeat(self):
        self.assertEqual(self.tag().state, 'committed')
        with patch.object(subject, 'save', side_effect=AssertionError('Do not repeat CLI')):
            self.assertEqual(self.publisher.tag(self.source, {'series':'Other'}, token=TOKEN).state, 'conflict')
            self.source.write_bytes(b'operator change')
            self.assertEqual(self.publisher.recover(TOKEN).state, 'conflict')
        self.assertEqual(self.source.read_bytes(), b'operator change')

    def test_superseded_completed_history_does_not_block_new_jobs(self):
        self.assertEqual(self.tag().state, 'committed')
        with patch.object(subject, 'save', side_effect=lambda *a, **k: TagResult('saved')):
            result = self.publisher.tag(self.source, {'series':'Second'}, token='b'*32, updates={'Series':'Second'})
            self.assertEqual(result.state, 'committed')
            self.assertEqual(self.publisher.recover(TOKEN).state, 'conflict')
            self.assertEqual(self.publisher.read(TOKEN)['state'], 'committed')
            self.assertEqual(self.publisher.tag(self.source, {'series':'Third'}, token='c'*32, updates={'Series':'Third'}).state, 'committed')

    def test_no_lifetime_quota_from_completed_history(self):
        self.assertEqual(self.tag().state, 'committed')
        template = self.publisher.read(TOKEN)
        self.publisher.receipt(TOKEN).unlink()
        for i in range(1001):
            token = format(i, '032x')
            self.publisher.receipt(token).write_text(json.dumps(dict(template, token=token, state='failed', cleaned=True)))
        with patch.object(subject, 'save', return_value=TagResult('saved')):
            self.assertEqual(self.publisher.tag(self.source, {'series':'Fixture'}, token=TOKEN).state, 'unchanged')

    def test_removed_completed_source_does_not_rewrite_history(self):
        self.assertEqual(self.tag().state, 'committed')
        self.source.unlink()
        self.assertEqual(self.publisher.recover(TOKEN).state, 'conflict')
        self.assertEqual(self.publisher.read(TOKEN)['state'], 'committed')

    def test_corrupt_crc_reports_failure_without_source_change(self):
        raw = self.source.read_bytes().replace(b'preserved page', b'corrupted page')
        self.source.write_bytes(raw)
        self.assertEqual(self.tag().state, 'failed')
        self.assertEqual(self.source.read_bytes(), raw)

    def test_permission_change_after_exchange_keeps_recovery_files(self):
        def changed(stage):
            if stage == 'after_exchange':
                self.source.chmod(0o600)
        with patch.object(subject, '_checkpoint', side_effect=changed):
            self.assertEqual(self.tag().state, 'conflict')
        self.assertEqual((self.root/('.mylar-tag-'+TOKEN)/'original.cbz').read_bytes(), self.before)

    def test_growing_source_hash_is_bounded(self):
        digest = hashlib.sha256()
        source = self.source
        class GrowingDigest:
            def update(self, block):
                digest.update(block)
                with source.open('ab') as writer:
                    writer.write(b'concurrent growth')
            def hexdigest(self):
                return digest.hexdigest()
        with patch.object(subject.hashlib, 'sha256', return_value=GrowingDigest()):
            with self.assertRaises(ValueError):
                subject.fingerprint(source)

    def test_path_alias_cannot_bypass_pending_recovery(self):
        self.crash('before_exchange')
        (self.root/'sub').mkdir()
        alias = self.root/'sub'/'..'/'comic.cbz'
        with patch.object(subject, 'save', side_effect=AssertionError('Pending owner must block')):
            self.assertEqual(self.publisher.tag(alias, {'series':'Fixture'}, token='b'*32).state, 'unsupported')
        self.assertEqual(self.publisher.read(TOKEN)['state'], 'publishing')
        self.assertEqual(self.source.read_bytes(), self.before)
        with self.assertRaises(ValueError):
            subject.Publisher(self.root/'sub'/'..'/'state')

    def test_startup_recovers_pending_and_skips_cleaned_history(self):
        self.crash('after_exchange')
        with patch.object(subject, 'save', side_effect=AssertionError('No repeated CLI')):
            rows = list(self.publisher.recover_pending())
        self.assertEqual(rows, [subject.RecoveryResult(TOKEN, 'committed', 'added')])
        with patch.object(subject, 'fingerprint', side_effect=AssertionError('No history hashing')):
            self.assertEqual(list(self.publisher.recover_pending()), [])
        self.assertNotIn(str(self.root), repr(rows))

    def test_startup_retains_invalid_receipts_and_continues_recovery(self):
        self.crash('staged')
        invalid = self.publisher.receipt('b'*32)
        invalid.write_text('not json')
        nested = self.publisher.receipt('c'*32)
        nested_raw = '['*100000 + '0' + ']'*100000
        nested.write_text(nested_raw)
        named = self.publisher.root/'private-name.json'
        named.write_text('{}')
        rows = list(self.publisher.recover_pending())
        self.assertEqual(sorted(r.state for r in rows), ['failed', 'invalid_journal', 'invalid_journal', 'invalid_journal'])
        self.assertEqual(invalid.read_text(), 'not json')
        self.assertTrue(named.exists())
        self.assertEqual(nested.read_text(), nested_raw)
        self.assertNotIn('private-name', repr(rows))
        self.assertEqual(self.source.read_bytes(), self.before)

    def test_startup_does_not_wait_on_active_token_or_source(self):
        self.crash('staged')
        for lock in ('token:' + TOKEN, self.source):
            with self.publisher.lock(lock):
                rows = list(self.publisher.recover_pending())
            self.assertEqual(rows, [subject.RecoveryResult(TOKEN, 'busy')])
            self.assertEqual(self.publisher.read(TOKEN)['state'], 'staged')
        self.assertEqual(list(self.publisher.recover_pending())[0].state, 'failed')

    def test_startup_releases_locks_before_yielding(self):
        self.crash('staged')
        pending = self.publisher.recover_pending()
        self.assertEqual(next(pending).state, 'failed')
        with self.publisher.lock('token:' + TOKEN, blocking=False), self.publisher.lock(self.source, blocking=False):
            pass
        pending.close()

    def test_startup_retains_symlink_receipt(self):
        external = self.root/'external'
        external.write_text('keep')
        self.publisher.receipt(TOKEN).symlink_to(external)
        self.assertEqual(list(self.publisher.recover_pending()), [subject.RecoveryResult(TOKEN, 'io_error')])
        self.assertEqual(external.read_text(), 'keep')
        self.assertTrue(self.publisher.receipt(TOKEN).is_symlink())

    def test_pre_epoch_source_timestamp_round_trips(self):
        os.utime(self.source, ns=(-1000000000, -1000000000))
        result = self.tag()
        self.assertEqual(result.state, 'committed')
        self.assertEqual(self.publisher.recover(TOKEN), result)
        self.assertEqual(list(self.publisher.recover_pending()), [])

    def test_double_root_alias_cannot_bypass_pending_owner(self):
        self.crash('staged')
        with patch.object(subject, 'save', side_effect=AssertionError('Pending owner must block')):
            self.assertEqual(self.publisher.tag('/'+str(self.source), {}, token='b'*32).state, 'unsupported')
        self.assertEqual(self.publisher.read(TOKEN)['state'], 'staged')
        self.assertEqual(self.source.read_bytes(), self.before)
        with self.assertRaises(ValueError):
            subject.Publisher('/'+str(self.publisher.root))

    def test_unknown_journal_version_retained(self):
        path = self.publisher.receipt(TOKEN)
        path.write_text(json.dumps({'version':99, 'token':TOKEN}))
        with self.assertRaises(ValueError):
            self.publisher.recover(TOKEN)
        self.assertEqual(json.loads(path.read_text())['version'], 99)
        self.assertEqual(self.source.read_bytes(), self.before)

    def test_concurrent_token_reuse_across_sources_has_one_owner(self):
        second = self.root/'other.cbz'
        second.write_bytes(self.before)
        entered, release = threading.Event(), threading.Event()
        results = []
        def blocking_save(path, metadata, **kwargs):
            entered.set()
            self.assertTrue(release.wait(5))
            return saved(path, metadata, **kwargs)
        def run(path):
            results.append(self.publisher.tag(path, {'series':'Fixture'}, token=TOKEN))
        with patch.object(subject, 'save', side_effect=blocking_save):
            one = threading.Thread(target=run, args=(self.source,))
            two = threading.Thread(target=run, args=(second,))
            one.start()
            self.assertTrue(entered.wait(5))
            two.start()
            time.sleep(0.05)
            release.set()
            one.join(5)
            two.join(5)
            self.assertFalse(one.is_alive() or two.is_alive())
        self.assertEqual(sorted(r.state for r in results), ['committed', 'conflict'])
        self.assertEqual(second.read_bytes(), self.before)
        self.assertEqual(self.publisher.read(TOKEN)['source'], str(self.source))

    def test_workspace_replaced_after_crash_is_not_removed(self):
        self.crash('before_exchange')
        folder = self.root/('.mylar-tag-'+TOKEN)
        folder.rename(self.root/'retained')
        folder.mkdir()
        (folder/'do-not-remove').write_text('other owner')
        self.assertEqual(self.publisher.recover(TOKEN).state, 'conflict')
        self.assertTrue((folder/'do-not-remove').exists())


if __name__ == '__main__':
    unittest.main()
