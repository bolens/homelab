"""Opt-in disposable native seed and real queued processing, before reader scan.

Host tests can double transport. Only actual runtime can establish catalog/file
completion. No ordinary ACK, NFS, Parent/Birth or factory grant is returned.
"""
import copy
import configparser
import hashlib
import os
from pathlib import Path
import stat
import time
import zipfile

import genuine_application_bootstrap as bootstrap
import genuine_archive_fixture as fixture
import genuine_native_catalog_helper as helper

p=bootstrap.p
need=p.need
HERE=Path(__file__).parent


class Catalog:
    def __init__(self, session, helper_ref, native):
        need(type(session) is bootstrap.Bootstrap,'original-bootstrap-required')
        self.s=session;self.native=copy.deepcopy(native);self.helper_ref=copy.deepcopy(helper_ref)
        need(Path(helper_ref['path'])==HERE/'genuine_native_catalog_helper.py','fixed-native-helper')
        self.program=p.read(helper_ref,private=False).decode()
        need({'__init__.py','db.py','media_writer.py','publication_guard.py'}<=set(session.sdk),'installed-seed-sdk-required')
        self.original=None;self.config=None;self.seed=None;self.inputs=[];self.records=[]
        self.library=session.library;self.source=session.data/('bootstrap-native-'+session.plan['nonce'])
        self.output=session.output/'native-catalog-processing.json'
        need(not os.path.lexists(self.source) and not os.path.lexists(self.output) and not os.listdir(self.library),'native-fixture-no-replay')

    def original_process(self, *, ready):
        s=self.s;s.roles();s.installed_sources()
        request=dict(version=1,nonce=s.plan['nonce'],source_sha256=s.plan['native_probe']['sha256'],seconds=s.seconds(),module_pins={'/app/mylar3/mylar/'+name:s.sdk[name] for name in ('worker_health.py','native_writers.py')},scope_source=s.scope_source)
        value=p.decode(s.engine.run(['exec','--interactive','--user','1000:1000',s.plan['roles']['native']['id'],'/lsiopy/bin/python3','-I','-B','-c',s.probe_program],s.seconds(),p.encode(request)))
        container_path='/config/'+str(s.data.relative_to(s.native_mount)/'config.ini')
        need(value.get('version')==1 and value.get('nonce')==s.plan['nonce'] and value.get('source_sha256')==s.plan['native_probe']['sha256'] and value.get('config',{}).get('path')==container_path and type(value.get('process'))is dict,'native-seed-original-probe')
        current=dict(process=value['process'],config=value['config'])
        if self.original is None:
            self.original=copy.deepcopy(current);self.config=dict(value['config'],path=str(s.data/'config.ini'));p.read(self.config,private=False)
        need(current==self.original,'native-seed-process-config-changed')
        if ready:need(value.get('publication',{}).get('state')=='ready','native-seed-not-ready')
        raw=p.read(self.config,private=False)
        cfg=configparser.ConfigParser(interpolation=None,strict=True);cfg.read_string(raw.decode());need(not cfg.defaults(),'native-seed-config-defaults')
        def one(key):
            values=[cfg.get(section,key,raw=True)for section in cfg.sections()if cfg.has_option(section,key)]
            need(len(values)==1,'native-seed-config-unique');return values[0]
        need(one('destination_dir')==str(self.library) and one('file_opts')=='move' and one('chmod_file')=='0600','native-seed-file-policy')
        for key in ('enable_meta','rename_files','enable_pre_scripts','enable_extra_scripts'):
            need(one(key).lower() in ('0','false'),'native-seed-offline-policy')
        need(one('post_processing').lower()in ('1','true'),'native-seed-queue-policy')
        s.roles();return value

    def request(self, action):
        s=self.s;self.original_process(ready=action=='seed')
        root='/config/'+str(s.data.relative_to(s.native_mount))
        value=dict(version=1,kind='disposable-native-catalog-fixture',nonce=s.plan['nonce'],cid=s.plan['roles']['native']['id'],action=action,root=str(Path(root)),library=str(s.library),config=self.original['config'],schema=self.native['schema'],sdk=s.sdk)
        raw=s.engine.run(['exec','--interactive','--user','1000:1000',s.plan['roles']['native']['id'],'/lsiopy/bin/python3','-I','-B','-c',self.program,'--disposable-native-catalog-v1',s.plan['nonce'],s.plan['roles']['native']['id']],s.seconds(),p.encode(value))
        result=p.decode(raw)
        need(type(result)is dict and set(result)=={'rows','catalog_signature9','schema_sha256','raw_writer_verified','daemon_operation_identity','ordinary_ack_verified','installed_factories_verified','publication_acceptance'} and result['raw_writer_verified']is True and all(result[k]is False for k in ('daemon_operation_identity','ordinary_ack_verified','installed_factories_verified','publication_acceptance')),'native-seed-result-rights')
        need(result['schema_sha256']==hashlib.sha256(helper.encode(self.native['schema'])).hexdigest() and type(result['rows'])is list and len(result['rows'])==2,'native-seed-schema-result')
        for row,comic,issue,title in zip(result['rows'],helper.COMICS,helper.ISSUES,helper.SERIES):
            need(row['comicid']==comic and row['issueid']==issue and row['series']==title and row['folder']==str(s.library/title),'native-seed-owner-result')
        self.original_process(ready=False);p.read(self.helper_ref,private=False);return result

    def stage_inputs(self):
        need(not os.path.lexists(self.source),'native-input-no-replay')
        self.source.mkdir(mode=0o700);os.chown(self.source,1000,1000)
        for title in helper.SERIES:
            folder=self.source/title;folder.mkdir(mode=0o700);os.chown(folder,1000,1000)
            path=folder/(title.replace(' ','.')+'.002.(2024)-Fixture.cbz')
            raw=fixture.archive(identity=(title,2,2024),unrelated=title==helper.SERIES[1])
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'wb')as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            os.chown(path,1000,1000);bootstrap.backup.sync(folder)
            hashes=self.pages(path)
            self.inputs.append(dict(role='target' if title==helper.SERIES[0] else 'unrelated',host=str(path),folder='/config/'+str(folder.relative_to(self.s.native_mount)),name=path.name,sha256=hashlib.sha256(raw).hexdigest(),signature9=p.nine(os.lstat(path)),pages=hashes))
        bootstrap.backup.sync(self.source)

    @staticmethod
    def pages(path):
        with zipfile.ZipFile(path)as archive:
            names=sorted(n for n in archive.namelist() if n.endswith('.png'))
            need(len(names)==3 and archive.testzip()is None,'native-fixture-pages')
            return [hashlib.sha256(archive.read(n)).hexdigest()for n in names]

    def submit(self, row, original):
        self.original_process(ready=True)
        need(p.nine(os.lstat(original['host']))==original['signature9'] and hashlib.sha256(Path(original['host']).read_bytes()).hexdigest()==original['sha256'],'native-input-generation')
        # Existing primary API and actual PP_QUEUE; no new route or supplied ACK.
        result=self.s.step('native-force-process-'+row['issueid'],lambda:self.s.http('native','force-process-fixture',dict(comicid=row['comicid'],issueid=row['issueid'],nzb_name=original['name'],nzb_folder=original['folder'])))
        need(result=='Successfully submitted request for post-processing for '+original['name'],'native-queue-submit-unconfirmed')

    def complete(self,index,before):
        original=self.inputs[index];last=None
        for _ in range(30):
            self.s.seconds();last=self.request('observe');row=last['rows'][index]
            # The other original owner must not change during this actual job.
            need(last['rows'][1-index]==before['rows'][1-index],'native-unrelated-owner-changed')
            if row['status']=='Downloaded' and type(row['location'])is str and row['location']:
                name=Path(row['location']);need(not name.is_absolute() and len(name.parts)==1 and name.name not in ('.','..'),'native-output-location')
                target=Path(row['folder'])/name
                need(target.resolve(strict=True)==target and self.library in target.parents and all(not q.is_symlink()for q in (target,*target.parents)),'native-output-canonical')
                z=os.lstat(target);need(stat.S_ISREG(z.st_mode) and z.st_nlink==1 and z.st_uid==1000 and self.pages(target)==original['pages'],'native-output-pages')
                need(not os.path.lexists(original['host']),'native-source-not-consumed')
                need(hashlib.sha256(target.read_bytes()).hexdigest()==original['sha256'],'native-offline-bytes-changed')
                record=dict(role=original['role'],owner=dict(table='issues',issueid=row['issueid'],parentcomicid=row['comicid'],releasecomicid=row['comicid']),path=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),signature9=p.nine(os.lstat(target)),pages=original['pages'],catalog=row)
                # Require a second independently admitted catalog read, not a
                # queue reply or a single transient Downloaded row.
                final=self.request('observe');need(final['rows']==last['rows'] and p.nine(os.lstat(target))==record['signature9'],'native-completion-stability')
                return record,final
            need(row['status'] in ('Wanted','Snatched'),'native-processing-refused')
            time.sleep(min(0.2,self.s.seconds()))
        raise p.Held('native-processing-completion-timeout')

    def execute(self):
        try:
            self.original_process(ready=True)
            self.seed=self.s.step('native-fixture-seed',lambda:self.request('seed'))
            need(all(r['status']=='Wanted' and r['location']is None for r in self.seed['rows']),'native-seed-no-owner-grant')
            self.stage_inputs();before=self.seed
            for index in range(2):
                self.submit(before['rows'][index],self.inputs[index]);record,before=self.complete(index,before);self.records.append(record)
            self.original_process(ready=True)
            result=dict(version=1,kind='disposable-native-catalog-processing-observation',nonce=self.s.plan['nonce'],native_CID=self.s.plan['roles']['native']['id'],native_image=self.s.plan['images']['native'],process=self.original,helper=self.helper_ref,seed=self.seed,inputs=self.inputs,files=self.records,native_catalog_processing_observed=True,ordinary_ack_verified=False,daemon_operation_identity=False,installed_factories_verified=False,actual_nfs_verified=False,birth_verified=False,publication_acceptance=False,mutation_authority=False,automatic_replay=False)
            return dict(result=result,ref=bootstrap.put(self.output,result))
        except Exception:
            # No resubmission or uncertain source cleanup. Preserve every intent.
            if not os.path.lexists(self.output.with_suffix('.held.json')):bootstrap.put(self.output.with_suffix('.held.json'),dict(kind='native-catalog-processing-held',automatic_replay=False))
            raise
