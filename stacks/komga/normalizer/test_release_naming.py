"""Release labels survive rendering, and unsupported identities stay reviewable."""
import unittest
from release_naming import render, issue_number, policy


class NamingTest(unittest.TestCase):
    def proposal(self, **values):
        return dict(dict(series='Series Name', source='/comics/Series Name 001 (2020) (Digital) (Son of Ultron-Empire).cbz',
                         issueid='123', number='1', year='2020', type='Print', volume=None,
                         group='Son of Ultron-Empire'), **values)

    def test_preference_and_roundtrip(self):
        data = self.proposal()
        name = render(data)
        self.assertEqual(name, 'Series.Name.001.(2020).(Digital)-Son.of.Ultron-Empire.cbz')
        data.update(source='/comics/'+name, group='Son.of.Ultron-Empire')
        self.assertEqual(render(data), name)

    def test_edition_source_language_and_variant_survive(self):
        data = self.proposal(source='/comics/Series 1 (2020) (Deluxe Edition) (Cover B) (French) (Digital-Son of Ultron-Empire).cbz')
        self.assertEqual(render(data), 'Series.Name.001.(2020).(Deluxe.Edition).(Cover.B).(French).(Digital)-Son.of.Ultron-Empire.cbz')

    def test_annual_volume_collected_and_no_invented_group(self):
        self.assertTrue(render(self.proposal(series='Series Annual', volume='2')).startswith('Series.Annual.v2.001.'))
        data = self.proposal(type='HC', source='/comics/Series 1 (HC) (2020).cbz', group=None)
        self.assertEqual(render(data), 'Series.Name.v001.(HC).(2020).cbz')
        self.assertEqual(render(dict(data, source='/comics/'+render(data))), render(data))

    def test_bare_edition_labels_are_held_instead_of_lost(self):
        for label in ('The Deluxe Edition', 'Anniversary Edition', 'Collectors Edition', 'Expanded Edition', 'Cover B', '2nd Printing', "Director's Cut"):
            with self.assertRaisesRegex(ValueError, 'Unbracketed edition'):
                render(self.proposal(source='/comics/Series Name 001 - '+label+' (2020).cbz', group=None))
        data = self.proposal(series='The Walking Dead Deluxe', source='/comics/The Walking Dead Deluxe 001 (2020) (Digital)-Cover-Group.cbz', group='Cover-Group')
        self.assertEqual(render(data), 'The.Walking.Dead.Deluxe.001.(2020).(Digital)-Cover-Group.cbz')
        with self.assertRaisesRegex(ValueError, 'Unbracketed edition'):
            render(self.proposal(type='HC', source='/comics/Series Name 001 - Omnibus (2020).cbz', group=None))

    def test_fraction_variants_zero_and_negative_numbers(self):
        for source, target in [('½','000.5'),('1¼','001.25'),('1.50','001.5'),('0','000'),('-1','-001'),('1 MU','001.MU')]:
            self.assertEqual(issue_number(source), target)
        with self.assertRaises(ValueError):issue_number("Director's Cut")

    def test_conflicting_year_id_and_invalid_labels_do_not_rename(self):
        for source in ['/comics/Series 1 (2019).cbz', '/comics/Series 1 [__456__] (2020).cbz']:
            with self.assertRaises(ValueError):render(self.proposal(source=source))
        with self.assertRaises(ValueError):render(self.proposal(series='bad\nname'))
        self.assertEqual(render(self.proposal(source='/comics/Series 1 [__123__] (2020).cbz', group=None)), 'Series.Name.001.(2020).cbz')

    def test_redundant_hash_issue_block_is_removed_only_for_exact_number(self):
        data=self.proposal(series='RWBY',number='7',year='2019',group='Glorith-HD',
                           source='/comics/RWBY 2019-11-27 (#07) (digital) (Glorith-HD).cbz')
        self.assertEqual(render(data),'RWBY.007.(2019).(digital)-Glorith-HD.cbz')
        self.assertEqual(render(dict(data,source='/comics/'+render(data))),render(data))
        with self.assertRaisesRegex(ValueError,'number'):
            render(dict(data,source=data['source'].replace('#07','#08')))
        self.assertIn('(Cover.B)',render(dict(data,source=data['source'].replace('#07','Cover B'))))

    def test_disabled_by_default_and_requires_coordination(self):
        self.assertFalse(policy({})['enabled'])
        with self.assertRaises(ValueError):policy({'release_naming':{'enabled':True}})
        with self.assertRaises(ValueError):policy({'release_naming':{'batch_size':True}})


if __name__ == '__main__':unittest.main()
