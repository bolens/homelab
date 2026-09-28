"""Pure XML acceptance; real ComicTagger/archive gates are separate."""
import unittest
from tagger_metadata import MAX_XML, overrides, parse, reconcile


class MetadataTest(unittest.TestCase):
    def test_explicit_volume_one_and_start_year(self):
        self.assertEqual(overrides(volume=1), {'Volume':'1'})
        self.assertEqual(overrides(volume='2017'), {'Volume':'2017'})
        for invalid in (True, 'v2', '0', '-1', '2.1'):
            with self.assertRaises(ValueError):
                overrides(volume=invalid)

    def test_missing_values_do_not_clear(self):
        self.assertEqual(overrides(volume='None', reading_order=[], age_rating=''), {})

    def test_paired_unicode_arcs(self):
        value = overrides(reading_order=[('Étoile & Moon', 1), ('Finale', '2.5')])
        root = parse(reconcile(b'', b'<ComicInfo/>', updates=value))
        self.assertEqual(root.findtext('StoryArc'), 'Étoile & Moon,Finale')
        self.assertEqual(root.findtext('StoryArcNumber'), '1,2.5')

    def test_ambiguous_arcs_are_rejected(self):
        for arcs in ([('A,B',1)], [('A',None)], [('A',True)], [('A',)], [(' ',1)]):
            with self.assertRaises(ValueError):
                overrides(reading_order=arcs)

    def test_preserves_notes_links_pages_and_extensions(self):
        old = b'<ComicInfo custom="yes"><Notes>old</Notes><Web>https://example.org</Web><Pages><Page Image="0" Bookmark="cover"/></Pages><Custom><Item>extra</Item></Custom></ComicInfo>'
        new = b'<ComicInfo><Notes>changed</Notes><Web/><Pages/><Title>New</Title></ComicInfo>'
        root = parse(reconcile(old, new))
        self.assertEqual(root.findtext('Notes'), 'old')
        self.assertEqual(root.findtext('Web'), 'https://example.org')
        self.assertEqual(root.find('Pages/Page').get('Bookmark'), 'cover')
        self.assertEqual(root.findtext('Custom/Item'), 'extra')
        self.assertEqual(root.findtext('Title'), 'New')
        self.assertEqual(root.get('custom'), 'yes')

    def test_annual_and_variant_identity_survives(self):
        old = b'<ComicInfo><Series>Annual</Series><Number>1</Number><Format>Annual</Format><ScanInformation>Variant B</ScanInformation></ComicInfo>'
        root = parse(reconcile(old, b'<ComicInfo><Series>Wrong</Series></ComicInfo>'))
        self.assertEqual(root.findtext('Series'), 'Annual')
        self.assertEqual(root.findtext('ScanInformation'), 'Variant B')

    def test_explicit_updates_replace_duplicate_fields(self):
        old = b'<ComicInfo><Volume>2</Volume><Volume>3</Volume></ComicInfo>'
        root = parse(reconcile(old, b'<ComicInfo/>', updates=overrides(volume=1)))
        self.assertEqual([n.text for n in root.findall('Volume')], ['1'])

    def test_explicit_policy_allows_replace_or_remove(self):
        old = b'<ComicInfo><Title>Old</Title><Notes>remove</Notes></ComicInfo>'
        root = parse(reconcile(old, b'<ComicInfo><Title>New</Title></ComicInfo>', replace_fields=('Title','Notes')))
        self.assertEqual(root.findtext('Title'), 'New')
        self.assertIsNone(root.find('Notes'))

    def test_existing_arc_numbers_survive_writer_omission(self):
        old = b'<ComicInfo><StoryArc>First,Second</StoryArc><StoryArcNumber>1,8</StoryArcNumber></ComicInfo>'
        root = parse(reconcile(old, b'<ComicInfo><StoryArc>Changed</StoryArc></ComicInfo>'))
        self.assertEqual(root.findtext('StoryArc'), 'First,Second')
        self.assertEqual(root.findtext('StoryArcNumber'), '1,8')

    def test_partial_original_arc_does_not_borrow_foreign_number(self):
        old = b'<ComicInfo><StoryArc>Existing</StoryArc></ComicInfo>'
        new = b'<ComicInfo><StoryArc>Different</StoryArc><StoryArcNumber>7</StoryArcNumber></ComicInfo>'
        root = parse(reconcile(old, new))
        self.assertEqual(root.findtext('StoryArc'), 'Existing')
        self.assertIsNone(root.find('StoryArcNumber'))

    def test_partial_explicit_arc_changes_are_rejected(self):
        for kwargs in ({'updates': {'StoryArc': 'Different'}}, {'replace_fields': ('StoryArc',)}):
            with self.assertRaises(ValueError):
                reconcile(b'<ComicInfo><StoryArc>Old</StoryArc><StoryArcNumber>2</StoryArcNumber></ComicInfo>', b'<ComicInfo/>', **kwargs)

    def test_mismatched_or_ambiguous_arc_counts_are_rejected(self):
        for new in (b'<ComicInfo><StoryArc>A,B</StoryArc><StoryArcNumber>1</StoryArcNumber></ComicInfo>', b'<ComicInfo><StoryArcNumber>1</StoryArcNumber></ComicInfo>', b'<ComicInfo><StoryArc>A</StoryArc><StoryArc>B</StoryArc><StoryArcNumber>1</StoryArcNumber></ComicInfo>'):
            with self.assertRaises(ValueError):
                reconcile(b'', new)

    def test_reconciliation_is_idempotent(self):
        old = b'<ComicInfo><Notes>old</Notes><Extra>one</Extra><Extra>two</Extra></ComicInfo>'
        updates = overrides(volume=1, age_rating='Teen')
        once = reconcile(old, b'<ComicInfo><Title>new</Title></ComicInfo>', updates=updates)
        self.assertEqual(reconcile(old, once, updates=updates), once)
        self.assertEqual(len(parse(once).findall('Extra')), 2)

    def test_rejects_malformed_oversize_dtd_and_wrong_root(self):
        for raw in (b'broken', b'<Other/>', b'<ComicInfo>'+b'a'*MAX_XML+b'</ComicInfo>', b'<!DOCTYPE ComicInfo [<!ENTITY x "secret">]><ComicInfo>&x;</ComicInfo>'):
            with self.assertRaises(ValueError):
                reconcile(b'', raw)

    def test_rejects_invalid_updates_and_result_overflow(self):
        for updates in ({'Notes': None}, {'bad tag':'x'}, {'Title':'\0'}):
            with self.assertRaises(ValueError):
                reconcile(b'', b'<ComicInfo/>', updates=updates)
        with self.assertRaises(ValueError):
            reconcile(b'', b'<ComicInfo/>', updates={'Title':'x'*MAX_XML})


if __name__ == '__main__':
    unittest.main()
