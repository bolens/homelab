"""Exercise the complete native filename parser in the candidate image."""

from pathlib import Path
import sys
import tempfile
import sqlite3
import zipfile
from types import SimpleNamespace
import unittest

SOURCE = Path(sys.argv.pop(1))
sys.path[:0] = [str(SOURCE.parent), "/app/mylar3", "/app/mylar3/lib"]
import mylar
from mylar import filechecker
from unittest.mock import Mock, patch


class NativeMatchingTest(unittest.TestCase):
    def pure_annual_match(self, filename, title='Action Comics', *, enabled=True, year_override='unchanged'):
        config = SimpleNamespace(IGNORE_SEARCH_WORDS=[], CUSTOM_ISSUE_EXCEPTIONS=[],
            ANNUALS_ON=enabled, FOLDER_SCAN_LOG_VERBOSE=False, READ2FILENAME=False, ZERO_LEVEL_N=None)
        with patch.object(mylar, 'CONFIG', config), patch.object(filechecker, 'logger', Mock()):
            parser = filechecker.FileChecker(dir='/fixture', justparse=True, pp_mode=True)
            registered = filechecker.FileChecker(watchcomic=title, AlternateSearch=None)
            with patch('builtins.open', side_effect=AssertionError('Archive reads are forbidden')), \
                    patch('os.stat', side_effect=AssertionError('Archive stat is forbidden')):
                parsed = parser.parseit('/fixture', filename, '/fixture/capture')
                if year_override != 'unchanged':
                    parsed['issue_year'] = year_override
                return parsed, registered.matchIT(parsed)

    def test_qualified_annual_release_matches_base_title_with_evidence_preserved(self):
        for year in ('2021', '2022', '2025'):
            with self.subTest(year=year):
                title = 'Action Comics '+year+' Annual'
                parsed, result = self.pure_annual_match(title+' 001 ('+year+') (Digital).cbz')
                self.assertEqual(result['process_status'], 'match')
                self.assertEqual(result['justthedigits'], 'Annual 001')
                self.assertEqual(result['series_name'], title)
                self.assertEqual(result['issue_year'], year)
                self.assertEqual(result['series_volume'], parsed['series_volume'])
                self.assertIsNone(result['annual_comicid'])

        parsed, result = self.pure_annual_match('Action.Comics.2021.Annual.001.(2021).cbz')
        self.assertEqual(result['process_status'], 'match')
        self.assertEqual(result['justthedigits'], 'Annual 001')
        self.assertEqual(result['series_name'], parsed['series_name'])
        self.assertEqual(result['issue_year'], '2021')

    def test_annual_release_conflicting_or_missing_year_cannot_gain_match(self):
        for filename, override in [('Action Comics 2020 Annual 001 (2021).cbz', 'unchanged'),
                                   ('Action Comics 2021 Annual 001 (2021).cbz', None)]:
            with self.subTest(filename=filename, override=override):
                _, result = self.pure_annual_match(filename, year_override=override)
                self.assertEqual(result['process_status'], 'fail')

    def test_annual_release_keeps_registered_title_years_and_separate_annual_owner(self):
        filename = 'Action Comics 2021 001 (2025).cbz'
        _, wrong = self.pure_annual_match(filename)
        _, right = self.pure_annual_match(filename, 'Action Comics 2021')
        self.assertEqual(wrong['process_status'], 'fail')
        self.assertEqual(right['process_status'], 'match')
        self.assertEqual(right['justthedigits'], '001')
        _, separate = self.pure_annual_match('Action Comics 2021 Annual 001 (2021).cbz',
                                            'Action Comics 2021 Annual')
        self.assertEqual(separate['process_status'], 'match')
        self.assertEqual(separate['justthedigits'], '001')
        self.assertIsNone(separate['annual_comicid'])
        _, retained = self.pure_annual_match('The 2000 Adventures 2022 Annual 001 (2022).cbz',
                                            'The 2000 Adventures')
        self.assertEqual(retained['process_status'], 'match')
        self.assertEqual(retained['series_name'], 'The 2000 Adventures 2022 Annual')
        _, unrelated = self.pure_annual_match('The 2000 Adventures 2022 Annual 001 (2022).cbz',
                                             'The Adventures')
        self.assertEqual(unrelated['process_status'], 'fail')

    def test_normal_annual_regular_issue_and_disabled_mode_keep_native_purpose(self):
        _, annual = self.pure_annual_match('Action Comics Annual 001 (2021).cbz')
        self.assertEqual((annual['process_status'], annual['justthedigits']), ('match', 'Annual 001'))
        _, regular = self.pure_annual_match('Action Comics 001 (2021).cbz')
        self.assertEqual((regular['process_status'], regular['justthedigits']), ('match', '001'))
        _, disabled = self.pure_annual_match('Action Comics 2021 Annual 001 (2021).cbz', enabled=False)
        self.assertEqual(disabled['process_status'], 'fail')

    def annual_lookup_keys(self, parsed):
        import ast
        import re
        from mylar import file_identity
        tree = ast.parse((SOURCE / 'PostProcessor.py').read_text())
        native = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                      and n.name == '_publication_process_original')
        loop = next(n for n in ast.walk(native) if isinstance(n, ast.For)
                    and isinstance(n.target, ast.Name) and n.target.id == 'fl'
                    and ast.unparse(n.iter) == "filelist['comiclist']")
        start = next(i for i, n in enumerate(loop.body) if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'annual_title' for t in n.targets))
        end = next(i for i in range(start, len(loop.body)) if isinstance(loop.body[i], ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'watchvals' for t in loop.body[i].targets))
        selected = ast.For(target=ast.Name(id='fl', ctx=ast.Store()),
            iter=ast.List(elts=[ast.Name(id='parsed', ctx=ast.Load())], ctx=ast.Load()),
            body=loop.body[start:end], orelse=[])
        import sqlite3
        database = sqlite3.connect(':memory:')
        database.row_factory = sqlite3.Row
        database.execute('CREATE TABLE comics(DynamicComicName TEXT)')
        database.executemany('INSERT INTO comics VALUES (?)', [(value,) for value in
            ('actioncomics', 'actioncomics2021', 'actioncomics2021annual', 'actioncomics2022annual',
             '2000adventures2022annual')])
        scope = dict(parsed=parsed, self=SimpleNamespace(issueid=None, comicid=None), re=re,
                     logger=Mock(), module='[POST-PROCESSING]', mylar=mylar, filechecker=filechecker,
                     file_identity=file_identity, alt_list=[],
                     myDB=SimpleNamespace(select=lambda sql, args: database.execute(sql, args).fetchall()))
        try:
            with patch.object(mylar, 'CONFIG', SimpleNamespace(ANNUALS_ON=True)), \
                    patch('builtins.open', side_effect=AssertionError('No archive reads')):
                exec(compile(ast.fix_missing_locations(ast.Module(body=[selected], type_ignores=[])),
                             'PostProcessor.py', 'exec'), scope)
            self.last_lookup_candidates = [row['DynamicComicName'] for row in scope.get('comicseries', [])]
        finally:
            database.close()
        return scope.get('loopchk')

    def test_native_candidate_lookup_agrees_with_annual_comparator_and_keeps_title_year(self):
        for year in ('2021', '2022', '2025'):
            parsed, matched = self.pure_annual_match('Action Comics '+year+' Annual 001 ('+year+').cbz')
            self.assertEqual(matched['process_status'], 'match')
            self.assertIn('actioncomics', self.annual_lookup_keys(parsed))
            # Exercise the actual alternate-title qualifier path as well.
            parsed['alt_series'] = 'Action Comics '+year+' Annual'
            self.assertIn('actioncomics', self.annual_lookup_keys(parsed))
        parsed, _ = self.pure_annual_match('Action Comics 2021 001 (2025).cbz', 'Action Comics 2021')
        self.assertIn('actioncomics2021', self.annual_lookup_keys(parsed))
        self.assertNotIn('actioncomics', self.annual_lookup_keys(parsed))
        parsed['series_name'] = 'Action Comics 2022 Annual'
        parsed['issue_year'] = None
        keys = self.annual_lookup_keys(parsed)
        self.assertNotIn('actioncomics', keys)
        self.assertIn('actioncomics2022annual', keys)

    def test_literal_registered_annual_title_keeps_its_independent_publication_year(self):
        for title, year in [('Action Comics 2021 Annual', '2025'),
                            ('The 2000 Adventures 2022 Annual', '2025')]:
            with self.subTest(title=title):
                parsed, own = self.pure_annual_match(title+' 001 ('+year+').cbz', title)
                self.assertEqual(own['process_status'], 'match')
                self.assertEqual(own['justthedigits'], '001')
                self.assertEqual(own['issue_year'], year)
                self.assertEqual(own['series_name'], title)
                self.assertIsNone(own['annual_comicid'])
                self.annual_lookup_keys(parsed)
                expected = ''.join(c for c in title.lower() if c.isalnum()).removeprefix('the')
                self.assertIn(expected, self.last_lookup_candidates)
        # The same qualifier cannot bridge to the unrelated bare parent with a conflicting year.
        _, wrong = self.pure_annual_match('Action Comics 2021 Annual 001 (2025).cbz')
        self.assertEqual(wrong['process_status'], 'fail')

    def annual_special_candidate_stage(self, matched, title, source=None):
        import ast
        import re
        from mylar import file_identity
        tree = ast.parse(source if source is not None else (SOURCE / 'PostProcessor.py').read_text())
        stage = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                     and "'special' in tmpseriesname.lower()" in ast.unparse(n.test)
                     and "cs['DynamicName']" in ast.unparse(n.test))
        owner = next(n for n in ast.walk(tree) if isinstance(n, (ast.If, ast.For, ast.FunctionDef))
                     and stage in n.body)
        start = owner.body.index(stage)
        end = next(i for i in range(start+1, len(owner.body)) if isinstance(owner.body[i], ast.If)
                   and 'alt_listing' in ast.unparse(owner.body[i].test)
                   and "cs['WatchValues']['Type']" in ast.unparse(owner.body[i].test))
        registered = filechecker.FileChecker(watchcomic=title, AlternateSearch=None)
        dynamic = registered.dynamic_replace(title)['mod_seriesname']
        scope = dict(mylar=mylar, re=re, file_identity=file_identity, as_d=registered,
                     watchmatch=matched, tmpseriesname=dynamic,
                     cs={'DynamicName': re.sub(r'[\|\s]', '', dynamic.lower()).strip(),
                         'WatchValues': {'Type': 'Print'}}, alt_list=[])
        with patch.object(mylar, 'CONFIG', SimpleNamespace(ANNUALS_ON=True)), \
                patch('builtins.open', side_effect=AssertionError('No archive reads')), \
                patch('os.stat', side_effect=AssertionError('No archive stat')):
            exec(compile(ast.fix_missing_locations(ast.Module(body=owner.body[start:end], type_ignores=[])),
                         'PostProcessor.py', 'exec'), scope)
            return eval(compile(ast.Expression(body=owner.body[end].test), 'PostProcessor.py', 'eval'), scope)

    def test_literal_annual_special_owner_reaches_later_native_candidate_gate_without_exception(self):
        for title in ('Action Comics Special 2021 Annual', 'The 2000 Adventures Special 2022 Annual'):
            with self.subTest(title=title):
                _, matched = self.pure_annual_match(title+' 001 (2025).cbz', title)
                self.assertEqual(matched['process_status'], 'match')
                self.assertEqual(matched['justthedigits'], '001')
                self.assertEqual(matched['issue_year'], '2025')
                self.assertIsNone(matched['annual_comicid'])
                # The genuine later stage retains its original strict candidate refusal.
                self.assertFalse(self.annual_special_candidate_stage(matched, title))

    def test_annual_lookup_rejects_stale_or_mutated_marked_later_stage(self):
        from patch_postprocessing import processor, LATER_ANNUAL_LOOKUP
        post = (SOURCE / 'PostProcessor.py').read_text()
        stale = "                                            release_title = file_identity.annual_release_title(watchmatch['series_name'], watchmatch['issue_year'])\n" + "                                            if release_title is not None:" + LATER_ANNUAL_LOOKUP.split("                                            if release_title is not None:", 1)[1]
        # A marked stale draft or changed catch cannot silently count as current source.
        for replacement in (stale, LATER_ANNUAL_LOOKUP.replace('except ValueError:', 'except LookupError:', 1)):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                processor(post.replace(LATER_ANNUAL_LOOKUP, replacement, 1))

    def test_annual_release_checked_patch_reuses_one_helper_and_preserves_later_gates(self):
        from patch_file_matching import patched
        from patch_postprocessing import processor
        checker = (SOURCE / 'filechecker.py').read_text()
        post = (SOURCE / 'PostProcessor.py').read_text()
        self.assertEqual(patched('filechecker.py', checker), checker)
        self.assertEqual(processor(post), post)
        self.assertIn('file_identity.annual_release_title', checker)
        self.assertIn('file_identity.annual_release_title', post)
        self.assertIn("issuechk = myDB.select(\"SELECT * from annuals WHERE ComicID=? AND Int_IssueNumber=? AND NOT Deleted\"", post)
        self.assertIn("if int(watch_issueyear) == int(watchmatch['issue_year']):", post)
        self.assertIn("if int(tmp_watchmatch_vol) == int(tmp_watchlist_vol):", post)

    def test_native_year_named_annuals_get_distinct_verified_release_ids(self):
        from mylar import file_identity
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        database = sqlite3.connect(':memory:')
        database.row_factory = sqlite3.Row
        self.addCleanup(database.close)
        database.executescript('''CREATE TABLE comics(ComicID,ComicName,ComicYear,ComicVersion,Type);
            CREATE TABLE issues(IssueID,ComicID,Issue_Number);
            CREATE TABLE annuals(IssueID,ComicID,Issue_Number,ReleaseComicName,ReleaseComicID,Deleted,IssueDate);
            INSERT INTO comics VALUES('10','Grimm Fairy Tales','2016',NULL,'Print');
            INSERT INTO annuals VALUES('100','10','1','Grimm Fairy Tales 2021 Annual','20',0,'2021-01-01'),
                ('200','10','1','Grimm Fairy Tales 2022 Annual','21',0,'2022-01-01');''')
        listing = []
        for year, issueid in [('2021','100'),('2022','200')]:
            name = 'Grimm Fairy Tales '+year+' Annual ('+year+').cbz'
            with zipfile.ZipFile(folder/name,'w') as archive:
                archive.writestr('page.jpg',b'fixture preserved')
                archive.writestr('ComicInfo.xml','<ComicInfo><Series>Grimm Fairy Tales '+year+' Annual</Series><Number>1</Number><Web>https://comicvine.gamespot.com/issue/4000-'+issueid+'/</Web></ComicInfo>')
        with patch.object(filechecker,'logger',Mock()), patch.object(mylar,'CONFIG',SimpleNamespace(IGNORE_SEARCH_WORDS=[],CUSTOM_ISSUE_EXCEPTIONS=[],ANNUALS_ON=True,FOLDER_SCAN_LOG_VERBOSE=False,ENFORCE_PERMS=False,ENABLE_TORRENTS=False,READ2FILENAME=False)):
            checker = filechecker.FileChecker(dir=str(folder),watchcomic='Grimm Fairy Tales',Publisher='Fixture',AlternateSearch='Grimm Fairy Tales 2021 Annual!!20##Grimm Fairy Tales 2022 Annual!!21',comic_type='Print')
            listing = checker.listFiles()['comiclist']
        self.assertEqual(len(listing),2)
        self.assertTrue(all(r['AnnualComicID'] is None for r in listing))
        adapter = Mock()
        adapter.select.side_effect = lambda sql,args:database.execute(sql,args).fetchall()
        series=dict(ComicID='10',ComicName='Grimm Fairy Tales',ComicYear='2016',ComicVersion=None,Type='Print')
        file_identity.validate_rescan(adapter,series,[dict(comiclist=listing)])
        self.assertEqual({r['IssueYear']:r['AnnualComicID'] for r in listing},{'2021':'20','2022':'21'})
        adapter.action.assert_not_called()
        adapter.upsert.assert_not_called()

    def test_native_duplicate_check_uses_annual_owner_and_retains_conflicts(self):
        from mylar import helpers, db
        from patch_postprocessing import duplicate_ownership
        source = (SOURCE / 'helpers.py').read_text()
        self.assertEqual(duplicate_ownership(source), source)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / 'Annual.cbz'
        path.write_bytes(b'original retained')
        database = sqlite3.connect(':memory:')
        database.row_factory = sqlite3.Row
        self.addCleanup(database.close)
        database.executescript('''CREATE TABLE issues(IssueID,ComicID,Status,Location,ComicSize);
            CREATE TABLE annuals(IssueID,ComicID,Status,Location,ComicSize,Deleted);
            CREATE TABLE comics(ComicID,ComicName,ComicLocation);
            INSERT INTO comics VALUES('10','Parent','/parent'),('20','Standalone','/standalone');
            INSERT INTO issues VALUES('100','20','Downloaded','wrong.cbz',100);
            INSERT INTO annuals VALUES('100','10','Wanted',NULL,NULL,0);''')
        adapter = Mock()
        adapter.selectone.side_effect = lambda sql, args: database.execute(sql, args)
        with patch.object(db, 'DBConnection', return_value=adapter), patch.object(helpers, 'logger', Mock()):
            self.assertEqual(helpers.duplicate_filecheck(str(path), ComicID='10', IssueID='100'), {'action': 'write'})
            self.assertEqual(helpers.duplicate_filecheck(str(path), ComicID='20', IssueID='100'), {'action': None})
            database.execute("UPDATE annuals SET Deleted=1")
            self.assertEqual(helpers.duplicate_filecheck(str(path), ComicID='10', IssueID='100'), {'action': None})
            database.execute('DELETE FROM annuals')
            database.execute("UPDATE issues SET Status='Wanted'")
            self.assertEqual(helpers.duplicate_filecheck(str(path), ComicID='20', IssueID='100'), {'action': 'write'})
        adapter.action.assert_not_called()
        adapter.upsert.assert_not_called()
        self.assertEqual(path.read_bytes(), b'original retained')

    def test_native_rescan_rejects_identity_before_any_catalog_action(self):
        from mylar import updater, db
        import inspect
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        name = 'Comic 016 (2021).cbz'
        path = folder/name
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('page.jpg', b'fixture')
            archive.writestr('ComicInfo.xml', '<ComicInfo><Series>Comic</Series><Web>https://comicvine.gamespot.com/issue/4000-100/</Web></ComicInfo>')
        database = sqlite3.connect(':memory:')
        database.row_factory = sqlite3.Row
        self.addCleanup(database.close)
        database.executescript('''CREATE TABLE comics(ComicID,ComicName,ComicYear,ComicVersion,Type);
            CREATE TABLE issues(IssueID,ComicID,Issue_Number,IssueDate);
            CREATE TABLE annuals(IssueID,ComicID,Issue_Number,ReleaseComicName,ReleaseComicID,Deleted);
            INSERT INTO comics VALUES('10','Comic','2020','v2','Print');
            INSERT INTO issues VALUES('100','10','15','2020-01-01'),('101','10','16','2021-01-01');''')
        series = dict(ComicID='10', ComicName='Comic', ComicYear='2020', ComicVersion='v2', Type='Print',
                      AlternateSearch=None, Status='Active', Corrected_Type=None, ComicPublisher='Fixture',
                      Total=2, ComicLocation=str(folder))
        adapter = Mock()
        adapter.select.side_effect = lambda sql, args: database.execute(sql, args).fetchall()
        adapter.selectone.return_value.fetchone.return_value = series
        parsed = self.parse(name, 'Comic')
        listing = dict(comiccount=1, comiclist=[dict(ComicFilename=name, ComicLocation=str(folder),
                                                   JusttheDigits=str(parsed['issue_number']), AnnualComicID=None)])
        with patch.object(db, 'DBConnection', return_value=adapter), \
                patch.object(filechecker.FileChecker, 'listFiles', return_value=listing), \
                patch.object(updater, 'logger', Mock()), \
                patch.object(mylar, 'CONFIG', SimpleNamespace(MULTIPLE_DEST_DIRS=None)):
            with self.assertRaises(ValueError):
                inspect.unwrap(updater.forceRescan)('10')
            database.execute("UPDATE issues SET Issue_Number='15' WHERE IssueID='101'")
            new_name = 'Comic 015 (2021).cbz'
            path = path.rename(folder/new_name)
            parsed = self.parse(new_name, 'Comic')
            listing['comiclist'][0].update(ComicFilename=new_name, JusttheDigits=str(parsed['issue_number']))
            with self.assertRaises(ValueError):
                inspect.unwrap(updater.forceRescan)('10')
        adapter.action.assert_not_called()
        adapter.upsert.assert_not_called()
        self.assertTrue(path.is_file())
        self.assertEqual(database.execute('SELECT IssueID,Issue_Number FROM issues ORDER BY IssueID').fetchall()[0]['Issue_Number'], '15')

    def test_rescan_identity_guard_precedes_duplicate_and_catalog_changes(self):
        source = (SOURCE / "updater.py").read_text()
        from patch_file_matching import patched
        self.assertEqual(patched("updater.py", source), source)
        start = source.index("def forceRescan(")
        end = source.find("\ndef ", start + 1)
        rescan = source[start:end if end != -1 else None]
        guard = rescan.index("publication_rescan.validate_rescan(myDB, rescan, fca, booktype=booktype)")
        self.assertLess(guard, rescan.index("    fcb = []"))
        self.assertLess(guard, rescan.index("d_issues.append"))

    def parse(self, name, title, kind=None, number=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        (Path(temp.name) / name).write_bytes(b"fixture")
        checker = filechecker.FileChecker(
            dir=temp.name,
            watchcomic=title,
            justparse=True,
            comic_type=kind,
            single_issue_number=number,
        )
        with (
            patch.object(filechecker, "logger", Mock()),
            patch.object(
                mylar,
                "CONFIG",
                SimpleNamespace(
                    IGNORE_SEARCH_WORDS=[], ANNUALS_ON=True, CUSTOM_ISSUE_EXCEPTIONS=[],
                    FOLDER_SCAN_LOG_VERBOSE=False,
                ),
            ),
        ):
            return checker.parseit(temp.name, name)

    def test_dotted_release_names_keep_numbers_and_group(self):
        for number in ('001', '001.5', '001.MU'):
            value = self.parse('Series.Name.'+number+'.(2020).(Digital)-Son.of.Ultron-Empire.cbz', 'Series Name', 'Print')
            self.assertEqual(str(value['issue_number']).lower().replace(' ', '.').lstrip('0'), number.lstrip('0').lower())
            self.assertEqual(value['scangroup'], 'Son.of.Ultron-Empire')

    def test_release_parser_upgrade_is_idempotent_for_legacy_marker(self):
        from patch_release_naming import PRINT_FIELDS, scanner
        source=(SOURCE/'filechecker.py').read_text()
        self.assertEqual(scanner(source),source)
        legacy=source.replace(PRINT_FIELDS,'').replace('release_naming.release_number(modfilename, self)',
                                                        'release_naming.release_number(modfilename)')
        self.assertNotEqual(legacy,source)
        self.assertEqual(scanner(legacy),source)
        self.assertEqual(scanner(scanner(legacy)),source)

    def test_dotted_print_run_and_four_digit_issue_keep_publication_year(self):
        for number in ('1019','1020'):
            value=self.parse('Detective.Comics.v3.'+number+'.(2020).(Webrip)-The.Last.Kryptonian-DCP.cbz',
                             'Detective Comics','Print')
            self.assertIsNotNone(value)
            self.assertEqual(value['series_name'],'Detective Comics')
            self.assertEqual(value['issue_number'],number)
            self.assertEqual(value['issue_year'],'2020')
            self.assertEqual(value['series_volume'],'3')

    def test_conflicting_dotted_print_year_remains_for_review(self):
        value=self.parse('Detective.Comics.v3.1019.(2020).(2021).(Webrip)-Group.cbz',
                         'Detective Comics','Print')
        self.assertTrue(value is None or value['series_name']!='Detective Comics' or value['issue_year']!='2020')

    def test_dotted_numeric_title_cannot_become_part_of_issue_number(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        folder=Path(temp.name)
        name='Gargoyles.Winter.Special.2025.001.(2025).(One.Shot).cbz'
        (folder/name).write_bytes(b'parser fixture')
        with patch.object(filechecker,'logger',Mock()), patch.object(mylar,'CONFIG',SimpleNamespace(
                IGNORE_SEARCH_WORDS=[],CUSTOM_ISSUE_EXCEPTIONS=[],ANNUALS_ON=True,
                FOLDER_SCAN_LOG_VERBOSE=False,ENFORCE_PERMS=False,ENABLE_TORRENTS=False,READ2FILENAME=False)):
            checker=filechecker.FileChecker(dir=str(folder),watchcomic='Gargoyles Winter Special 2025',
                                            comic_type='One-Shot',single_issue_number='1')
            entries=checker.listFiles()['comiclist']
        self.assertEqual(len(entries),1)
        self.assertEqual(entries[0]['JusttheDigits'],'001')
        self.assertEqual(entries[0]['ComicName'],'Gargoyles Winter Special 2025')

    def test_collected_release_preserves_distinct_series_and_issue_volumes(self):
        for kind in ('GN', 'TPB', 'HC'):
            value = self.parse('Series.Name.v2.v005.('+kind+').(2020).(Digital)-Group.cbz',
                               'Series Name', kind, '5')
            self.assertIsNotNone(value)
            self.assertEqual(value['series_name'], 'Series Name')
            self.assertEqual(int(value['issue_number']), 5)
            self.assertEqual(value['scangroup'], 'Group')

    def test_title_ending_in_year_survives_regular_issue_parser(self):
        value = self.parse(
            "American Vampire 1976 001 (2020).cbz", "American Vampire 1976"
        )
        self.assertEqual(value["series_name"], "American Vampire 1976")
        self.assertEqual(int(value["issue_number"]), 1)

    def test_unnumbered_numeric_title_uses_unique_catalog_identity(self):
        value = self.parse("1984 (2020).cbz", "1984", "GN", "1")
        self.assertEqual(value["series_name"], "1984")
        self.assertEqual(str(value["issue_number"]), "1")
        self.assertEqual(value["booktype"], "GN")

    def test_unicode_title_separator_keeps_native_issue_number(self):
        value = self.parse("Grimm Tales of Terror v5 007 – Slit Mouthed Woman (2025).cbz", "Grimm Tales of Terror", "Print")
        self.assertEqual(int(value['issue_number']), 7)
        from patch_file_matching import patched
        source = (SOURCE / 'filechecker.py').read_text()
        self.assertEqual(patched('filechecker.py', source), source)

    def test_ordinary_title_and_issue_unchanged(self):
        value = self.parse("Batman 003 (2020).cbz", "Batman")
        self.assertEqual(value["series_name"], "Batman")
        self.assertEqual(int(value["issue_number"]), 3)


if __name__ == "__main__":
    unittest.main()
