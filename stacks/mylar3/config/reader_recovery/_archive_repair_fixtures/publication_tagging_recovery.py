"""Explicit completion of witnessed terminal tagging; never replay a media write."""
import json
import os
from pathlib import Path
import re

if __package__:
    from . import publication_guard as guard, publication_native as native
    from .publication_transaction import NAME, _write, state_evidence, history_identity, terminal_digest
    from .tagger_handoff import Published
    from .tagger_staging import Staging
    from .media_writer import sync
else:
    import publication_guard as guard
    import publication_native as native
    from publication_transaction import NAME, _write, state_evidence, history_identity, terminal_digest
    from tagger_handoff import Published
    from tagger_staging import Staging
    from media_writer import sync

PENDING='tagger-recovery-v1.pending'
KEYS={'version','kind','phase','token','writer','source','owner','payload','source_sha256',
      'source_signature','census','policy','observed','recovery','history','fence',
      'publisher','completion','in_place'}


def backup_value(value):
    if (not isinstance(value,dict) or set(value)!={'manifest_sha256','restore_sha256','description'}
            or any(not guard.digest_value(value[key]) for key in ('manifest_sha256','restore_sha256'))
            or not isinstance(value['description'],str) or not 1<=len(value['description'].encode())<=1024):
        raise guard.Unavailable('Reviewed restore evidence is required')
    return value


def job_value(job):
    if (not isinstance(job,dict) or set(job)!=KEYS or type(job['version']) is not int
            or job['version']!=1 or job['kind']!='tagging' or job['phase']!='completing'
            or not isinstance(job['token'],str) or not re.fullmatch('[0-9a-f]{32}',job['token'])
            or not guard.digest_value(job['payload']) or not guard.digest_value(job['source_sha256'])
            or not isinstance(job['policy'],dict) or type(job['policy'].get('manualmeta')) is not bool):
        raise guard.Unavailable('Only a witnessed terminal tagging job can be completed')
    binding=job['publisher'];predecessor={key:value for key,value in job.items() if key not in ('publisher','completion')}
    predecessor['phase']='fenced';predecessor['in_place']=None
    if (not isinstance(binding,dict) or binding.get('token')!=job['token']
            or binding.get('before')!=job['source_sha256']
            or binding.get('intent_sha256')!=guard.canonical_digest(predecessor)
            or not guard.same_json(binding.get('owner'),job['owner'])
            or not guard.same_json(binding.get('payload'),job['payload'])
            or not guard.same_json(binding.get('census'),job['census'])
            or not guard.same_json(binding.get('in_place'),job['in_place'])):
        raise guard.Unavailable('Terminal tagging predecessor changed')
    return job


@guard.state_errors
def snapshot(controller,writer,job):
    """Read current complete authority and files without preparing or replaying them."""
    job_value(job)
    if (not writer.local[1].depth or writer.root.parent!=controller.root
            or writer.fenced() or writer.fenced(release=True)
            or not guard.same_json(guard.writer_identity(writer),job['writer'])
            or not guard.same_json(state_evidence(writer),job['recovery'])
            or not guard.same_json(history_identity(Path(job['history'][0])),job['history'])):
        raise guard.Unavailable('Terminal tagging ownership changed')
    history=writer.root/'tagger-completed-v1'
    if str(history)!=job['history'][0]:raise guard.Unavailable('Terminal history path changed')
    witness=history/(job['token']+'.json')
    if not guard.same_json(guard.private_json(witness),dict(version=1,kind='tagging-terminal-proof',job=job)):
        raise guard.Unavailable('Exact immutable terminal witness required')
    terminal=job['completion'];recovery=job['recovery']['directories'];receipt=Path(recovery[1][0])/(job['token']+'.json')
    if (not isinstance(terminal,dict) or set(terminal)!={'target','sha256','signature','receipt','receipt_evidence','record','stage'}
            or terminal['receipt']!=str(receipt)
            or guard.private_evidence(receipt)!=terminal['receipt_evidence']
            or not guard.same_json(guard.private_json(receipt),terminal['record'])):
        raise guard.Unavailable('Terminal receipt changed')
    record=terminal['record'];target=Path(terminal['target']);source=Path(job['source'])
    if (record.get('state') not in ('committed','unchanged') or record.get('cleaned') is not True
            or record.get('token')!=job['token'] or record.get('source')!=str(target)
            or record.get('before')!=job['source_sha256']
            or not guard.same_json(record.get('correction_guard'),job['publisher'])
            or not guard.same_json(record.get('terminal_proof'),dict(version=1,digest=terminal_digest(terminal)))
            or terminal['sha256']!=record.get('after' if record['state']=='committed' else 'before')):
        raise guard.Unavailable('Terminal receipt is not a completed owned publication')
    if job['policy']['manualmeta']:
        if target!=source or terminal['stage'] is not None:raise guard.Unavailable('Manual terminal path changed')
    else:
        expected=Path(recovery[2][0])/('mylar_modern_'+job['token'])/source.name
        stage_path=Path(recovery[3][0])/(job['token']+'.json');stage=terminal['stage']
        if (target!=expected or not isinstance(stage,dict) or set(stage)!={'path','evidence','record'}
                or stage['path']!=str(stage_path) or guard.private_evidence(stage_path)!=stage['evidence']
                or not guard.same_json(guard.private_json(stage_path),stage['record'])):
            raise guard.Unavailable('Terminal staging evidence changed')
        reader=Staging.__new__(Staging);reader.root=Path(recovery[2][0]);reader.receipts=Path(recovery[3][0])
        row=reader.read(stage_path)
        if (row['state']!='ready' or row.get('after')!=terminal['sha256']
                or row['source']!=str(source) or row['before']!=job['source_sha256']
                or row['folder_identity']!=list(guard.signature(target.parent.lstat())[:2])
                or list(target.parent.iterdir())!=[target]):
            raise guard.Unavailable('Terminal staging ownership changed')
    value=guard.inventory(target,tool_root=controller.tool_root)
    if (value['payload']!=job['payload'] or value['source_sha256']!=terminal['sha256']
            or not guard.same_json(value['source_signature'],terminal['signature'])):
        raise guard.Unavailable('Terminal source changed')
    handoff=Published(record['state'],record.get('metadata',''),str(target),terminal['sha256'],
                      tuple(record['candidate_identity' if record['state']=='committed' else 'source_identity'][:4]),
                      tuple(record['permissions']),tuple(sorted(record.get('attributes',{}).items())))
    if not handoff.valid_for(target):raise guard.Unavailable('Terminal attributes changed')
    if not job['policy']['manualmeta'] or job['in_place'] is None:
        original=guard.inventory(source,tool_root=controller.tool_root)
        if (original['source_sha256']!=job['source_sha256']
                or not guard.same_json(original['source_signature'],job['source_signature'])):
            raise guard.Unavailable('Retained acquisition changed')
    proposed=native.owner(controller.root,None if job['owner'] is None else job['owner']['issueid'])
    if not guard.same_json(proposed,job['owner']):raise guard.Unavailable('Terminal claimed owner changed')
    census,records=guard.registry_snapshot(controller.database,writer.root/'publication-v1.json')
    if not guard.same_json(census,job['census']):raise guard.Unavailable('Terminal correction authority changed')
    matched=[entry for entry in records.values() if entry['inventory']['payload']==job['payload']]
    observed=[]
    if matched:
        allowed={guard.canonical_digest(owner):owner for entry in matched for owner in entry['allowed']}
        rejected={guard.canonical_digest(owner) for entry in matched for owner in entry['rejected']}
        owner_key=guard.canonical_digest(proposed)
        if owner_key not in allowed or owner_key in rejected or len(allowed)>8:
            raise guard.Unavailable('Terminal publication is no longer eligible')
        fresh=controller.observe(writer,dict(allowed=[allowed[key] for key in sorted(allowed)]))
        if fresh['inventory']['payload']!=job['payload']:raise guard.Unavailable('Correct publication changed')
        observed=fresh['observed']
    projected=json.loads(json.dumps(observed))
    for item in projected:
        if item['catalog']['path']!=str(source) or job['in_place'] is None:continue
        old=[entry for entry in job['observed'] if guard.same_json(entry['owner'],item['owner'])
             and guard.same_json(entry['catalog'],item['catalog'])]
        if (len(old)!=1 or item['source_sha256']!=terminal['sha256']
                or not guard.same_json(item['signature'],terminal['signature'])):
            raise guard.Unavailable('Terminal catalog transition changed')
        item['source_sha256']=old[0]['source_sha256'];item['signature']=old[0]['signature']
    if not guard.same_json(projected,job['observed']):raise guard.Unavailable('Terminal correct-owner facts changed')
    return dict(writer=guard.writer_identity(writer),census=census,witness=guard.private_evidence(witness),
                receipt=guard.private_evidence(receipt),target=value,observed=observed)


class Completion:
    """Explicit reviewed completion ledger, with a hold spanning every unlink.

    The ledger never invokes a producer or changes an archive. Missing intent
    or fence is acceptable only after this exact plan was durably accepted.
    """
    def __init__(self,controller,writer):
        self.controller=controller;self.writer=writer
        self.marker=writer.root/PENDING;self.intent=writer.root/NAME
        self.root=writer.root/'tagger-recovery-v1'

    def _locked(self):
        if not self.writer.local[1].depth:raise guard.Unavailable('Raw Writer required')

    def _read(self,token):
        self._locked()
        if not guard.digest_value(token):raise guard.Unavailable('Exact completion token required')
        history_identity(self.root)
        row=guard.private_json(self.root/(token+'.json'))
        if (set(row)!={'version','plan','phase'} or type(row['version']) is not int
                or row['version']!=1 or row['phase'] not in ('prepared','accepted','completed')
                or not isinstance(row['plan'],dict)
                or set(row['plan'])!={'job','intent','snapshot','backup'}
                or guard.canonical_digest(row['plan'])!=token):
            raise guard.Unavailable('Completion ledger changed')
        job_value(row['plan']['job']);backup_value(row['plan']['backup'])
        return row

    def prepare(self,backup):
        self._locked();backup_value(backup)
        if os.path.lexists(self.marker):raise guard.Unavailable('Completion already pending')
        job=guard.private_json(self.intent);fresh=snapshot(self.controller,self.writer,job)
        if (not os.path.lexists(self.writer.tagger_pending)
                or not guard.same_json(list(guard.signature(self.writer.tagger_pending.lstat())),job['fence'])):
            # A normal completion can lose its marker before crashing. Exact
            # immutable history plus a still-present owned intent is sufficient.
            if os.path.lexists(self.writer.tagger_pending):
                raise guard.Unavailable('Terminal tagging fence changed')
        plan=dict(job=job,intent=guard.private_evidence(self.intent),snapshot=fresh,backup=backup)
        token=guard.canonical_digest(plan)
        self.root.mkdir(mode=0o700,exist_ok=True);history_identity(self.root);sync(self.writer.root)
        path=self.root/(token+'.json')
        if os.path.lexists(path):
            row=self._read(token)
            if row['phase']!='prepared':raise guard.Unavailable('Completion already accepted')
        else:_write(path,dict(version=1,plan=plan,phase='prepared'),exclusive=True)
        return token

    def complete(self,token,*,boundary=lambda _:None):
        row=self._read(token);plan=row['plan'];job=plan['job']
        path=self.root/(token+'.json');hold=dict(version=1,token=token)
        fresh=snapshot(self.controller,self.writer,job)
        if not guard.same_json(fresh,plan['snapshot']):raise guard.Unavailable('Completion facts changed')
        if row['phase']=='completed':
            if os.path.lexists(self.intent) or os.path.lexists(self.writer.tagger_pending):
                raise guard.Unavailable('Foreign tagging hold after completion')
            if not os.path.lexists(self.marker):return 'completed'
        if row['phase']=='prepared':
            if (guard.private_evidence(self.intent)!=plan['intent']
                    or not guard.same_json(guard.private_json(self.intent),job)):
                raise guard.Unavailable('Prepared terminal intent changed')
            if os.path.lexists(self.marker):
                if not guard.same_json(guard.private_json(self.marker),hold):
                    raise guard.Unavailable('Foreign completion hold')
            else:_write(self.marker,hold,exclusive=True)
            boundary('hold')
            row['phase']='accepted';_write(path,row,exclusive=False);boundary('accepted')
        if not guard.same_json(guard.private_json(self.marker),hold):
            raise guard.Unavailable('Completion hold changed')
        hold_evidence=guard.private_evidence(self.marker)
        if row['phase']!='completed':
            # Pin each captured inode through unlink; a foreign replacement is
            # never cleared. The separate hold remains if any sync fails.
            for target,evidence,value in (
                    (self.writer.tagger_pending,None,None),(self.intent,plan['intent'],job)):
                if not os.path.lexists(target):continue
                with guard.regular(target) as stream:
                    info=os.fstat(stream.fileno())
                    if guard.signature(target.lstat())!=guard.signature(info):
                        raise guard.Unavailable('Terminal hold inode changed')
                    if target==self.writer.tagger_pending:
                        if not guard.same_json(list(guard.signature(info)),job['fence']):
                            raise guard.Unavailable('Terminal tagging fence changed')
                    elif (guard.private_evidence(target)!=evidence
                            or not guard.same_json(guard.private_json(target),value)):
                        raise guard.Unavailable('Terminal tagging intent changed')
                    if not guard.same_json(snapshot(self.controller,self.writer,job),plan['snapshot']):
                        raise guard.Unavailable('Completion facts changed before clearing')
                    target.unlink();sync(self.writer.root)
                boundary('fence' if target==self.writer.tagger_pending else 'intent')
            row['phase']='completed';_write(path,row,exclusive=False);boundary('completed')
        if (os.path.lexists(self.intent) or os.path.lexists(self.writer.tagger_pending)
                or not guard.same_json(snapshot(self.controller,self.writer,job),plan['snapshot'])):
            raise guard.Unavailable('Completion changed before final release')
        with guard.regular(self.marker) as stream:
            if (guard.private_evidence(self.marker)!=hold_evidence
                    or guard.signature(self.marker.lstat())!=guard.signature(os.fstat(stream.fileno()))
                    or not guard.same_json(guard.private_json(self.marker),hold)):
                raise guard.Unavailable('Completion hold changed before release')
            self.marker.unlink()
            try:sync(self.writer.root)
            except OSError:
                if not os.path.lexists(self.marker):_write(self.marker,hold,exclusive=True)
                raise
        boundary('released')
        return 'completed'
