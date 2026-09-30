"""Known CBZ/CBR alternatives outrank PDF without weakening matching policy."""
from types import SimpleNamespace
import unittest
from comic_format_preference import declared_format, rank, first, ordered


def row(name, pack=False):
    return {'pack': pack, 'entry': {'filename': name}}


class PreferenceTest(unittest.TestCase):
    def test_explicit_formats_and_unknown_links(self):
        self.assertEqual(declared_format('Year : 2020 | Format : CBR, CBZ | Size : 20 MB'), 'CBR, CBZ')
        self.assertEqual(rank({'entry': {'download_format': 'CBR, PDF'}}), 0)
        self.assertEqual(rank(row('Book.CBZ')), 0)
        self.assertEqual(rank(row('Book.pdf')), 2)
        self.assertEqual(rank({'link': 'https://host.invalid/PDF-Book/?token=.cbz'}), 1)
        self.assertEqual(rank({'link': 'https://host.invalid/Book%20One.cbr?token=secret'}), 0)

    def test_native_match_checks_then_native_format_preference(self):
        pdf, unknown, cbr = row('Book.pdf'), row('Book'), row('Book.cbr')
        checker = SimpleNamespace(_process_entry=lambda entry, info: None if entry == 'rejected' else entry)
        self.assertIs(first(checker, [pdf, 'rejected', unknown, cbr], {}), cbr)
        self.assertIs(first(checker, [pdf], {}), pdf)
        self.assertIs(first(checker, [pdf, unknown], {}), unknown)

    def test_pack_priority_and_stable_kind_slots(self):
        single_pdf, pack_cbz, single_cbz = row('one.pdf'), row('pack.cbz', True), row('one.cbz')
        checker = SimpleNamespace(_process_entry=lambda entry, info: entry)
        self.assertIs(first(checker, [single_pdf, pack_cbz, single_cbz], {}, True), pack_cbz)
        self.assertIs(first(checker, [single_pdf, pack_cbz], {}, False), single_pdf)
        self.assertEqual(ordered([single_pdf, pack_cbz, single_cbz]), [single_cbz, pack_cbz, single_pdf])

    def test_later_network_failure_keeps_fallback_but_checker_errors_propagate(self):
        pdf = row('book.pdf')
        def entries():
            yield pdf
            raise TimeoutError('next page')
        checker = SimpleNamespace(_process_entry=lambda entry, info: entry)
        self.assertIs(first(checker, entries(), {}), pdf)
        def before_match():
            raise TimeoutError('first page')
            yield
        with self.assertRaises(TimeoutError): first(checker, before_match(), {})
        def broken(entry, info):
            raise ValueError('checker failure')
        with self.assertRaises(ValueError): first(SimpleNamespace(_process_entry=broken), [pdf], {})
        self.assertEqual(rank({'link': 'http://[bad'}), 1)

    def test_lookahead_is_bounded_without_dropping_pdf_fallback(self):
        seen = []
        pdf = row('one.pdf')
        def entries():
            for i in range(1000):
                seen.append(i)
                yield pdf
        checker = SimpleNamespace(_process_entry=lambda entry, info: entry)
        self.assertIs(first(checker, entries(), {}), pdf)
        self.assertEqual(len(seen), 100)


if __name__ == '__main__':
    unittest.main()
