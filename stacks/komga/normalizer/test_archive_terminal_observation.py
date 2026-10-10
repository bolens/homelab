"""Real pipes/SQLite/files; parent foreign provenance is an explicit host fixture."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import select
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
import archive_terminal_observation as h


class Dialogue(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.archive = self.root / 'Comic.cbz'
        self.archive.write_bytes(b'actual preserved archive fixture')
        self.catalog = self.root / 'mylar.db'; self.authority = self.root / 'workflow.sqlite'
        self.marker = self.root / 'publication-v1.json'; self.marker.write_text('{}')
        with closing(sqlite3.connect(self.catalog)) as db, db:
            db.execute('CREATE TABLE comics(ComicID TEXT,ComicLocation TEXT)')
            db.execute('CREATE TABLE issues(IssueID TEXT,ComicID TEXT,Location TEXT,Status TEXT)')
            db.execute('CREATE TABLE annuals(IssueID TEXT,ComicID TEXT,ReleaseComicID TEXT,Location TEXT,Status TEXT,Deleted INT)')
            db.execute('INSERT INTO comics VALUES(?,?)', ('11', '/native/comics'))
            db.execute('INSERT INTO issues VALUES(?,?,?,?)', ('12', '11', 'Comic.cbz', 'Downloaded'))
        with closing(sqlite3.connect(self.authority)) as db, db: db.execute('CREATE TABLE records(key TEXT,value TEXT)')
        self.owner = dict(table='issues', issueid='12', parentcomicid='11', releasecomicid='11')
        self.roles = dict(archive=str(self.archive), catalog=str(self.catalog), authority=str(self.authority),
                          marker=str(self.marker), catalog_native_target='/native/comics/Comic.cbz')
        self.enable = patch.object(h, 'ENABLED', True); self.enable.start(); self.addCleanup(self.enable.stop)
        self.roots = patch.object(h, 'READ_ROOTS', (str(self.root),)); self.roots.start(); self.addCleanup(self.roots.stop)

    def originals(self):
        files = [self.archive, self.catalog, self.authority, self.marker]
        nodes = {str(p):h.five(p.lstat()) for f in files for p in f.parents}
        return dict(files9=[(str(p),h.nine(p.lstat())) for p in files], nodes5=sorted(nodes.items()),
                    namespaces=[(str(self.root), sorted(os.listdir(self.root)))], claims=[],
                    absent=[str(p)+s for p in (self.catalog,self.authority) for s in ('-journal','-wal','-shm')],
                    hashes=[(str(p),hashlib.sha256(p.read_bytes()).hexdigest()) for p in files])

    def run_dialogue(self, mutate=None, bad=None, release_mutate=None, reviewed=False, birth_mutate=None):
        bootstrap = dict(protocol=h.WIRE2 if reviewed else h.PROTOCOL,type='bootstrap',nonce='a'*64,operation_id='b'*64,
                         owner=self.owner,roles=self.roles,local_originals=self.originals(),
                         source_map={str(Path(h.__file__).absolute()):hashlib.sha256(Path(h.__file__).read_bytes()).hexdigest()})
        source_r,parent_w=os.pipe();parent_r,source_w=os.pipe();errors=[];channels=[]
        argv=[str(Path(h.__file__).absolute()),'--reviewed-original-parent-v1','--nonce','a'*64,'--operation-id','b'*64,'--bind-roots',h.encode([str(self.root)]).decode()]
        launch_argv=patch.object(h.sys,'argv',argv);launch_argv.start()
        def worker():
            try:
                launch=h.reviewed_launch(tuple(argv)) if reviewed else None
                c=h.ParentChannel(source_r,source_w,launch=launch);channels.append(c);h.exchange(c)
            except BaseException as e:errors.append(e)
            finally:os.close(source_w);os.close(source_r)
        t=threading.Thread(target=worker);t.start()
        def send(v):os.write(parent_w,h.encode(v)+b'\n')
        def receive():
            raw=bytearray()
            while not raw.endswith(b'\n'):
                if not select.select([parent_r],[],[],3)[0]:raise AssertionError('parent fixture timed out')
                b=os.read(parent_r,1)
                if not b:return None
                raw.extend(b)
            return bytes(raw[:-1])
        try:
            if reviewed:
                birth_raw=receive()
                if birth_raw is None:return [],errors,channels
                birth=json.loads(birth_raw);self.assertEqual(birth['type'],'receiver-birth')
                self.assertEqual(birth['rights'],h.RIGHTS)
                bootstrap['receiver_birth_sha256']=hashlib.sha256(birth_raw).hexdigest()
                if birth_mutate:birth_mutate(bootstrap,birth,channels[0])
            send(bootstrap);hello_raw=receive()
            if hello_raw is None:return [],errors,channels
            hello=json.loads(hello_raw);foreign={k:[] for k in h.VECTORS}
            ref={'path':'/foreign/original.json','sha256':'c'*64,'signature9':[1,2,3,4,5,33152,1000,1000,1]}
            request=dict(protocol=h.WIRE2 if reviewed else h.PROTOCOL,type='observe',nonce='a'*64,operation_id='b'*64,sequence=1,
                         challenge=hello['challenge'],owner=self.owner,outcome='observed-forward',
                         producer_ref=ref,producer_history_ref=ref,producer_originals=foreign,
                         host_projection=foreign,consumer_projection=json.loads(h.encode(bootstrap['local_originals'])),rights=dict(h.RIGHTS))
            if reviewed:request['receiver_birth_sha256']=bootstrap['receiver_birth_sha256']
            if bad:bad(request)
            if mutate:mutate()
            raw=h.encode(request);send(request);answer=receive()
            if answer is None:return [hello],errors,channels
            result=json.loads(answer)
            release=dict(protocol=h.WIRE2 if reviewed else h.PROTOCOL,type='release',nonce='a'*64,operation_id='b'*64,sequence=2,
                         challenge=hello['challenge'],request_sha256=hashlib.sha256(raw).hexdigest(),
                         result_sha256=hashlib.sha256(answer).hexdigest(),rights=dict(h.RIGHTS))
            if reviewed:release['receiver_birth_sha256']=bootstrap['receiver_birth_sha256']
            if release_mutate:release_mutate(release,channels[0])
            send(release);final=receive()
            return [hello,result,None if final is None else json.loads(final)],errors,channels
        finally:
            os.close(parent_w);os.close(parent_r);t.join(3);launch_argv.stop();self.assertFalse(t.is_alive())

    def test_complete_real_pipe_sql_regular_facts_no_grant(self):
        before={p:p.read_bytes() for p in (self.archive,self.catalog,self.authority,self.marker)}
        messages,errors,c=self.run_dialogue();self.assertFalse(errors);self.assertEqual(len(messages),3)
        self.assertEqual(messages[-1]['type'],'released');self.assertTrue(c[0].used)
        self.assertEqual(messages[1]['local_proof']['catalog_owner']['issueid'],'12')
        self.assertEqual(messages[1]['rights'],h.RIGHTS);self.assertEqual(messages[1]['foreign_unrestated']['producer_originals']['files9'],[])
        self.assertEqual(before,{p:p.read_bytes() for p in before})
        with self.assertRaises(h.Held):h.exchange(c[0])

    def test_real_annual_release_identity(self):
        with closing(sqlite3.connect(self.catalog)) as db, db:
            db.execute('DELETE FROM issues');db.execute('INSERT INTO annuals VALUES(?,?,?,?,?,?)',('12','11','13','Comic.cbz','Archived',0))
        self.owner=dict(table='annuals',issueid='12',parentcomicid='11',releasecomicid='13')
        messages,errors,_=self.run_dialogue();self.assertFalse(errors)
        self.assertEqual(messages[1]['local_proof']['catalog_owner']['releasecomicid'],'13')

    def test_wrong_annual_release_held(self):
        with closing(sqlite3.connect(self.catalog)) as db, db:
            db.execute('DELETE FROM issues');db.execute('INSERT INTO annuals VALUES(?,?,?,?,?,?)',('12','11','14','Comic.cbz','Archived',0))
        self.owner=dict(table='annuals',issueid='12',parentcomicid='11',releasecomicid='13')
        messages,errors,_=self.run_dialogue();self.assertTrue(errors);self.assertEqual(len(messages),1)

    def test_original_mode_change_after_hello_held(self):
        messages,errors,_=self.run_dialogue(mutate=lambda:self.archive.chmod(0o640))
        self.assertEqual(len(messages),1);self.assertTrue(errors)

    def test_source_bytes_same_inode_changed_held(self):
        messages,errors,_=self.run_dialogue(mutate=lambda:self.archive.write_bytes(b'changed same inode'))
        self.assertEqual(len(messages),1);self.assertTrue(errors)

    def test_late_namespace_callback_target_mode_held(self):
        real=os.listdir;armed=[];fired=[]
        def late(p):
            result=real(p)
            if armed and Path(p)==self.root and not fired:self.archive.chmod(0o640);fired.append(True)
            return result
        with patch.object(h.os,'listdir',side_effect=late):
            messages,errors,_=self.run_dialogue(mutate=lambda:armed.append(True))
        self.assertTrue(fired);self.assertEqual(len(messages),1);self.assertTrue(errors)

    def test_wrong_original_pipe_challenge_held(self):
        messages,errors,_=self.run_dialogue(bad=lambda r:r.update(challenge='e'*64))
        self.assertEqual(len(messages),1);self.assertTrue(errors)

    def test_wal_is_not_ignored(self):
        messages,errors,_=self.run_dialogue(mutate=lambda:Path(str(self.catalog)+'-wal').write_bytes(b'live WAL'))
        self.assertEqual(len(messages),1);self.assertTrue(errors)

    def test_rights_and_unknown_geometry_refused(self):
        for mutate in (lambda r:r['rights'].update(cleanup=True),lambda r:r['consumer_projection']['files9'].append(['/unknown/path',[1]*9])):
            messages,errors,_=self.run_dialogue(bad=mutate);self.assertEqual(len(messages),1);self.assertTrue(errors)

    def test_wrong_projected_original_cannot_reseal(self):
        def bad(r):r['consumer_projection']['files9'][0][1][5]^=0o040
        messages,errors,_=self.run_dialogue(bad=bad);self.assertEqual(len(messages),1);self.assertTrue(errors)

    def test_saved_json_is_not_channel(self):
        with self.assertRaises(h.Held):h.exchange({'facts':[]})

    def test_default_off_before_pipe_or_read(self):
        with patch.object(h,'ENABLED',False),patch.object(h.os,'fstat') as f:
            with self.assertRaises(h.Held):h.ParentChannel()
            f.assert_not_called()

    def test_late_release_target_change_no_final_ack(self):
        messages,errors,_=self.run_dialogue(release_mutate=lambda r,c:self.archive.chmod(0o640))
        self.assertEqual(len(messages),3);self.assertIsNone(messages[-1]);self.assertTrue(errors)

    def test_release_digest_cannot_be_substituted(self):
        messages,errors,_=self.run_dialogue(release_mutate=lambda r,c:r.update(result_sha256='e'*64))
        self.assertIsNone(messages[-1]);self.assertTrue(errors)

    def test_original_channel_fields_cannot_be_resealed(self):
        messages,errors,_=self.run_dialogue(release_mutate=lambda r,c:setattr(c,'deadline',c.deadline+100))
        self.assertIsNone(messages[-1]);self.assertTrue(errors)

    def test_one_use_survives_changed_public_used_flag(self):
        messages,errors,c=self.run_dialogue();self.assertFalse(errors);c[0].used=False
        with self.assertRaises(h.Held):h.exchange(c[0])

    def test_bool_sequence_is_not_integer(self):
        messages,errors,_=self.run_dialogue(bad=lambda r:r.update(sequence=True))
        self.assertEqual(len(messages),1);self.assertTrue(errors)

    def test_late_final_digest_callback_archive_change_held(self):
        real=hashlib.sha256;fired=[]
        def late(data=b'',*a,**kw):
            result=real(data,*a,**kw)
            if threading.current_thread() is not threading.main_thread() and b'"type":"observed"' in data and not fired:
                self.archive.chmod(0o640);fired.append(True)
            return result
        with patch.object(h.hashlib,'sha256',side_effect=late):messages,errors,_=self.run_dialogue()
        self.assertTrue(fired);self.assertEqual(len(messages),1);self.assertTrue(errors)

    def test_unrelated_33GiB_raw_fact_does_not_stream(self):
        large=self.root/'unrelated.cbz'
        with large.open('wb') as f:f.truncate(33*1024**3)
        real=self.originals
        def original():
            f=real();f['files9'].append((str(large),h.nine(large.lstat())));return f
        with patch.object(self,'originals',side_effect=original):messages,errors,_=self.run_dialogue()
        self.assertFalse(errors);self.assertEqual(messages[-1]['type'],'released');self.assertEqual(large.stat().st_size,33*1024**3)

    def test_actual_fork_original_channel_refused(self):
        r,w=os.pipe();r2,w2=os.pipe();diagnostic_r,diagnostic_w=os.pipe()
        try:
            c=h.ParentChannel(r,w2);pid=os.fork()
            if pid==0:
                try:
                    try:h.exchange(c)
                    except h.Held:os.write(diagnostic_w,b'Held')
                    else:os.write(diagnostic_w,b'unsafe')
                finally:os._exit(0)
            os.close(diagnostic_w);diagnostic_w=None;os.waitpid(pid,0)
            self.assertEqual(os.read(diagnostic_r,16),b'Held');self.assertFalse(c.used)
        finally:
            for fd in (r,w,r2,w2,diagnostic_r,diagnostic_w):
                if fd is not None:os.close(fd)

    def test_actual_write_fd_replacement_no_final_ack(self):
        def replace_fd(r,c):
            fd=os.open('/dev/null',os.O_WRONLY)
            try:os.dup2(fd,c.write_fd)
            finally:os.close(fd)
        messages,errors,_=self.run_dialogue(release_mutate=replace_fd)
        self.assertIsNone(messages[-1]);self.assertTrue(errors)
        self.assertIsInstance(errors[0],h.Held)

    def test_callback_changes_function_identity_no_final_ack(self):
        original=h.catalog_owner
        def replace(r,c):h.catalog_owner=lambda *args:original(*args)
        try:messages,errors,_=self.run_dialogue(release_mutate=replace)
        finally:h.catalog_owner=original
        self.assertIsNone(messages[-1]);self.assertTrue(errors)
        self.assertIsInstance(errors[0],h.Held)

    def test_callback_changes_root_config_no_final_ack(self):
        original=h.READ_ROOTS
        def replace(r,c):h.READ_ROOTS=original+('/unreviewed',)
        try:messages,errors,_=self.run_dialogue(release_mutate=replace)
        finally:h.READ_ROOTS=original
        self.assertIsNone(messages[-1]);self.assertTrue(errors)
        self.assertIsInstance(errors[0],h.Held)

    def test_actual_installed_entry_mode_change_no_final_ack(self):
        source=Path(h.__file__);original=source.stat().st_mode & 0o777
        try:
            messages,errors,_=self.run_dialogue(release_mutate=lambda r,c:source.chmod(original ^ 0o040))
        finally:source.chmod(original)
        self.assertIsNone(messages[-1]);self.assertTrue(errors)
        self.assertIsInstance(errors[0],h.Held)

    def test_original_pipe_lost_spends_channel_without_receipt(self):
        r,w=os.pipe();r2,w2=os.pipe()
        try:
            c=h.ParentChannel(r,w2);os.close(w);w=None
            with self.assertRaises(h.Held):h.exchange(c)
            self.assertTrue(c.used)
            with self.assertRaises(h.Held):h.exchange(c)
        finally:
            for fd in (r,w,r2,w2):
                if fd is not None:os.close(fd)

    def test_final_claim_callback_archive_change_no_final_ack(self):
        original=self.originals
        def originals():
            frame=original();z=self.marker.lstat()
            frame['claims']=[(str(self.marker),(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,z.st_nlink))]
            return frame
        real=h.os.lstat;armed=[];fired=[]
        def late(p,*a,**kw):
            z=real(p,*a,**kw)
            if armed and not fired and threading.current_thread() is not threading.main_thread() and Path(p)==self.marker:
                self.archive.chmod(0o640);fired.append(True)
            return z
        with patch.object(self,'originals',originals),patch.object(h.os,'lstat',late):
            messages,errors,_=self.run_dialogue(release_mutate=lambda r,c:armed.append(True))
        self.assertTrue(fired);self.assertIsNone(messages[-1]);self.assertIsInstance(errors[0],h.Held)

    def test_final_fd_callback_archive_change_no_final_ack(self):
        real=h.os.fstat;armed=[];fired=[]
        def late(fd):
            z=real(fd)
            if armed and fd==armed[0] and not fired:
                self.archive.chmod(0o640);fired.append(True)
            return z
        with patch.object(h.os,'fstat',late):
            messages,errors,_=self.run_dialogue(release_mutate=lambda r,c:armed.append(c.write_fd))
        self.assertTrue(fired);self.assertIsNone(messages[-1]);self.assertIsInstance(errors[0],h.Held)

    def test_final_absence_callback_wal_change_no_final_ack(self):
        real=h.os.lstat;armed=[];fired=[];watched=str(self.authority)+'-shm'
        def late(p,*a,**kw):
            try:z=real(p,*a,**kw)
            except FileNotFoundError:
                if armed and not fired and str(p)==watched:
                    Path(str(self.catalog)+'-wal').write_bytes(b'late mutable WAL');fired.append(True)
                raise
            return z
        with patch.object(h.os,'lstat',late):
            messages,errors,_=self.run_dialogue(release_mutate=lambda r,c:armed.append(True))
        self.assertTrue(fired);self.assertIsNone(messages[-1]);self.assertIsInstance(errors[0],h.Held)

    def test_final_fd_callback_installed_source_parent_change_held(self):
        real=h.os.fstat;armed=[];fired=[];source=Path(h.__file__).parent;mode=source.stat().st_mode & 0o777
        def late(fd):
            z=real(fd)
            if armed and fd==armed[0] and not fired:
                source.chmod(mode ^ 0o020);fired.append(True)
            return z
        try:
            with patch.object(h.os,'fstat',late):
                messages,errors,_=self.run_dialogue(release_mutate=lambda r,c:armed.append(c.write_fd))
        finally:source.chmod(mode)
        self.assertTrue(fired);self.assertIsNone(messages[-1]);self.assertIsInstance(errors[0],h.Held)

    def test_parser_duplicate_deep_bool_and_nonfinite_refuse(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":'+b'['*25+b'0'+b']'*25+b'}',b'{"a":NaN}'):
            with self.assertRaises(h.Held):h.decode(raw)

class Unit5(unittest.TestCase):
    # Real files/SQLite/pipes; READ_ROOTS and launch argv are explicit host fixtures.
    # This is not an installed image/interpreter/mount proof.
    setUp=Dialogue.setUp
    originals=Dialogue.originals
    run_dialogue=Dialogue.run_dialogue

    def test_reviewed_birth_original_real_pipe_positive(self):
        messages,errors,channels=self.run_dialogue(reviewed=True)
        self.assertFalse(errors);self.assertEqual(messages[-1]['type'],'released')
        self.assertEqual(messages[-1]['protocol'],h.WIRE2)
        self.assertEqual(len(messages[-1]['receiver_birth_sha256']),64)
        self.assertEqual(channels[0].launch.bind_roots,(str(self.root),))

    def test_reviewed_annual_original_real_pipe_positive(self):
        with closing(sqlite3.connect(self.catalog)) as db,db:
            db.execute('DELETE FROM issues');db.execute('INSERT INTO annuals VALUES(?,?,?,?,?,?)',('12','11','13','Comic.cbz','Archived',0))
        self.owner=dict(table='annuals',issueid='12',parentcomicid='11',releasecomicid='13')
        messages,errors,_=self.run_dialogue(reviewed=True)
        self.assertFalse(errors);self.assertEqual(messages[1]['local_proof']['catalog_owner']['releasecomicid'],'13')

    def test_wrong_original_birth_hash_holds(self):
        messages,errors,_=self.run_dialogue(reviewed=True,birth_mutate=lambda boot,b,c:boot.update(receiver_birth_sha256='0'*64))
        self.assertTrue(errors);self.assertFalse(messages)

    def test_birth_cannot_replace_shared_leaf(self):
        def change(boot,b,c):
            old=self.archive;old.rename(self.root/'old.cbz');old.write_bytes(b'actual preserved archive fixture')
        _,errors,_=self.run_dialogue(reviewed=True,birth_mutate=change);self.assertTrue(errors)

    def test_bootstrap_cannot_rebase_receiver_original_parent(self):
        def change(boot,b,c):
            boot['local_originals']['nodes5']=[(p,(v[0],v[1],v[2]^0o020,v[3],v[4]) if p=='/tmp' else v) for p,v in boot['local_originals']['nodes5']]
        _,errors,_=self.run_dialogue(reviewed=True,birth_mutate=change);self.assertTrue(errors)

    def test_launch_registry_replacement_holds(self):
        def change(boot,b,c):h._LAUNCHES[c.launch]=tuple(list(h._LAUNCHES[c.launch]))
        _,errors,_=self.run_dialogue(reviewed=True,birth_mutate=change);self.assertTrue(errors)

    def test_live_launch_nonce_mutation_holds(self):
        def change(boot,b,c):c.launch.nonce='0'*64
        _,errors,_=self.run_dialogue(reviewed=True,birth_mutate=change);self.assertTrue(errors)

    def test_observe_original_birth_replay_holds(self):
        _,errors,_=self.run_dialogue(reviewed=True,bad=lambda q:q.update(receiver_birth_sha256='0'*64));self.assertTrue(errors)

    def test_release_original_birth_replay_holds(self):
        _,errors,_=self.run_dialogue(reviewed=True,release_mutate=lambda q,c:q.update(receiver_birth_sha256='0'*64));self.assertTrue(errors)

    def test_default_disabled_preserved(self):
        with patch.object(h,'ENABLED',False):
            with self.assertRaises(h.Held):h.ParentChannel()
        with self.assertRaises(h.Held):h.reviewed_launch((h.__file__,'--anything'))

    def test_launch_extra_or_unmapped_root_holds(self):
        argv=(h.__file__,'--reviewed-original-parent-v1','--nonce','a'*64,'--operation-id','b'*64,'--bind-roots','["/outside"]')
        with self.assertRaises(h.Held):h.reviewed_launch(argv)
        with self.assertRaises(h.Held):h.reviewed_launch(argv+('extra',))


class FinalUnit5(unittest.TestCase):
    setUp=Dialogue.setUp
    originals=Dialogue.originals
    run_dialogue=Dialogue.run_dialogue
    def test_actual_original_interpreter_argv_mutation_holds(self):
        original=list(h.sys.orig_argv)
        def mutate(boot,b,c):h.sys.orig_argv=[*original,'foreign']
        try:
            _,errors,_=self.run_dialogue(reviewed=True,birth_mutate=mutate);self.assertTrue(errors)
        finally:h.sys.orig_argv=original
    def test_sender_last_select_callback_cannot_release_changed_archive(self):
        real=h.select.select;fired=[]
        def callback(r,w,e,t):
            ready=real(r,w,e,t)
            if w and not fired:fired.append(True);self.archive.chmod(0o640)
            return ready
        with patch.object(h.select,'select',callback):_,errors,_=self.run_dialogue(reviewed=True)
        self.assertTrue(fired);self.assertTrue(errors)

if __name__=='__main__':unittest.main()
