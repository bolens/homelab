"""Protect supplementation identity matching and uncertain-submission retries."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('supplement', ROOT / 'stacks/librarr/bookshelf_supplement.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class SupplementTests(unittest.TestCase):
    def setUp(self):
        self.book = {'id': 1, 'authorId': 2, 'title': 'Dune'}
        self.candidate = {'source': 'prowlarr', 'title': 'Frank Herbert - Dune EPUB',
            'format': 'epub', 'seeders': 2, 'download_protocol': 'torrent',
            'magnet_url': 'magnet:?xt=urn:btih:' + 'a' * 40}

    def test_exact_ebook_with_author_matches(self):
        self.assertTrue(s.match_candidate(self.book, 'Frank Herbert', self.candidate))

    def test_wrong_book_author_format_media_or_source_rejected(self):
        changes = [{'title': 'Frank Herbert - Dune Messiah EPUB'},
                   {'title': 'Frank Smith - Dune EPUB'}, {'format': 'mp3'},
                   {'media_type': 'audiobook'}, {'download_protocol': 'nzb'},
                   {'seeders': 0}, {'in_library': True}, {'language': 'ru'},
                   {'title': 'Frank Herbert Dune Complete Works EPUB'}]
        for change in changes:
            with self.subTest(change=change):
                self.assertFalse(s.match_candidate(self.book, 'Frank Herbert', self.candidate | change))

    def test_reordered_leading_article_does_not_hide_an_exact_match(self):
        book = self.book | {'title': 'The Twelfth Planet'}
        candidate = self.candidate | {'title': 'Twelfth Planet, The - Zecharia Sitchin EPUB'}
        self.assertTrue(s.match_candidate(book, 'Zecharia Sitchin', candidate))

    def test_plain_novel_cannot_satisfy_graphic_adaptation(self):
        book = self.book | {'title': 'The Hobbit: A Graphic Novel'}
        candidate = self.candidate | {'title': 'J R R Tolkien - The Hobbit (retail) (azw3)', 'format': 'azw3'}
        self.assertFalse(s.match_candidate(book, 'J. R. R. Tolkien', candidate))

    def test_same_surname_or_conflicting_author_metadata_is_rejected(self):
        for title in ('Dune EPUB', self.candidate['title']):
            candidate = self.candidate | {'title': title, 'author': 'Brian Herbert'}
            self.assertFalse(s.match_candidate(self.book, 'Frank Herbert', candidate))

    def test_distinguishing_subtitle_is_required(self):
        book = self.book | {'title': 'Dune: The Illustrated Edition'}
        self.assertFalse(s.match_candidate(book, 'Frank Herbert', self.candidate))
        candidate = self.candidate | {'title': 'Frank Herbert - Dune The Illustrated Edition EPUB'}
        self.assertTrue(s.match_candidate(book, 'Frank Herbert', candidate))

    def test_explicit_rejection_is_failed_and_blocked_without_retry(self):
        outer = self
        class Bookshelf:
            def call(self, path):
                if path == '/api/v1/author':
                    return [{'id': 2, 'authorName': 'Frank Herbert'}]
                if 'wanted/missing' in path:
                    return {'records': [outer.book]}
                if '/queue' in path:
                    return {'records': []}
                return outer.book
        class Librarr:
            grabs = 0
            def call(self, path, data=None):
                if '/search?' in path:
                    return {'results': [outer.candidate]}
                self.grabs += 1
                return {'success': False, 'error': 'rejected'}
        client = Librarr()
        with tempfile.TemporaryDirectory() as directory:
            first = s.acquire(Bookshelf(), client, Path(directory), 1, apply=True)
            second = s.acquire(Bookshelf(), client, Path(directory), 1, apply=True)
        self.assertEqual(first['failed'], 1)
        self.assertEqual(first['submitted'], 0)
        self.assertEqual(second['already_owned_or_queued'], 0)
        self.assertEqual(second['receipt_blocked'], 1)
        self.assertEqual(client.grabs, 1)

    def test_unknown_submission_is_not_repeated(self):
        outer = self
        class Bookshelf:
            def call(self, path):
                if path == '/api/v1/author':
                    return [{'id': 2, 'authorName': 'Frank Herbert'}]
                if 'wanted/missing' in path:
                    return {'records': [outer.book]}
                if '/queue' in path:
                    return {'records': []}
                return outer.book
        class Librarr:
            grabs = 0
            def call(self, path, data=None):
                if '/search?' in path:
                    return {'results': [outer.candidate]}
                self.grabs += 1
                raise TimeoutError('uncertain response after submit')
        client = Librarr()
        with tempfile.TemporaryDirectory() as directory:
            s.acquire(Bookshelf(), client, Path(directory), 1, apply=True)
            s.acquire(Bookshelf(), client, Path(directory), 1, apply=True)
        self.assertEqual(client.grabs, 1)


if __name__ == '__main__':
    unittest.main()
