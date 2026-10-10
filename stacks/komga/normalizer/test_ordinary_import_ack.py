"""Actual files/SQLite; synthetic authority and receipt wrappers explicit."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('ordinary_import_ack',HERE/'ordinary_import_ack.py')
reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)


def signature(info):return [info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink]


def file_hash(path):
    path=Path(path);original=signature(path.lstat());data=path.read_bytes()
    if signature(path.lstat())!=original:raise ValueError('Disposable file changed')
    return original,hashlib.sha256(data).hexdigest()


class Ack(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.state=self.root/'state';self.state.mkdir()
        (self.state/'imports').mkdir();self.writer=self.root/'writer';self.writer.mkdir()
        self.config=self.root/'config';self.config.mkdir()
        for p in (self.config/'workflow.sqlite',self.config/'mylar.db',self.writer/'writer-v1.lock',self.writer/'publication-v1.json'):p.write_bytes(b'disposable source control')
        self.source=self.root/'original.cbz';self.source.write_bytes(b'original')
        self.target=self.root/'library.cbz';self.target.write_bytes(b'original')
        self.owner={'table':'issues','issueid':'12','parentcomicid':'34','releasecomicid':'34'}
        self.match={'issueid':'12','comicid':'34'};self.census={'fixture':True}
        self.stage={'inventory':{'payload':'c'*64,'source_sha256':'d'*64},'authority':{'census':self.census}}
        self.record={'source':str(self.source),'sha256':file_hash(self.source)[1],'phase':'submitted',
            'match':self.match,'stage':str(self.root/'stage.cbz'),'publication':{'source':{'inventory':{'source_signature':file_hash(self.source)[0]}},'stage':self.stage}}
        self.key=hashlib.sha256(os.fsencode(self.source)+self.record['sha256'].encode()).hexdigest()
        self.receipt=self.state/'imports'/(self.key+'.json');self.receipt.write_text(json.dumps(self.record));self.receipt.chmod(0o600)
        self.proof={'token':self.key,'source':self.record['stage'],'owner':self.owner,'payload':'c'*64,'source_sha256':'d'*64,'census':self.census}
        self.attempt={'token':self.key,'proof':self.proof,'owner':self.owner,'destination':str(self.target)}
        self.ack={'owner':self.owner,'destination':{'signature':file_hash(self.target)[0],'sha256':file_hash(self.target)[1]}}
        self.history=self.config/'ordinary-import-v1.sqlite'
        db=sqlite3.connect(self.history);db.execute('CREATE TABLE completions(token TEXT,attempt TEXT,ack TEXT)')
        db.execute('INSERT INTO completions VALUES (?,?,?)',(self.key,json.dumps(self.attempt),json.dumps(self.ack)));db.commit();db.close();self.history.chmod(0o600)
        self.maintenance=types.SimpleNamespace(worker=types.SimpleNamespace(config={'writer_state':str(self.writer),'mylar':{'config_dir':str(self.config)}}),state=self.state)
        evidence=types.SimpleNamespace(file_hash=file_hash,signature=signature)
        authority=types.SimpleNamespace(config=self.config,writer=types.SimpleNamespace(root=self.writer,lock=self.writer/'writer-v1.lock'))
        self.guard=types.SimpleNamespace(evidence=evidence,current=lambda _:authority,
            confirmation_check=lambda *_:{'target':{'authority':{'owner':self.owner}}})
        self.receipt_reader=types.SimpleNamespace(handoff_read=lambda path:(json.loads(path.read_text()),signature(path.lstat())))
        # Receipt-reader shape is synthetic here; full owning import_recovery tests
        # independently exercise its public read function and private file policy.
        self.patcher=patch.dict(sys.modules,{'publication_guard':self.guard,'native_handoff':types.SimpleNamespace(native_path=lambda _,p:str(p)),
            'import_recovery':self.receipt_reader});self.patcher.start();self.addCleanup(self.patcher.stop)
    def confirmed(self):return reader.confirmed(self.maintenance,self.source,self.match,self.target)
    def test_exact_original_receipt_token_and_target_ack(self):self.assertEqual(self.confirmed(),self.key)
    def test_archive_without_ack_and_unknown_phase_held(self):
        self.history.unlink();self.assertIsNone(self.confirmed())
    def test_wrong_original_stage_join_held(self):
        self.record['stage']=str(self.root/'foreign-stage');self.receipt.write_text(json.dumps(self.record))
        self.assertIsNone(self.confirmed())
    def test_same_bytes_target_replacement_held(self):
        data=self.target.read_bytes();self.target.unlink();self.target.write_bytes(data)
        self.assertIsNone(self.confirmed())
    def test_late_history_helper_changes_source_held(self):
        original=file_hash;fired=[]
        def late(path):
            result=original(path)
            if Path(path)==self.history and len(fired)==1:self.source.chmod(0o640);fired.append(True)
            elif Path(path)==self.history:fired.append(True)
            return result
        with patch.object(self.guard.evidence,'file_hash',late):self.assertIsNone(self.confirmed())
        self.assertEqual(len(fired),2)
    def test_last_confirmation_changes_original_control_held(self):
        count=[]
        def late(*_):
            count.append(True)
            if len(count)==2:(self.config/'workflow.sqlite').chmod(0o640)
            return {'target':{'authority':{'owner':self.owner}}}
        with patch.object(self.guard,'confirmation_check',late):self.assertIsNone(self.confirmed())
        self.assertEqual(len(count),2)
    def test_original_receipt_late_changed_held(self):
        original=self.guard.confirmation_check;count=[]
        def late(*args):
            count.append(True)
            if len(count)==2:self.receipt.chmod(0o640)
            return original(*args)
        with patch.object(self.guard,'confirmation_check',late):self.assertIsNone(self.confirmed())
    def test_child_host_geometry_mismatch_is_held_not_relabelled(self):
        ack=dict(self.ack,destination=dict(self.ack['destination'],signature=list(self.ack['destination']['signature'])))
        ack['destination']['signature'][0]+=1
        db=sqlite3.connect(self.history);db.execute('UPDATE completions SET ack=?',(json.dumps(ack),));db.commit();db.close()
        self.assertIsNone(self.confirmed())


if __name__=='__main__':unittest.main()
