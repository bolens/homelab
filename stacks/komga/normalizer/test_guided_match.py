"""Guided source identity, exact alias scope and uncertain submission regressions."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

from guided_match import Guided, alias_match
from import_match import catalog
from normalize import digest, save


class GuidedTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.downloads, self.cache, self.state, self.library = [self.root / x for x in ('downloads', 'cache', 'state', 'library')]
        for p in (self.downloads, self.cache, self.state, self.library): p.mkdir()
        self.receipts = self.state / 'receipts'; self.receipts.mkdir()
        self.db = self.root / 'mylar.db'
        with closing(sqlite3.connect(self.db)) as db, db:
            db.executescript('''CREATE TABLE comics(ComicID TEXT,ComicName TEXT,ComicYear TEXT,ComicLocation TEXT);
            CREATE TABLE issues(IssueID TEXT,ComicID TEXT,Status TEXT,Issue_Number TEXT,IssueDate TEXT,Location TEXT);
            INSERT INTO comics VALUES('10','Test Comics','2017','');
            INSERT INTO issues VALUES('100','10','Wanted','1','2017-05-01','');
            INSERT INTO issues VALUES('101','10','Wanted','2','2017-06-01','');''')
        self.m = SimpleNamespace(state=self.state, receipts=self.receipts, roots=[self.downloads,self.cache],
            worker=SimpleNamespace(config={'mylar':{'config_dir':str(self.root)}},roots=[self.library]),
            settings={'auto_import':False,'ddl_cache':str(self.cache),'mylar_ddl_cache':'/config/mylar/cache'},
            idle=Mock(return_value=True), pending_ddl_names=Mock(return_value=set()), info=Mock(),
            import_submitted=False, mylar=Mock(return_value={'commands':[],'aliases':[]}))
        self.g = Guided(self.m); self.g.poll()
        self.source = self.archive('Test Comix 001 (2017).cbz')

    def archive(self, name, meta=None):
        path = self.downloads / name
        path.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(path,'w') as archive:
            archive.writestr('001.png',b'fixture')
            if meta: archive.writestr('ComicInfo.xml',meta)
        return path

    def command(self):
        proposal = self.g.propose(self.source)
        return {'id':'a'*32, **proposal, 'issueid':'100','comicid':'10','save_alias':False,'phase':'queued'}

    def force_calls(self):
        return [c for c in self.m.mylar.call_args_list if c.args[0]=='forceProcess']

    def test_separate_same_names_private_paths_and_evidence(self):
        first=self.g.propose(self.source)
        second=self.g.propose(self.archive('nested/'+self.source.name))
        self.assertNotEqual(first['source_token'],second['source_token'])
        public=json.dumps(self.g.proposals)
        self.assertNotIn(str(self.root),public)
        self.assertIn('filename series',public)
        self.assertEqual(self.g.proposals[0]['alias_scope'],{'series':'testcomix','year':'2017'})
        self.assertEqual(self.g.propose(self.source),first)

    def test_hostile_metadata_omits_only_its_guidance_and_keeps_other_problem_rows(self):
        valid = self.g.propose(self.source)
        problems = [{'name': self.source.name, 'kind': 'unmatched', **valid}]
        for index, series in enumerate(('https://host.invalid/private?token=fixture', 'Bad&#10;Series')):
            source = self.archive('Opaque %s.cbz' % index,
                '<ComicInfo><Series>%s</Series><Number>1</Number><Volume>2017</Volume></ComicInfo>' % series)
            before = digest(source)
            result = self.g.propose(source)
            self.assertEqual(result, {})
            problems.append({'name': source.name, 'kind': 'unmatched', **result})
            self.assertEqual(digest(source), before)
        self.assertEqual(len(problems), 3)
        self.assertEqual(len(self.g.proposals), 1)
        self.assertEqual(self.g.proposals[0]['source_token'], valid['source_token'])
        payload = json.dumps(self.g.proposals)
        self.assertNotIn('token=fixture', payload)
        self.assertNotIn('Bad', payload)
        self.assertEqual(problems[-1], {'name': 'Opaque 1.cbz', 'kind': 'unmatched'})
        # A bad catalog display field is also optional; it cannot break every report.
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("UPDATE comics SET ComicName='https://host.invalid/'")
        self.assertEqual(self.g.propose(self.source), {})
        self.assertEqual(len(self.g.proposals), 1)

    def test_explicit_confirmation_with_auto_import_disabled_preserves_source(self):
        command=self.command(); checksum=digest(self.source)
        self.g.process(command)
        self.assertEqual(len(self.force_calls()),1)
        self.assertEqual(self.force_calls()[0].kwargs['workflow_command'], command['id'])
        self.assertEqual(digest(self.source),checksum)
        self.assertEqual(digest(next(self.cache.glob('.mylar-recovery-*/*.cbz'))),checksum)
        self.g.process(command)
        self.assertEqual(len(self.force_calls()),1)

    def test_changed_stale_missing_and_symlink_sources_rejected(self):
        command=self.command()
        self.source.write_bytes(b'changed');self.g.process(command)
        self.assertEqual(self.m.mylar.call_args.kwargs['reason'],'changed_source')
        self.assertFalse(self.force_calls())
        command['id']='b'*32;command['version']='f'*64
        self.g.process(command)
        self.assertEqual(self.m.mylar.call_args.kwargs['reason'],'stale_source')
        command['id']='c'*32; command['version']=self.g.proposals[0]['version']
        self.source.unlink();self.source.symlink_to(self.db);self.g.process(command)
        self.assertEqual(self.m.mylar.call_args.kwargs['reason'],'changed_source')

    def test_active_and_already_downloaded_rejected(self):
        command=self.command();self.m.pending_ddl_names.return_value={self.source.name}
        self.g.process(command);self.assertEqual(self.m.mylar.call_args.kwargs['reason'],'source_unavailable')
        self.m.pending_ddl_names.return_value=set();command['id']='b'*32
        with closing(sqlite3.connect(self.db)) as db, db: db.execute("UPDATE issues SET Status='Downloaded' WHERE IssueID='100'")
        self.g.process(command);self.assertEqual(self.m.mylar.call_args.kwargs['reason'],'issue_unavailable')
        self.assertFalse(self.force_calls())

    def test_lost_force_response_and_restart_do_not_resubmit(self):
        command=self.command()
        def api(name, **kw):
            if name=='forceProcess': raise TimeoutError
            return {'commands':[command],'aliases':[]}
        self.m.mylar.side_effect=api
        self.g.process(command)
        self.assertEqual(self.m.mylar.call_args.kwargs['phase'],'review')
        Guided(self.m).poll()
        self.assertEqual(len(self.force_calls()),1)

    def test_rejected_processing_response_stays_review_without_resending(self):
        command=self.command()
        def api(name, **kwargs):
            if name=='forceProcess': raise RuntimeError('Mylar maintenance API rejected the request')
            return {}
        self.m.mylar.side_effect=api
        self.g.process(command);self.g.process(command)
        self.assertEqual(self.m.mylar.call_args.kwargs['phase'],'review')
        self.assertEqual(len(self.force_calls()),1)
        self.assertEqual(self.force_calls()[0].kwargs['workflow_command'],command['id'])
        self.assertTrue(self.source.is_file())

    def test_lost_claim_ack_is_never_blindly_retried(self):
        command=self.command()
        self.m.mylar.side_effect=TimeoutError
        with self.assertRaises(TimeoutError): self.g.process(command)
        self.m.mylar.side_effect=None
        self.g.process(command)
        self.assertEqual(self.m.mylar.call_args.kwargs['phase'],'review')
        self.assertFalse(self.force_calls())

    def test_unsupported_api_preserves_state_and_disables_guidance(self):
        command=self.command();self.g.process(command)
        before={p.name:p.read_bytes() for p in self.g.commands.glob('*.json')}
        self.m.mylar.side_effect=RuntimeError
        other=Guided(self.m);other.poll()
        self.assertFalse(other.available)
        self.assertEqual(other.propose(self.source),{})
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.g.commands.glob('*.json')})

    def test_exact_alias_year_number_metadata_and_id_guards(self):
        aliases=[{'id':'one','series':'testcomix','year':'2017','comicid':'10','enabled':True}]
        rows=catalog(self.db)
        self.assertEqual(alias_match(self.source,rows,aliases),{'issueid':'100','comicid':'10'})
        for name,meta in [('Test Comix 001 (2018).cbz',None),('Test Comix 001.cbz',None),
                          ('Test Comix 001 (2017) [__101__].cbz',None),
                          ('Test Comix 001 (2017).cbz','<ComicInfo><Number>2</Number></ComicInfo>'),
                          ('Test Comix 001 (2017).cbz','<ComicInfo><Series>Other</Series></ComicInfo>')]:
            self.assertIsNone(alias_match(self.archive(name,meta),rows,aliases))
        self.assertIsNone(alias_match(self.source,rows,[dict(aliases[0],enabled=False)]))

    def test_only_verified_selected_library_target_confirms_after_source_removed(self):
        command=self.command(); self.g.process(command)
        target=self.library/self.source.name; target.write_bytes(self.source.read_bytes())
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("UPDATE comics SET ComicLocation=?",(str(self.library),))
            db.execute("UPDATE issues SET Status='Downloaded',Location=? WHERE IssueID='100'",(target.name,))
        self.g.process(command)
        self.assertEqual(self.m.mylar.call_args.kwargs['phase'],'submitted')
        receipt={'kind':'duplicate','phase':'removed','source':str(self.source),'destination':str(target),
                 'sha256':digest(self.source),'destination_sha256':digest(target)}
        save(self.receipts/'verified.json',receipt);self.source.unlink()
        self.g.process(command)
        self.assertEqual(self.m.mylar.call_args.kwargs['phase'],'confirmed')

    def test_stale_submission_becomes_review_without_retry(self):
        command=self.command();self.g.process(command)
        with patch('guided_match.time.time',return_value=10**12): self.g.process(command)
        self.assertEqual(self.m.mylar.call_args.kwargs['phase'],'review')
        self.assertEqual(len(self.force_calls()),1)

    def test_alias_cannot_be_saved_from_conflicting_issue_number(self):
        command=self.command();command.update(issueid='101',save_alias=True)
        self.g.process(command)
        self.assertEqual(self.m.mylar.call_args.kwargs['reason'],'issue_unavailable')
        self.assertFalse(self.force_calls())

    def test_selection_cannot_escape_reported_candidates_or_identifier_scope(self):
        command=self.command();command['issueid']='999'
        self.g.process(command)
        self.assertEqual(self.m.mylar.call_args.kwargs['reason'],'issue_unavailable')
        command['id']='../../bad';self.g.process(command)
        self.assertFalse(self.force_calls())
        self.assertFalse((self.root/'bad.json').exists())

    def test_changed_during_claim_cannot_be_staged(self):
        command=self.command()
        def api(name, **kwargs):
            if name=='workflowAcknowledge' and kwargs['phase']=='claimed':
                self.source.write_bytes(b'changed during claim')
            return {}
        self.m.mylar.side_effect=api
        with self.assertRaises(RuntimeError): self.g.process(command)
        self.assertFalse(self.force_calls())
        self.assertFalse(list(self.cache.glob('.mylar-recovery-*')))

    def test_one_submission_per_cycle_and_busy_command_waits(self):
        command=self.command();self.m.idle.return_value=False
        self.g.process(command)
        self.assertFalse(list(self.g.commands.glob('*.json')))
        self.m.idle.return_value=True;self.g.process(command)
        self.source=self.archive('Test Comix 002 (2017).cbz')
        second=self.command();second.update(id='b'*32,issueid='101')
        self.g.process(second)
        self.assertEqual(len(self.force_calls()),1)
        self.assertFalse((self.g.commands/('b'*32+'.json')).exists())

    def test_alias_conflicting_rules_and_catalog_identity_remain_ambiguous(self):
        aliases=[{'id':'one','series':'testcomix','year':'2017','comicid':'10','enabled':True}]
        rows=catalog(self.db)
        self.assertIsNone(alias_match(self.source,rows+rows,aliases))
        self.assertIsNone(alias_match(self.source,rows,aliases+[dict(aliases[0],comicid='20')]))

    def test_pending_import_different_selection_cannot_claim_success(self):
        command=self.command();self.g.process(command)
        command['id']='b'*32;command['issueid']='101';self.m.import_submitted=False
        self.g.process(command)
        self.assertEqual(self.m.mylar.call_args.kwargs['phase'],'review')
        self.assertEqual(len(self.force_calls()),1)


if __name__=='__main__': unittest.main()
