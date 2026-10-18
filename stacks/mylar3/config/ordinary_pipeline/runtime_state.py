"""Disposable genesis and factual observations for the installed Mylar pipeline."""
from contextlib import contextmanager
import ast
import base64
import configparser
import hashlib
import importlib
import json
from pathlib import Path
import queue
import secrets
import shutil
import sqlite3
import sys
import tempfile
import zipfile

NATIVE = Path('/app/mylar3/mylar')
SERIES = 'Runtime Fixture Series'
COMIC = '410001'
ISSUE = '410002'
DELIVERY = '410003'
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def signature(path):
    z = Path(path).lstat()
    return (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
            z.st_mode, z.st_uid, z.st_gid, z.st_nlink)


def installed(expected_path, expected_sha):
    raw = Path(expected_path).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected_sha
    expected = json.loads(raw)
    assert type(expected) is dict and len(expected) == 180
    assert {p.name for p in NATIVE.glob('*.py')} == set(expected)
    frames = {}
    for name, checksum in expected.items():
        assert Path(name).name == name and name.endswith('.py')
        path = NATIVE / name
        before = signature(path)
        assert not path.is_symlink() and path.is_file() and before[-1] == 1
        assert digest(path) == checksum and signature(path) == before
        frames[path] = before
    sys.path[:0] = ['/app/mylar3', '/app/mylar3/lib']
    app = importlib.import_module('mylar')
    assert Path(app.__file__) == NATIVE / '__init__.py'
    for name in ('PostProcessor', 'db', 'config', 'native_writers', 'publication_guard',
                 'publication_api', 'ordinary_import_history', 'ordinary_import_continuity',
                 'processing_guard', 'release_naming', 'tagger_supplement', 'tagger_native'):
        module = importlib.import_module('mylar.' + name)
        assert Path(module.__file__) == NATIVE / (name + '.py')
        assert module.__spec__.origin == str(NATIVE / (name + '.py'))
        assert digest(module.__file__) == expected[name + '.py']
    assert 'publication_guard' not in sys.modules and 'media_writer' not in sys.modules
    return app, frames


def close_installed(frames):
    for path, before in frames.items():
        assert signature(path) == before


def schema_statements(source):
    """Use only the owning installed bootstrap's literal table definitions."""
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'dbcheck')
    statements = []
    for node in ast.walk(function):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'execute' and node.args
                and isinstance(node.args[0], ast.Constant)
                and type(node.args[0].value) is str
                and node.args[0].value.upper().startswith('CREATE TABLE')):
            statements.append(node.args[0].value)
    assert len(statements) >= 20 and all('IF NOT EXISTS' in sql.upper() for sql in statements)
    return statements


class State:
    def __init__(self, app):
        self.app = app
        self.temp = tempfile.TemporaryDirectory(prefix='mylar-genuine-pipeline-')
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.data = self.root / 'data'
        self.cache = self.root / 'cache'
        self.library = self.root / 'library'
        self.download = self.root / 'download'
        for path in (self.data, self.cache, self.library, self.download):
            path.mkdir(mode=0o700)
        self.series = self.library / (SERIES + ' (2024)')
        self.series.mkdir()
        self.catalog = self.data / 'mylar.db'
        app.DATA_DIR = str(self.data)
        app.DB_FILE = str(self.catalog)
        app.PROG_DIR = '/app/mylar3'
        app.OS_DETECT = 'Linux'
        app.SYS_ENCODING = 'UTF-8'
        app.APILOCK = False
        app.USE_SABNZBD = 0
        app.USE_NZBGET = 0
        app.PP_QUEUE = queue.Queue()
        app.SEARCH_QUEUE = queue.Queue()
        app.NZB_QUEUE = queue.Queue()
        # Config.read(startup=False) writes provider ordering through the real DB.
        # Match native startup: owning catalog schema precedes provider sequencing.
        with sqlite3.connect(self.catalog) as db:
            for sql in schema_statements((NATIVE / '__init__.py').read_text()):
                db.execute(sql)
            assert db.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
        self.catalog.chmod(0o600)
        ini = self.data / 'config.ini'
        settings = dict(CONFIG_VERSION=19, DESTINATION_DIR=str(self.library),
                        CACHE_DIR=str(self.cache), DDL_LOCATION=str(self.download),
                        LOG_DIR=str(self.data / 'logs'), SECURE_DIR=str(self.data / '.secure'),
                        BACKUP_LOCATION=str(self.data / 'backup'), ENABLE_META=False,
                        ENABLE_PRE_SCRIPTS=False, ENABLE_EXTRA_SCRIPTS=False,
                        RENAME_FILES=False, FILE_OPTS='move', ENFORCE_PERMS=True,
                        CHMOD_FILE='0600', CHMOD_DIR='0700', CHECK_FOLDER=str(self.download),
                        ENABLE_CHECK_FOLDER=False, ANNUALS_ON=True)
        config = configparser.ConfigParser()
        for key, value in settings.items():
            definition = app.config._CONFIG_DEFINITIONS[key]
            section = definition[1]
            if not config.has_section(section):
                config.add_section(section)
            config.set(section, key.lower(), str(value))
        with ini.open('w') as handle:
            config.write(handle)
        ini.chmod(0o600)
        app.CONFIG_FILE = str(ini)
        app.CONFIG = app.config.Config(str(ini))
        assert app.CONFIG.read(startup=False) is app.CONFIG
        assert app.logger.LOG_LANG.startswith('en')
        app.logger.initLogger(console=True, log_dir=app.CONFIG.LOG_DIR,
                              max_logsize=app.CONFIG.MAX_LOGSIZE,
                              max_logfiles=app.CONFIG.MAX_LOGFILES, loglevel=2)
        settings = dict(DESTINATION_DIR=str(self.library), CACHE_DIR=str(self.cache),
                        DDL_LOCATION=str(self.download), ENABLE_META=False, CBR2CBZ_ONLY=False,
                        RENAME_FILES=False, FILE_OPTS='move', CHMOD_FILE='0600', CHGROUP='',
                        ENFORCE_PERMS=True, ENABLE_PRE_SCRIPTS=False, ENABLE_EXTRA_SCRIPTS=False,
                        ENABLE_TORRENTS=False, SNATCHEDTORRENT_NOTIFY=False,
                        CHECK_FOLDER=str(self.download), ENABLE_CHECK_FOLDER=False,
                        STORE_COVER_LOCAL=False, ANNUALS_ON=True)
        for key, value in settings.items():
            setattr(app.CONFIG, key, value)
        self.source = self.download / (SERIES.replace(' ', '.') + '.001.(2024).cbz')
        xml = ('<ComicInfo><Series>' + SERIES + '</Series><Number>1</Number>'
               '<Year>2024</Year><Publisher>Runtime Fixture</Publisher></ComicInfo>')
        with zipfile.ZipFile(self.source, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('001.png', PNG)
            archive.writestr('002.png', PNG)
            archive.writestr('ComicInfo.xml', xml)
            archive.writestr('notes/readme.txt', 'preserved fixture extra')
        self.source.chmod(0o600)
        self.original_sha = digest(self.source)
        self.seed()
        from mylar import workflow_store, media_writer, publication_guard, native_writers
        self.store = workflow_store.Store(self.data)
        self.writer = media_writer.Writer(self.data / 'media-writer', create=True)
        self.registry = publication_guard.RegistryState(self.store.path, self.writer)
        # New fixture genesis, not an assertion about any operational backup.
        saved = self.root / 'genesis-workflow.sqlite'
        shutil.copy2(self.store.path, saved)
        assert digest(saved) == digest(self.store.path)
        evidence = dict(manifest_sha256=digest(self.catalog), restore_sha256=digest(saved),
                        description='New disposable runtime-fixture genesis; no live state')
        token = self.registry.prepare_bootstrap(evidence, epoch=secrets.token_hex(32))
        self.registry.initialize(token, accepted_token=token)
        assert native_writers.initialize_publication()['state'] == 'ready'
        with native_writers.operation(startup=True):
            native_writers.startup_catalog(self.writer)
            native_writers.complete_startup()
        assert native_writers.startup_status()['state'] == 'ready'
        from mylar import ordinary_import_continuity
        ordinary_import_continuity.initialize(self.data)
        self.events = []
        self.queue = queue.Queue()

    def seed(self):
        with sqlite3.connect(self.catalog) as db:
            comic = dict(ComicID=COMIC, ComicName=SERIES, ComicSortName=SERIES,
                         ComicYear='2024', ComicLocation=str(self.series),
                         ComicName_Filesafe=SERIES, DateAdded=self.app.helpers.today(),
                         LastUpdated=self.app.helpers.now(), LatestIssueID=ISSUE,
                         ComicPublisher='Runtime Fixture', ComicPublished='2024 - Present',
                         Status='Active', Have=0, Total=1, ComicVersion='None',
                         AlternateFileName='None', AlternateSearch='None', UseFuzzy='0',
                         DynamicComicName=None, ForceContinuing=0, cv_removed=0,
                         AgeRating='Teen', Type='Comic', AllowPacks='0')
            issue = dict(IssueID=ISSUE, ComicID=COMIC, ComicName=SERIES, Issue_Number='1',
                         IssueDate='2024-01-01', ReleaseDate='2024-01-01',
                         Int_IssueNumber=1000, Status='Wanted', Location=None)
            ddl = dict(ID=DELIVERY, issueid=ISSUE, comicid=COMIC, status='Completed', pack=0,
                       filename=self.source.name, tmp_filename=str(self.source))
            sentinel_comic = dict(comic, ComicID='410010', ComicName='Unrelated Fixture',
                                  ComicSortName='Unrelated Fixture',
                                  ComicName_Filesafe='Unrelated Fixture', LatestIssueID='410011',
                                  ComicLocation=str(self.library / 'Unrelated Fixture'),
                                  DynamicComicName=None)
            sentinel_issue = dict(issue, IssueID='410011', ComicID='410010', ComicName='Unrelated Fixture')
            for table, row in (('comics', comic), ('issues', issue), ('ddl_info', ddl),
                               ('comics', sentinel_comic), ('issues', sentinel_issue)):
                columns = ','.join(row)
                db.execute('INSERT INTO ' + table + '(' + columns + ') VALUES('
                           + ','.join('?' for _ in row) + ')', tuple(row.values()))

        # Native dbcheck's real derived-name upgrade supplies the storage form,
        # including lowercase and delimiter removal used by the discovery query.
        self.app.helpers.upgrade_dynamic()
        # Use the genuine updater's normal series summaries for the actual issues.
        for comic_id in (COMIC, '410010'):
            self.app.updater.latest_update(comic_id, '1', '2024-01-01')
        with sqlite3.connect(self.catalog) as db:
            self.unrelated = (
                tuple(db.execute('SELECT * FROM comics WHERE ComicID=?', ('410010',)).fetchone()),
                tuple(db.execute('SELECT * FROM issues WHERE IssueID=?', ('410011',)).fetchone()),
            )

    def preserved_unrelated(self):
        with sqlite3.connect(self.catalog) as db:
            current = (
                tuple(db.execute('SELECT * FROM comics WHERE ComicID=?', ('410010',)).fetchone()),
                tuple(db.execute('SELECT * FROM issues WHERE IssueID=?', ('410011',)).fetchone()),
            )
        assert current == self.unrelated, 'unrelated comic or issue changed'

    def processor(self, *, discovery):
        from mylar import PostProcessor
        obj = PostProcessor.PostProcessor('Manual Run' if discovery else self.source.stem, str(self.download),
                                         issueid=None if discovery else ISSUE,
                                         comicid=None if discovery else COMIC,
                                         queue=self.queue, ddl=True)
        obj.download_info = dict(provider='DDL', id=DELIVERY)
        return obj

    @contextmanager
    def completion_probe(self, *, lost_reply=False):
        """Inject only after the original SQLite completion transaction commits."""
        from mylar import ordinary_import_history as history
        original = history._database
        fired = False
        @contextmanager
        def observed_database(*, write=False):
            nonlocal fired
            with original(write=write) as db:
                yield db
            if write:
                with sqlite3.connect(self.data / history._NAME) as connection:
                    rows = connection.execute('SELECT ack FROM completions WHERE ack IS NOT NULL').fetchall()
                if rows and not fired:
                    fired = True
                    self.events.append(dict(completion_committed=True,
                                            source_retained=self.source.exists(),
                                            source_sha256=digest(self.source) if self.source.exists() else None))
                    if lost_reply:
                        raise sqlite3.OperationalError('injected reply loss after genuine durable completion')
        history._database = observed_database
        try:
            yield
        finally:
            history._database = original
        assert fired, 'the genuine completion commit was never reached'

    def run(self, *, discovery, lost_reply=False):
        from mylar import processing_guard
        obj = self.processor(discovery=discovery)
        try:
            with self.completion_probe(lost_reply=lost_reply):
                if discovery:
                    obj.Process()
                else:
                    # Explicit already-matched input seam; no placement/ACK substitute.
                    def matched(processor):
                        return processor.Process_next(COMIC, ISSUE, '1')
                    processing_guard.run(matched)(obj)
        except BaseException:
            # Diagnostic output never replaces the original exception or acceptance.
            try:
                with self.queue.mutex:
                    queued = list(self.queue.queue)[:16]
                report = dict(processor_log=obj.log[-65536:],
                              valreturn=obj.valreturn[:16], queue=queued,
                              completion_events=list(self.events))
                print('GENUINE_PIPELINE_REFUSAL=' + json.dumps(report, default=str),
                      file=sys.stderr, flush=True)
            except Exception:
                print('GENUINE_PIPELINE_REFUSAL=diagnostic-unavailable',
                      file=sys.stderr, flush=True)
            raise
        assert self.events == [dict(completion_committed=True, source_retained=True,
                                    source_sha256=self.original_sha)]
        assert not self.queue.empty(), 'owning processing queue has no terminal result'
        rows = []
        while not self.queue.empty():
            rows.extend(self.queue.get_nowait())
        return rows

    def completion(self):
        from mylar import ordinary_import_history as history
        with history._database() as db:
            rows = db.execute('SELECT token,attempt,ack FROM completions').fetchall()
        assert len(rows) == 1 and rows[0][2] is not None
        token, attempt, ack = rows[0]
        return token, json.loads(attempt), json.loads(ack), (attempt, ack)

    def destination(self):
        with sqlite3.connect(self.catalog) as db:
            row = db.execute('SELECT Status,Location FROM issues WHERE IssueID=?', (ISSUE,)).fetchone()
            assert row and row[0] == 'Downloaded' and row[1]
            assert db.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
        path = self.series / row[1]
        assert path.is_file()
        return path
