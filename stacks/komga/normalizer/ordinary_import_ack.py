"""Passive exact coordinated import acknowledgement; no API calls or grants."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat


def confirmed(maintenance,source,match,target,*,cleanup=False,_copied=False):
    """Return original attempt token only for a current exact native delivery."""
    try:
        if maintenance.worker.config.get('writer_state') is None:return None
        import ordinary_import_observation as observation
        outer=observation.originals(maintenance,source,target)
        continuity_frame=None
        from publication_guard import confirmation_check, evidence, current
        from native_handoff import native_path
        from import_recovery import handoff_read
        source=Path(source);target=Path(target)
        records=[]
        directory=maintenance.state/'imports'
        receipts=list(directory.glob('*.json'))
        if len(receipts)>4096:return None
        for receipt in sorted(receipts):
            record,receipt_signature=handoff_read(receipt)
            if record.get('source')!=str(source) or record.get('match')!=match:continue
            key=hashlib.sha256(os.fsencode(source)+record['sha256'].encode()+(record.get('workflow_command') or '').encode()).hexdigest()
            if receipt.name!=key+'.json' or record.get('phase') not in ('submitted','dispatching'):continue
            records.append((key,record,receipt,receipt_signature))
        if len(records)!=1:return None
        key,record,receipt,receipt_signature=records[0]
        authority=current(maintenance.worker)
        retained=[];retained_nodes=[];absences=[]
        for control in (authority.config/'mylar.db',authority.config/'workflow.sqlite',
                        authority.writer.root/'publication-v1.json',authority.writer.lock):
            if control==authority.writer.root/'publication-v1.json' and not os.path.lexists(control):
                absences.append(control)
                for parent in control.parents:
                    info=parent.lstat()
                    if info.st_mode&0o170000!=0o040000:return None
                    retained_nodes.append((parent,(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)))
                continue
            signature,checksum=evidence.file_hash(control)
            retained.append((control,signature,checksum))
        for control in (authority.config/'mylar.db',authority.config/'ordinary-import-v1.sqlite'):
            for suffix in ('-journal','-wal','-shm'):
                sidecar=Path(str(control)+suffix)
                if os.path.lexists(sidecar):return None
                absences.append(sidecar)
        source_absent=not os.path.lexists(source)
        if source_absent:absences.append(source)
        if not source_absent:
            original_signature,original_hash=evidence.file_hash(source)
            if (original_signature!=record['publication']['source']['inventory']['source_signature']
                    or original_hash!=record['sha256']):return None
            retained.append((source,original_signature,original_hash))
        original_target_signature,original_target_hash=evidence.file_hash(target)
        retained.append((target,original_target_signature,original_target_hash))
        for control,_,_ in retained:
            for parent in control.parents:
                info=parent.lstat()
                if info.st_mode&0o170000!=0o040000:return None
                retained_nodes.append((parent,(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)))
        checked=confirmation_check(maintenance.worker,source if not source_absent else target,target,match)
        owner=checked['target']['authority']['owner']
        database=Path(maintenance.worker.config['mylar'].get('config_dir','/mylar'))/'ordinary-import-v1.sqlite'
        stamp,digest=evidence.file_hash(database)
        if stat.S_IMODE(stamp[5])!=0o600 or stamp[8]!=1:return None
        parents=[]
        for parent in database.parents:
            info=parent.lstat()
            if info.st_mode&0o170000!=0o040000:return None
            parents.append((parent,(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)))
        if any(os.path.lexists(str(database)+s) for s in ('-journal','-wal','-shm')):return None
        with closing(sqlite3.connect(database.absolute().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
            if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:return None
            rows=db.execute('SELECT attempt,ack FROM completions WHERE token=?',(key,)).fetchall()
        if len(rows)!=1 or rows[0][1] is None:return None
        attempt=json.loads(rows[0][0]);ack=json.loads(rows[0][1])
        stage=record['publication']['stage']
        proof=attempt['proof']
        if (attempt['token']!=key or attempt['owner']!=owner or ack['owner']!=owner
                or proof['token']!=key or proof['owner']!=owner
                or proof['source']!=native_path(maintenance,Path(record['stage']))
                or proof['payload']!=stage['inventory']['payload']
                or proof['source_sha256']!=stage['inventory']['source_sha256']
                or proof['census']!=stage['authority']['census']):return None
        target_stamp,target_hash=evidence.file_hash(target)
        if (attempt['destination']!=native_path(maintenance,target) or target_stamp!=ack['destination']['signature'] or target_hash!=ack['destination']['sha256']):
            if cleanup:return None  # Factual continuity never clears retained source.
            if observation.ENABLED and outer is None:
                observation.defer(maintenance,source,match,target)
                return None
            request=dict(version=1,nonce='',token=key,owner=owner,destination=native_path(maintenance,target),
                attempt_sha256=hashlib.sha256(rows[0][0].encode()).hexdigest(),ack_sha256=hashlib.sha256(rows[0][1].encode()).hexdigest(),
                target=dict(signature=target_stamp,sha256=target_hash),payload=proof['payload'],census=authority.admission()[0])
            token,continuity_frame=observation.request_or_consume(maintenance,request,outer,source,target,match)
            if token!=key:return None
        if checked!=confirmation_check(maintenance.worker,source if source.exists() else target,target,match):return None
        if evidence.file_hash(database)!=(stamp,digest):return None
        for path,signature,checksum in retained:
            if evidence.file_hash(path)!=(signature,checksum):return None
        if source_absent and os.path.lexists(source):return None
        if any(os.path.lexists(path) for path in absences):return None
        for path,expected in parents+retained_nodes:
            info=os.lstat(path)
            if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=expected:return None
        for path,expected in ((database,stamp),(target,target_stamp),(receipt,receipt_signature),*((path,signature) for path,signature,_ in retained)):
            info=os.lstat(path)
            if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=tuple(expected):return None
        for path in absences:
            try:os.lstat(path)
            except FileNotFoundError:pass
            else:return None
        copied=None
        if _copied:
            if continuity_frame is None or outer is None:return None
            copied=json.loads(json.dumps(observation._merge(outer,continuity_frame)))
        for frame in (outer,continuity_frame):
            if frame is None:continue
            for row in frame['namespaces']:
                if sorted(os.listdir(row['path']))!=row['names']:return None
            for path,expected in frame['nodes']:
                info=os.lstat(path)
                if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=tuple(expected):return None
            for row in frame['files']:
                info=os.lstat(row['path'])
                if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=tuple(row['signature']):return None
            for path,expected in frame['claims']:
                try:info=os.lstat(path)
                except FileNotFoundError:
                    if expected is not None:return None
                    continue
                actual=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode&0o170000==0o040000 else info.st_nlink)
                if expected is None or actual!=tuple(expected):return None
            for path in frame['absent']:
                try:os.lstat(path)
                except FileNotFoundError:continue
                return None
        return (key,copied) if _copied else key
    except Exception:return None  # Unavailable evidence retains the delivery.
