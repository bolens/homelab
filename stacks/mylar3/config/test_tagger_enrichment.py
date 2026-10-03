"""Reader supplements: real publication, preservation, and a byte-stable repeat."""
from pathlib import Path
import tempfile
import hashlib
import json
import unittest
from unittest.mock import patch
import zipfile

from tagger_enrichment import supplements, validate
from tagger_metadata import reconcile, parse
from tagger_archive import snapshot
from tagger_nfs import Publisher
from tagger_supplement import apply, main, bound_publisher
from media_writer import Writer, PROTOCOL


class EnrichmentTest(unittest.TestCase):
    def test_search_labels_and_publisher_collection_are_idempotent(self):
        raw = b'<ComicInfo><Publisher>Marvel</Publisher><Characters>Wolverine, Storm</Characters><Teams>X-Men</Teams><Tags>Favorite, Character: Storm</Tags><Notes>keep</Notes><Pages><Page Image="0" Bookmark="Start" /></Pages><Extension>private</Extension></ComicInfo>'
        updates = supplements(raw)
        self.assertEqual(updates['SeriesGroup'], 'Publisher: Marvel')
        self.assertEqual(updates['Tags'], 'Favorite, Character: Storm, Character: Wolverine, Team: X-Men')
        result = reconcile(raw, raw, updates=updates)
        self.assertEqual(supplements(result), {})
        self.assertEqual(parse(result).find('Extension').text, 'private')
        self.assertEqual(parse(result).find('Pages/Page').get('Bookmark'), 'Start')

    def test_preserve_existing_fields_and_arc_order(self):
        raw = b'<ComicInfo><Genre>Custom</Genre><LanguageISO>fr</LanguageISO><SeriesGroup>Curated</SeriesGroup><StoryArc>Existing</StoryArc></ComicInfo>'
        policy = {'Genre':'Action', 'LanguageISO':'en', 'SeriesGroup':'Other', 'StoryArc':'New', 'StoryArcNumber':'1', 'AgeRating':'Teen'}
        self.assertEqual(supplements(raw, policy), {'AgeRating':'Teen'})

    def test_repeated_unknown_extensions_are_preserved(self):
        raw = b'<ComicInfo><Extension>A</Extension><Extension>B</Extension><Publisher>DC</Publisher></ComicInfo>'
        result = reconcile(raw, raw, updates=supplements(raw))
        self.assertEqual([n.text for n in parse(result).findall('Extension')], ['A', 'B'])

    def test_empty_field_is_filled_and_missing_facts_are_not_guessed(self):
        self.assertEqual(supplements(b'<ComicInfo><LanguageISO> </LanguageISO></ComicInfo>', {'LanguageISO':'en'}), {'LanguageISO':'en'})
        self.assertEqual(supplements(b'<ComicInfo><Series>Fixture Manga</Series></ComicInfo>'), {})

    def test_policy_rejects_invalid_or_ambiguous_fields(self):
        for policy in ({'AgeRating':'Probably Teen'}, {'LanguageISO':'English'}, {'Manga':'RTL'},
                       {'GTIN':'9780000000000'}, {'GTIN':'4006381333931'}, {'GTIN':'0000000000000'},
                       {'StoryArcNumber':'1'}, {'StoryArc':'A'}, {'StoryArc':'A,,B', 'StoryArcNumber':'1,2'},
                       {'StoryArc':'A,B', 'StoryArcNumber':'1'}, {'Count':'3'}, {'Tags':12}):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                validate(policy)
        self.assertTrue(validate({'GTIN':'9780306406157'}))
        self.assertTrue(validate({'GTIN':'0306406152'}))

    def test_new_provider_metadata_adds_reader_fields(self):
        self.assertEqual(supplements(None, metadata={'publisher':'DC', 'characters':['Batman']}),
                         {'SeriesGroup':'Publisher: DC', 'Tags':'Character: Batman'})

    def test_real_batch_apply_restores_backup_preserves_media_and_repeat_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer_root = root/'writer'; writer_root.mkdir(mode=0o700)
            (writer_root/'writer-v1.lock').write_bytes(PROTOCOL)
            (writer_root/'writer-v1.lock').chmod(0o600)
            writer = Writer(writer_root)
            backup = root/'backup'; backup.mkdir(mode=0o700)
            publisher = Publisher(root/'journal')
            source = root/'comic.cbz'
            with zipfile.ZipFile(source, 'w') as z:
                z.writestr('001.jpg', b'page unchanged')
                z.writestr('credits.txt', b'sidecar unchanged')
                z.writestr('ComicInfo.xml', '<ComicInfo><Series>Fixture</Series><Publisher>DC</Publisher><Characters>Batman</Characters><Notes>Retain me</Notes></ComicInfo>')
                z.comment = b'archive comment'
            source.chmod(0o640)
            old = snapshot(source)
            with patch('tagger_adapter.save', side_effect=AssertionError('Offline supplement must not invoke CLI')):
                self.assertEqual(apply(source, {}, writer, publisher, backup), 'committed')
                new = snapshot(source)
                self.assertEqual((old.members, old.comment, old.mode, old.uid, old.gid),
                                 (new.members, new.comment, new.mode, new.uid, new.gid))
                before = source.read_bytes()
                self.assertEqual(apply(source, {}, writer, publisher, backup), 'unchanged')
                self.assertEqual(source.read_bytes(), before)
                self.assertFalse(writer.fenced(tagger=True))
                self.assertEqual(list(backup.iterdir()), [])

    def test_main_recovers_hidden_or_published_source_before_enumerating(self):
        for checkpoint in ('after_displace', 'after_link'):
            with self.subTest(checkpoint=checkpoint), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                config = root/'config'; config.mkdir()
                writer = Writer(config/'media-writer', create=True)
                state = config/'modern-tagger-v2'
                paths = (state, state/'journal-v2', state/'staging', state/'staging-receipts')
                for path in paths: path.mkdir(mode=0o700)
                digest = hashlib.sha256(json.dumps([(p.stat().st_dev, p.stat().st_ino) for p in paths]).encode()).hexdigest()
                binding = writer.root/'tagger-state-v2.identity'
                binding.write_text(digest+'\n'); binding.chmod(0o600)
                publisher = bound_publisher(writer)
                backup = root/'backups'; backup.mkdir(mode=0o700)
                library = root/'library'; library.mkdir()
                source = library/'comic.cbz'
                with zipfile.ZipFile(source, 'w') as z:
                    z.writestr('001.jpg', b'preserved')
                    z.writestr('ComicInfo.xml', '<ComicInfo><Series>Fixture</Series><Publisher>DC</Publisher></ComicInfo>')
                old = snapshot(source)
                def crash(stage):
                    if stage == checkpoint: raise KeyboardInterrupt()
                with patch('tagger_adapter._checkpoint', side_effect=crash), self.assertRaises(KeyboardInterrupt):
                    apply(source, {}, writer, publisher, backup)
                self.assertTrue(writer.fenced(tagger=True))
                self.assertEqual(main([str(library), '--apply', '--config', str(config), '--backup-root', str(backup)]), 0)
                self.assertEqual(snapshot(source).members, old.members)
                self.assertEqual(supplements(snapshot(source).xml), {})
                self.assertFalse(writer.fenced(tagger=True))
                # Evidence from the interrupted per-file verification is retained.
                self.assertTrue(list(backup.iterdir()))
                (state/'staging').rmdir(); (state/'staging').mkdir(mode=0o700)
                with self.assertRaises(ValueError): bound_publisher(writer)


if __name__ == '__main__':
    unittest.main()
