"""Private durable workflow journal; no native Mylar schema changes."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time

LOCK=threading.RLock()
STAGES={'search','provider','download','processing','conversion','tagging','library','handoff','matching','intake'}


def identifier(value):
    value=str(value or '')
    return value if value.isdecimal() and len(value)<=20 else ''


def label(value,limit=160):
    value=str(value or '')
    if '://' in value or '?' in value:return 'Details withheld'
    return re.sub(r'[\x00-\x1f\x7f]','',value.replace('\\','/').rstrip('/').rsplit('/',1)[-1])[:limit]


class Store:
    def __init__(self,root,clock=time.time):
        self.path=Path(root)/'workflow.sqlite';self.clock=clock
        with self.connection() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, at REAL NOT NULL, issueid TEXT, comicid TEXT,
                name TEXT, stage TEXT, provider TEXT, outcome TEXT, retry_at REAL);
                CREATE INDEX IF NOT EXISTS events_issue ON events(issueid,id);
                CREATE TABLE IF NOT EXISTS records (
                kind TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, updated REAL NOT NULL,
                PRIMARY KEY(kind,key));''')
    @contextmanager
    def connection(self):
        with LOCK:
            fd=os.open(self.path,os.O_CREAT|os.O_RDWR,0o600);os.close(fd)
            os.chmod(self.path,0o600)
            db=sqlite3.connect(str(self.path),timeout=10)
            db.row_factory=sqlite3.Row
            try:
                with db:yield db
            finally:db.close()
    def get(self,kind,key,default=None):
        with self.connection() as db:
            row=db.execute('SELECT value FROM records WHERE kind=? AND key=?',(kind,str(key))).fetchone()
            return json.loads(row[0]) if row else default
    def all(self,kind,limit=1000):
        with self.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM records WHERE kind=? ORDER BY updated DESC LIMIT ?', (kind,limit))]
    def active(self,kind,phases,limit=None):
        # Filter before pagination: terminal history cannot hide an unresolved owner.
        with self.connection() as db:
            rows=[json.loads(r[0]) for r in db.execute('SELECT value FROM records WHERE kind=? ORDER BY updated ASC',(kind,))]
        rows=[r for r in rows if r.get('phase') in phases]
        return rows if limit is None else rows[:limit]
    def set(self,kind,key,value):
        with self.connection() as db:
            db.execute('INSERT INTO records VALUES (?,?,?,?) ON CONFLICT(kind,key) DO UPDATE SET value=excluded.value,updated=excluded.updated', (kind,str(key),json.dumps(value),self.clock()))
            if kind in ('command','handoff','dispatch'):
                terminal={'confirmed','rejected','completed','failed','released','no-result'}
                rows=db.execute('SELECT key,value FROM records WHERE kind=? ORDER BY updated DESC',(kind,)).fetchall()
                keys=[r['key'] for r in rows if json.loads(r['value']).get('phase') in terminal][1000:]
                db.executemany('DELETE FROM records WHERE kind=? AND key=?',[(kind,k) for k in keys])
                if kind=='command':db.executemany("DELETE FROM records WHERE kind='command_scope' AND key=?",[(k,) for k in keys])
    def create(self,kind,key,value):
        with self.connection() as db:
            return bool(db.execute('INSERT OR IGNORE INTO records VALUES (?,?,?,?)',(kind,str(key),json.dumps(value),self.clock())).rowcount)
    def delete(self,kind,key):
        with self.connection() as db:db.execute('DELETE FROM records WHERE kind=? AND key=?',(kind,str(key)))
    def event(self,stage,outcome,issueid='',comicid='',name='',provider='',retry_at=None,key=None):
        if stage not in STAGES:raise ValueError('Invalid activity stage')
        now=self.clock()
        with self.connection() as db:
            if key:
                changed=db.execute('INSERT OR IGNORE INTO records VALUES (?,?,?,?)',('observation',str(key),'{}',now)).rowcount
                if not changed:return
            db.execute('INSERT INTO events(at,issueid,comicid,name,stage,provider,outcome,retry_at) VALUES (?,?,?,?,?,?,?,?)',
                       (now,identifier(issueid),identifier(comicid),label(name),stage,label(provider,80),label(outcome),retry_at))
            db.execute('DELETE FROM events WHERE at<? OR id IN (SELECT id FROM events ORDER BY id DESC LIMIT -1 OFFSET 5000)',(now-30*86400,))
            db.execute("DELETE FROM records WHERE kind='observation' AND updated<?",(now-30*86400,))
    def events(self,issueid='',stage='',before=0):
        clauses=[];args=[]
        if issueid:clauses.append('issueid=?');args.append(identifier(issueid))
        if stage:clauses.append('stage=?');args.append(stage)
        if before:clauses.append('id<?');args.append(int(before))
        query='SELECT * FROM events'+(' WHERE '+' AND '.join(clauses) if clauses else '')+' ORDER BY id DESC LIMIT 100'
        with self.connection() as db:return [dict(r) for r in db.execute(query,args)]
