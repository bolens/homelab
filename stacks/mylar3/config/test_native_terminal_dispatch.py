"""Finite real-queue/source dispatch controls; native ACK execution is root image-gated."""
import argparse
import ast
from contextlib import closing
import importlib.util
from pathlib import Path
import queue
import sqlite3
import tempfile
import unittest
import sys

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('migration',HERE/'patch_publication_processing.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
SOURCE=HERE.parent/'preimages/PostProcessor.py'


def producer_type():
    patched=p.patched_source(SOURCE.read_text())
    process=next(n for n in ast.walk(ast.parse(patched)) if isinstance(n,ast.FunctionDef) and n.name=='Process')
    process.decorator_list=[]
    # Real wrapper and exact owned producer/skip/stop statements, with a small
    # explicit source/SQLite seam instead of pretending full native admission.
    wrapper=ast.unparse(process)
    original='''def _publication_process_original(self):
    for member in self.initial:
        self.Process_next(*member)
    for ml in self.manual:
        comicid=ml['ComicID'];issueid=ml['IssueID']
SKIP
        self.Process_next(ml['AnnualType'],comicid,issueid,ml['ComicLocation'])
    if self.inject_review:self.valreturn.append({'mode':'review','reason':'fixture-failure'})
    if self.early_failure:
        self.valreturn.append({'self.log':self.log,'mode':'stop'})
        self.queue.put(self.valreturn)
    if self.raise_after:raise RuntimeError('fixture-unexpected')
    if self._publication_terminal_scope:return
    self.valreturn.append({'self.log':self.log,'mode':'stop'})
    return self.queue.put(self.valreturn)
'''.replace('SKIP','\n'.join(line[12:] for line in p.TERMINAL_SKIP.rstrip().splitlines()))
    success=p.TERMINAL_SUCCESS
    nxt='''def Process_next(self,annchk,comicid,issueid,path):
    subpath,orig_filename=__import__('os').path.split(path)
    _publication_terminal_source=__import__('os').path.join(subpath,orig_filename)
    source=Path(path)
    if not source.is_file():raise FileNotFoundError(path)
    if self.reject_ack:raise RuntimeError('fixture-ACK-not-committed')
    with closing(sqlite3.connect(self.database)) as db:
        db.execute('INSERT INTO events VALUES (?,?,?,?)',(annchk,comicid,issueid,path));db.commit()
    source.unlink()
SUCCESS
'''.replace('SUCCESS','\n'.join(line[8:] for line in success.rstrip().splitlines()))
    text='class Producer:\n'+ '\n'.join('    '+line for line in (wrapper+'\n'+original+'\n'+nxt).splitlines())
    ns={'queue':queue,'sqlite3':sqlite3,'Path':Path,'closing':closing};exec(compile(text,'<exact-terminal-source-fragments>','exec'),ns)
    return ns['Producer']


class Dispatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.type=producer_type()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.obj=self.type();self.obj.queue=queue.Queue();self.obj.valreturn=[];self.obj.log=''
        self.obj._log=lambda text:setattr(self.obj,'log',self.obj.log+text)
        self.obj.initial=[];self.obj.manual=[];self.obj.inject_review=False;self.obj.raise_after=False;self.obj.reject_ack=False;self.obj.early_failure=False
        self.obj.database=self.root/'events.sqlite'
        with closing(sqlite3.connect(self.obj.database)) as db:db.execute('CREATE TABLE events (kind,parent,issue,path)')
    def member(self,issue='12',path='one.cbz',kind='no',parent='34'):
        source=self.root/path;source.write_bytes(b'fixture archive bytes')
        return (kind,parent,issue,str(source))
    @staticmethod
    def manual(member):
        kind,parent,issue,path=member
        return dict(AnnualType=None if kind=='no' else 'Annual',ComicID=parent,IssueID=issue,ComicLocation=path)
    def packet(self):
        result=self.obj.queue.get_nowait();self.assertTrue(self.obj.queue.empty());return result
    def test_single_discovery_original_success_not_readmitted(self):
        member=self.member();self.obj.initial=[member];self.obj.manual=[self.manual(member)]
        self.obj.Process();packet=self.packet();self.assertEqual(packet,self.obj.valreturn);self.assertEqual(len(packet),1)
        with closing(sqlite3.connect(self.obj.database)) as db:self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone(),(1,))
        self.assertFalse(Path(member[3]).exists())
    def test_manual_multiple_distinct_owner_source_rows(self):
        members=[self.member(),self.member('13','two.cbz')];self.obj.manual=[self.manual(m) for m in members]
        self.obj.Process();self.assertEqual([r['issueid'] for r in self.packet()],['12','13'])
    def test_same_owner_different_source_is_not_skipped(self):
        first=self.member();second=self.member(path='two.cbz');self.obj.initial=[first];self.obj.manual=[self.manual(second)]
        self.obj.Process();self.assertEqual(len(self.packet()),2);self.assertFalse(Path(second[3]).exists())
    def test_direct_next_has_one_owned_stop(self):
        self.obj.Process_next(*self.member());self.assertEqual(len(self.packet()),1)
    def test_annual_success_same_source_is_single(self):
        m=self.member(kind='yes');self.obj.initial=[m];self.obj.manual=[self.manual(m)]
        self.obj.Process();self.assertEqual(len(self.packet()),1)
    def test_annual_regular_separation_is_not_skipped(self):
        m=self.member(kind='yes');self.obj.initial=[m];self.obj.manual=[dict(self.manual(m),AnnualType=None)]
        with self.assertRaises(FileNotFoundError):self.obj.Process()
        self.assertTrue(self.obj.queue.empty())
    def test_other_parent_same_source_is_not_skipped(self):
        m=self.member();self.obj.initial=[m];self.obj.manual=[dict(self.manual(m),ComicID='35')]
        with self.assertRaises(FileNotFoundError):self.obj.Process()
    def test_mixed_success_review_preserved(self):
        self.obj.initial=[self.member()];self.obj.inject_review=True;self.obj.Process()
        self.assertEqual([r['mode'] for r in self.packet()],['stop','review'])
    def test_mixed_success_early_failure_rows_not_removed_or_promoted(self):
        self.obj.initial=[self.member()];self.obj.early_failure=True;self.obj.Process()
        first=self.obj.queue.get_nowait();last=self.obj.queue.get_nowait()
        self.assertTrue(self.obj.queue.empty());self.assertEqual(first,last)
        self.assertEqual(len(last),2);self.assertEqual(set(last[-1]),{'self.log','mode'})
        self.assertEqual(last[0]['issueid'],'12')
    def test_ack_failure_never_produces_completion(self):
        m=self.member();self.obj.initial=[m];self.obj.reject_ack=True
        with self.assertRaisesRegex(RuntimeError,'ACK-not-committed'):self.obj.Process()
        self.assertTrue(Path(m[3]).exists());self.assertEqual(self.obj.valreturn,[]);self.assertTrue(self.obj.queue.empty())
        self.assertFalse(hasattr(self.obj,'_publication_terminal_scope'))
    def test_unexpected_exception_never_emits_completion(self):
        self.obj.initial=[self.member()];self.obj.raise_after=True
        with self.assertRaisesRegex(RuntimeError,'unexpected'):self.obj.Process()
        self.assertTrue(self.obj.queue.empty());self.assertFalse(hasattr(self.obj,'_publication_terminal_scope'))
    def test_stale_invocation_receipt_refused(self):
        self.obj._publication_terminal_scope=[]
        with self.assertRaisesRegex(RuntimeError,'already active'):self.obj.Process()
        self.assertTrue(self.obj.queue.empty())
    def test_injected_stop_row_is_not_completion(self):
        self.obj.valreturn=[dict(mode='stop',issueid='12',comicid='34')];self.obj.Process()
        self.assertEqual(len(self.packet()),2)  # Generic early/no-success stop retained.
    def test_emitted_packet_independent_of_later_append_and_row_edit(self):
        self.obj.initial=[self.member()];self.obj.Process();packet=self.packet()
        self.obj.valreturn[0]['mode']='foreign';self.obj.valreturn.append({'mode':'foreign'})
        self.assertEqual(len(packet),1);self.assertEqual(packet[0]['mode'],'stop')
    def test_no_completed_member_retains_generic_stop(self):
        self.obj.Process();self.assertEqual(self.packet(),[{'self.log':'','mode':'stop'}])


class Source(unittest.TestCase):
    def test_actual615_and_roundtrip_exact(self):
        original=p.terminal_predecessor(SOURCE.read_text());current=p.patched_source(original)
        self.assertEqual(p.terminal_predecessor(current),original)
        self.assertEqual(p.patched_source(current),current)
        ast.parse(current,feature_version=(3,10))
    def test_all47_original_guards_and_ack_hook_unchanged(self):
        original=p.terminal_predecessor(SOURCE.read_text());current=p.patched_source(original)
        def guards(s):
            return [ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(s)) if isinstance(n,ast.Expr)
                    and isinstance(n.value,ast.Call) and ast.unparse(n.value.func) in
                    ('processing_guard.publication','processing_guard.placement','processing_guard.displacement','processing_guard.cleanup','processing_guard.cleanup_scope')]
        self.assertEqual(sorted(guards(original)),sorted(guards(current)));self.assertEqual(len(guards(current)),47)
        self.assertEqual(current.count(p.IMPORT_HOOK),1)
        self.assertIn('myDB.upsert(updatetable, newVal, ctrlVal)\n'+p.IMPORT_HOOK,current)
    def test_partial_or_moved_terminal_patch_refused(self):
        current=p.patched_source(SOURCE.read_text())
        for altered in (current.replace(p.TERMINAL_CAPTURE,'',1),current.replace(p.TERMINAL_SKIP,'',1),
                        current.replace('original_source == ml[\'ComicLocation\']','True',1),
                        current+p.TERMINAL_MARKER+'\n'):
            with self.assertRaises(ValueError):p.patched_source(altered)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',nargs='?',type=Path)
    options=parser.parse_args()
    if options.source is not None:SOURCE=options.source/'PostProcessor.py' if options.source.is_dir() else options.source
    unittest.main(argv=[sys.argv[0]])
