"""Finite disposable fixture rows; existing installed DB and raw Writer only.

No schema creation, daemon startup impersonation, provider import, ACK or Parent
capability is produced. The caller binds the actual container/process/config.
"""
from contextlib import contextmanager
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import stat
import sys

LIMIT=8*1024**2
COMICS=('710001','710011')
ISSUES=('710002','710012')
SERIES=('Bootstrap Target','Bootstrap Unrelated')


def need(value, reason):
    if not value:raise ValueError(reason)


def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def nine(z):return [z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink]
def read(path, pin, expected=None):
    path=Path(path);need(path.is_absolute() and '..' not in path.parts,'fixed-source-path')
    nodes={}
    for parent in path.parents:
        z=os.lstat(parent);need(stat.S_ISDIR(z.st_mode),'source-parent');nodes[parent]=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=nine(os.fstat(fd));need(stat.S_ISREG(before[5]) and before[8]==1 and before[2]<=LIMIT and before==nine(os.lstat(path)) and (expected is None or before==expected),'source-original')
        raw=b''
        while len(raw)<before[2]:
            block=os.read(fd,min(65536,before[2]-len(raw)));need(bool(block),'source-short');raw+=block
        need(hashlib.sha256(raw).hexdigest()==pin and before==nine(os.fstat(fd))==nine(os.lstat(path)),'source-pin-close')
    finally:os.close(fd)
    for parent,expected5 in nodes.items():
        z=os.lstat(parent);need((z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)==expected5,'source-parent-close')
    return raw,before


def schema(db):
    return [list(r) for r in db.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]


def snapshot(db):
    names=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    need(10<=len(names)<=100 and all(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',n) for n in names),'full-native-schema')
    result={};count=0
    for name in names:
        rows=[list(r) for r in db.execute('SELECT * FROM "'+name+'"')];count+=len(rows)
        need(count<=10000,'finite-native-census');result[name]=sorted(rows,key=lambda r:encode(r))
    need(len(encode(result))<=LIMIT,'finite-native-bytes');return result


def rows(library):
    comics=[];issues=[]
    for comic,issue,title in zip(COMICS,ISSUES,SERIES):
        comics.append(dict(ComicID=comic,ComicName=title,ComicSortName=title,ComicYear='2024',ComicLocation=str(Path(library)/title),ComicName_Filesafe=title,DateAdded='2024-01-01',LastUpdated='2024-01-01 00:00:00',LatestIssueID=issue,LatestDate='2024-01-01',LatestIssue='2',intLatestIssue=2000,ComicPublisher='Runtime Fixture',ComicPublished='2024 - Present',Status='Active',Have=0,Total=1,ComicVersion='None',AlternateFileName='None',AlternateSearch='None',UseFuzzy='0',DynamicComicName=title.lower().replace(' ',''),ForceContinuing=0,cv_removed=0,AgeRating='Teen',Type='Comic',AllowPacks='0'))
        issues.append(dict(IssueID=issue,ComicID=comic,ComicName=title,Issue_Number='2',IssueDate='2024-01-01',ReleaseDate='2024-01-01',Int_IssueNumber=2000,Status='Wanted',Location=None))
    return dict(comics=comics,issues=issues)


def check_data_root(original):
    root, nodes = original
    need(type(root) is str and nodes and nodes[0][0] == root, 'native-data-root-original')
    for value, fd, frame in nodes:
        held = os.fstat(fd); current = os.lstat(value)
        need([held.st_dev,held.st_ino,held.st_mode,held.st_uid,held.st_gid] == frame
             == [current.st_dev,current.st_ino,current.st_mode,current.st_uid,current.st_gid],
             'native-data-root-changed')
    need(stat.S_ISDIR(nodes[0][2][2]) and stat.S_IMODE(nodes[0][2][2]) == 0o700
         and nodes[0][2][3:] == [1000,1000], 'native-data-root-private')


@contextmanager
def private_data_root(root, original=None):
    """Retain the actual private DATA directory; never chmod or adopt drift."""
    root = Path(root); owned = original is None; nodes = []; primary = None
    try:
        if owned:
            need(root.is_absolute() and root.resolve(strict=True) == root, 'native-data-root-canonical')
            for path in (root, *root.parents):
                z = os.lstat(path); need(stat.S_ISDIR(z.st_mode), 'native-data-root-directory')
                frame = [z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid]
                fd = os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
                nodes.append((str(path),fd,frame))
            original = (str(root),tuple(nodes))
        need(type(original) is tuple and len(original) == 2 and original[0] == str(root), 'native-data-root-original')
        check_data_root(original)
        yield original
    except BaseException as error:
        primary = error; raise
    finally:
        try:
            if original is not None:check_data_root(original)
        except BaseException as error:
            if primary is None:raise
            primary.native_data_root_closure_failure = type(error).__name__
        finally:
            if owned:
                for _,fd,_ in nodes:os.close(fd)


@contextmanager
def existing_connection(factory,writer,root,guard,*,original_root=None):
    """Never let the installed constructor create/recover an absent catalog."""
    # Preserve the original absent-database refusal before any constructor.
    os.lstat(Path(root)/'mylar.db')
    with private_data_root(root,original_root) as original_root:
        database=Path(root)/'mylar.db'
        with writer.hold(timeout=30):
            before=nine(os.lstat(database))
            need(stat.S_ISREG(before[5]) and before[6:]==[os.geteuid(),os.getegid(),1] and stat.S_IMODE(before[5]) in (0o600,0o644) and 4096<=before[2]<=256*1024**2,'native-existing-database')
            need(not any(os.path.lexists(str(database)+suffix) for suffix in ('-wal','-shm','-journal')),'native-existing-companion')
            fd=os.open(database,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            try:
                need(nine(os.fstat(fd))==before==nine(os.lstat(database)),'native-existing-open')
                header=os.read(fd,100);need(header[:16]==b'SQLite format 3\0' and header[18:20]==b'\x01\x01','native-existing-rollback-header')
                census,_=guard.media_snapshot(Path(root)/'workflow.sqlite',writer.root/'publication-v1.json')
                check_data_root(original_root)
                connection=factory()
                try:
                    need(nine(os.fstat(fd))==before==nine(os.lstat(database)),'native-constructor-changed-original')
                    need(guard.media_snapshot(Path(root)/'workflow.sqlite',writer.root/'publication-v1.json')[0]==census,'native-constructor-authority-changed')
                    check_data_root(original_root)
                    yield connection
                    check_data_root(original_root)
                finally:connection.connection.close()
                now=nine(os.fstat(fd));need(now[:2]==before[:2] and now[5:]==before[5:] and now==nine(os.lstat(database)),'native-existing-final-node')
                need(not any(os.path.lexists(str(database)+suffix) for suffix in ('-wal','-shm','-journal')),'native-existing-final-companion')
            finally:os.close(fd)


def transaction(connection, writer, guard, root, library, expected_schema, *, seed, original_root=None):
    """A real installed connection/Writer is supplied only by installed()."""
    with private_data_root(root,original_root) as original_root:
        database=Path(root)/'mylar.db';before=nine(os.lstat(database))
        need(stat.S_ISREG(before[5]) and before[6:]==[os.geteuid(),os.getegid(),1] and stat.S_IMODE(before[5]) in (0o600,0o644),'native-db-original')
        sidecars=[Path(str(database)+s) for s in ('-wal','-shm','-journal')]
        need(not any(os.path.lexists(p) for p in sidecars),'native-db-companion')
        with writer.hold(timeout=30):
            census,_=guard.media_snapshot(Path(root)/'workflow.sqlite',writer.root/'publication-v1.json')
            connection.execute('PRAGMA trusted_schema=OFF');connection.execute('PRAGMA busy_timeout=5000')
            need(connection.execute('PRAGMA journal_mode').fetchone()[0]=='delete','native-delete-journal')
            check_data_root(original_root)
            connection.execute('BEGIN IMMEDIATE' if seed else 'BEGIN')
            try:
                need([tuple(r) for r in connection.execute('PRAGMA quick_check').fetchall()]==[('ok',)],'native-db-integrity')
                need(schema(connection)==expected_schema,'native-original-schema')
                old=snapshot(connection)
                need(seed or len(old['comics'])==len(old['issues'])==2 and old['annuals']==[] and old['ddl_info']==[],'finite-existing-fixture')
                need({'comics','issues','annuals','ddl_info','snatched'}<=set(old),'native-owner-tables')
                if seed:
                    need(all(old[n]==[] for n in ('comics','issues','annuals','ddl_info')),'native-seed-empty-only')
                    for table,values in rows(library).items():
                        actual={r[1] for r in connection.execute('PRAGMA table_info('+table+')')}
                        for value in values:
                            need(set(value)<=actual,'native-seed-field-schema')
                            connection.execute('INSERT INTO '+table+'('+','.join(value)+') VALUES('+','.join('?' for _ in value)+')',tuple(value.values()))
                    after=snapshot(connection)
                    need(all(after[n]==old[n] for n in old if n not in ('comics','issues')),'unrelated-tables-changed')
                    need(len(after['comics'])==len(after['issues'])==2,'finite-seed-counts')
                need(guard.media_snapshot(Path(root)/'workflow.sqlite',writer.root/'publication-v1.json')[0]==census,'original-authority-census')
                result=[]
                for comic,issue,title in zip(COMICS,ISSUES,SERIES):
                    cs=connection.execute('SELECT ComicLocation FROM comics WHERE ComicID=?',(comic,)).fetchall()
                    rs=connection.execute('SELECT ComicID,Status,Location FROM issues WHERE IssueID=?',(issue,)).fetchall()
                    need(len(cs)==len(rs)==1 and cs[0][0]==str(Path(library)/title) and rs[0][0]==comic,'exact-native-owner')
                    need(connection.execute('SELECT count(*) FROM annuals WHERE IssueID=?',(issue,)).fetchone()[0]==0,'no-shadowed-annual')
                    result.append(dict(comicid=comic,issueid=issue,series=title,folder=cs[0][0],status=rs[0][1],location=rs[0][2],comic_row=list(connection.execute('SELECT * FROM comics WHERE ComicID=?',(comic,)).fetchone()),issue_row=list(connection.execute('SELECT * FROM issues WHERE IssueID=?',(issue,)).fetchone())))
                check_data_root(original_root)
                current=nine(os.lstat(database))
                need(current[:2]==before[:2] and current[5:]==before[5:], 'native-db-before-commit')
                connection.commit()
            except BaseException:
                connection.rollback();raise
            need(guard.media_snapshot(Path(root)/'workflow.sqlite',writer.root/'publication-v1.json')[0]==census,'final-authority-census')
        after=nine(os.lstat(database));need(after[:2]==before[:2] and after[5:]==before[5:] and not any(os.path.lexists(p) for p in sidecars),'native-db-final-identity')
        return dict(rows=result,catalog_signature9=after,schema_sha256=hashlib.sha256(encode(expected_schema)).hexdigest(),raw_writer_verified=True,daemon_operation_identity=False,ordinary_ack_verified=False,installed_factories_verified=False,publication_acceptance=False)


def installed(value):
    need(type(value)is dict and set(value)=={'version','kind','nonce','cid','action','root','library','config','schema','sdk'},'seed-request-schema')
    need(value['version']==1 and value['kind']=='disposable-native-catalog-fixture' and value['action'] in ('seed','observe') and all(type(value[k])is str and re.fullmatch('[a-f0-9]{64}',value[k]) for k in ('nonce','cid')),'seed-request-kind')
    root=Path(value['root']);library=Path(value['library'])
    need(root.is_absolute() and root.parts[1:2]==('config',) and '..' not in root.parts and library.is_absolute() and '..' not in library.parts and 'archive-publication-'+value['nonce'] in library.parts,'disposable-native-paths')
    with private_data_root(root) as original_root:
        config=value['config'];need(type(config)is dict and set(config)=={'path','sha256','signature9'} and config['path']==str(root/'config.ini'),'native-config-ref')
        raw,config9=read(config['path'],config['sha256'],config['signature9'])
        sdk=value['sdk'];need(type(sdk)is dict and {'__init__.py','db.py','media_writer.py','publication_guard.py'}<=set(sdk) and len(sdk)<=512,'native-sdk-fields')
        need({p.name for p in Path('/app/mylar3/mylar').glob('*.py')}==set(sdk),'complete-native-flat-source-map')
        frames={}
        for name,pin in sdk.items():
            need(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*[.]py',name) and re.fullmatch('[a-f0-9]{64}',pin),'native-sdk-row')
            _,frames[name]=read('/app/mylar3/mylar/'+name,pin)
        sys.path[:0]=['/app/mylar3','/app/mylar3/lib']
        app=importlib.import_module('mylar');need(Path(app.__file__)==Path('/app/mylar3/mylar/__init__.py'),'installed-native-app')
        # DBConnection resolves only DATA_DIR; do not initialize Config, schedulers,
        # native_writers startup flags or a new authority/Writer registry here.
        app.DATA_DIR=str(root)
        modules={n:importlib.import_module('mylar.'+n) for n in ('db','media_writer','publication_guard')}
        for name,module in modules.items():need(Path(module.__file__)==Path('/app/mylar3/mylar')/(name+'.py'),'installed-native-module')
        writer=modules['media_writer'].Writer(root/'media-writer',create=False)
        with existing_connection(modules['db'].DBConnection,writer,root,modules['publication_guard'],original_root=original_root) as connection:
            result=transaction(connection.connection,writer,modules['publication_guard'],root,library,value['schema'],seed=value['action']=='seed',original_root=original_root)
        read(config['path'],config['sha256'],config9)
        for name,pin in sdk.items():read('/app/mylar3/mylar/'+name,pin,frames[name])
        return result


def failure_diagnostic(error):
    """Fixed types and genuine helper code locations; never values or paths."""
    classes=(AssertionError,ValueError,TypeError,KeyError,RuntimeError,OSError,
             TimeoutError,PermissionError,FileNotFoundError,UnicodeError,json.JSONDecodeError)
    token=next((kind.__name__ for kind in classes if type(error) is kind),'unclassified-exception')
    answer=dict(exception_class=token,source_frame=None)
    try:
        trace=error.__traceback__;count=0;selected=None
        while trace is not None and count<64:
            frame=trace.tb_frame;code=frame.f_code
            if (frame.f_globals is globals() and any(code is trusted for trusted in _DIAGNOSTIC_CODES)
                    and code.co_name!='need' and re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,79}',code.co_name)
                    and trace.tb_lineno in {line for _,_,line in code.co_lines() if line is not None}):
                selected=dict(function=code.co_name,line=trace.tb_lineno)
            trace=trace.tb_next;count+=1
        if trace is None:answer['source_frame']=selected
    except BaseException:
        pass
    return answer


def main():
    try:
        need(sys.flags.isolated and sys.dont_write_bytecode and os.geteuid()==1000 and len(sys.argv)==4 and sys.argv[1]=='--disposable-native-catalog-v1','original-seed-invocation')
        raw=sys.stdin.buffer.read(LIMIT+1);need(0<len(raw)<=LIMIT,'request-limit');value=json.loads(raw)
        need(sys.argv[2:]==[value['nonce'],value['cid']],'original-seed-invocation-binding')
        result=installed(value);sys.stdout.buffer.write(encode(result)+b'\n');return 0
    except Exception as error:
        try:
            sys.stderr.buffer.write(encode(dict(kind='disposable-native-catalog-failure',**failure_diagnostic(error)))+b'\n')
        except BaseException:
            pass  # Losing safe diagnostics never changes the original held result.
        sys.stdout.buffer.write(b'{"held":"disposable-native-catalog"}\n');return 2


_DIAGNOSTIC_CODES=tuple(function.__code__ for function in
    (need,encode,nine,read,schema,snapshot,rows,check_data_root,private_data_root.__wrapped__,existing_connection.__wrapped__,transaction,installed,main))



if __name__=='__main__':raise SystemExit(main())
