"""Private isolated fixture copies; public source modes and bytes are preserved."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
FIXES=Path(__file__).resolve().parent
SUITES=(('test_negative_reader_action.py',33),('test_negative_reader_partial_rollback.py',13),('test_negative_reader_preimage.py',7),('test_negative_terminal_observer.py',21),('test_reader_proof_producer.py', 11),('test_reader_proof_admission.py', 54),('test_reader_proof_timestamp_summary.py',13),('test_reader_lifecycle_parent.py',129),('test_native_evidence.py',39),('test_reader_phase_custody.py', 26),('test_terminal_reconstruction.py',11),('test_terminal_observation_producer.py', 20),('test_terminal_phase_custody.py',5),('test_archive_repair_protocol.py',28),('test_archive_repair_flow.py',16),('test_nfs_current_source.py',50),('test_hardlink_nfs_probe.py',29),('test_nfs_factual_successor.py',15),('test_nfs_public_geometry.py',9),('test_archive_proof_producer.py', 45),('test_archive_nfs_readiness.py',23))
SUITES=SUITES+(('test_archive_backup_action.py',20),('test_archive_backup_bootstrap.py',3),('test_archive_parent_composition.py',27),('test_archive_terminal_vectors.py',12),('test_archive_native_geometry.py',10),('test_archive_parent_admission.py',4),('test_archive_same_child_parent.py',22),('test_archive_same_child_producer.py',10),('test_archive_worker_vectors.py',16),('test_archive_worker_composition.py',45))
SUITES=SUITES+(('test_child_control_projection.py', 51), ('test_configured_parent_installation.py',25), ('test_nfs_parent_admission.py', 11), ('test_nfs_parent_session.py',14), ('test_retained_nfs_boundary.py', 9), ('test_host_lease.py',42), ('test_lease_supervision.py', 15), ('test_host_probe.py', 24), ('test_host_intents.py', 11), ('test_child_transport.py', 17), ('test_child_factory_interface.py', 8), ('test_factory_entry.py', 4), ('test_namespace_clients.py', 7))
SUITES=SUITES+(('test_nfs_current_roles.py',19),)
SUITES=SUITES+(('test_deferred_lease.py',11),('test_local_lease_window.py',14),('test_nfs_remote_guard.py',10),('test_expired_lease_paths.py',33))
SUITES=SUITES+(('test_probe_stdin_gate.py',4),('test_gated_host_probe.py',9),('test_phased_child_interface.py',12),('test_probe_lease_order.py',17),('test_prelease_staging.py',3),('test_probe_birth_registry.py',5))
SUITES=SUITES+(('test_probe_cleanup_transition.py',32),)
SUITES=SUITES+(('test_configured_worker_library_query.py', 81), ('test_effective_review_projection.py', 36), ('test_nfs_mount_namespace.py', 39), ('test_nfs_stopped_handoff.py', 94))
SUITES=SUITES+(('test_archive_common_root.py',102),('test_archive_plan13.py',24),('test_genuine_archive_fixture.py',6))
SUITES=SUITES+(('test_genuine_application_bootstrap.py',41),)
SUITES=SUITES+(('test_genuine_native_catalog.py',41),)
SUITES=SUITES+(('test_genuine_bootstrap_creator.py',73),)
SUITES=SUITES+(('test_genuine_bootstrap_batch.py',26),)
SUITES=SUITES+(('test_plan13_disposable_mapping.py',33),)
SUITES=SUITES+(('test_genuine_reader_quiescence.py',18),)
SUITES=SUITES+(('test_genuine_plan13_producer.py',29),)
SUITES=SUITES+(('test_genuine_current_roles.py',26),)
SUITES=SUITES+(('test_genuine_source_cohort.py',38),)
SUITES=SUITES+(('test_genuine_active_inputs.py',25),)
SUITES=SUITES+(('test_fixture_transition.py',41),('test_transition_consumers.py',9))
SUITES=SUITES+(('test_configured_archive_geometry.py', 34),('test_configured_plan13_producer.py', 17),)
# Resource ceiling shared with the complete owning source union. This is not
# the current manifest census: membership comes from the checked source maps.
SUITE_TIMEOUT=120
MAX_SOURCE_FILES=1024
MAX_BYTES=16*1024**2
class Held(RuntimeError):pass
def sig(z):return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def checked(p,expected,files,nodes):
 p=Path(p)
 if p.resolve()!=p or any(q.is_symlink() for q in (p,*p.parents)):raise Held('Source path is not canonical')
 for q in p.parents:
  z=q.lstat();value=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
  if not stat.S_ISDIR(z.st_mode) or (q in nodes and nodes[q]!=value):raise Held('Source ancestor changed')
  nodes[q]=value
 before=p.lstat()
 if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>MAX_BYTES:raise Held('Source is not bounded regular single-link')
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  if sig(os.fstat(fd))!=sig(before):raise Held('Source open changed')
  with os.fdopen(os.dup(fd),'rb') as f:raw=f.read(MAX_BYTES+1)
  if sig(os.fstat(fd))!=sig(before) or sig(p.lstat())!=sig(before) or len(raw)!=before.st_size or (expected is not None and digest(raw)!=expected):raise Held('Source bytes or incarnation changed')
 finally:os.close(fd)
 if p in files and files[p]!=sig(before):raise Held('Original source replaced')
 files[p]=sig(before);return raw

def close_original(files,nodes):
 # Last closure is direct: no replaceable hash/stat/signature helper callback.
 for p,value in tuple(nodes.items()):
  z=os.lstat(p)
  if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('Original source directory drift')
 for p,value in tuple(files.items()):
  z=os.lstat(p)
  if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise Held('Original source file drift')

def copy_fixtures(fixes,temporary):
 fixes=Path(fixes);root=fixes/'reader_recovery';files={};nodes={}
 manifest_raw=checked(root/'source-manifest.json',None,files,nodes);manifest=json.loads(manifest_raw)
 cohort=json.loads(checked(fixes/'publication_reader_cohort.json',None,files,nodes))
 if manifest['version']!=1 or type(manifest['files']) is not dict or not 1<=len(manifest['files'])<=MAX_SOURCE_FILES:raise Held('Explicit fixture manifest required')
 private=Path(temporary)/'config';private.mkdir(mode=0o700);tree=private/'reader_recovery';tree.mkdir(mode=0o700);total=0
 # Only declared files are copied. Ignored configuration and extra entries are
 # never walked or adopted into the private fixture tree.
 for name,row in manifest['files'].items():
  rel=PurePosixPath(name)
  if type(name) is not str or rel.is_absolute() or '..' in rel.parts or str(rel)!=name or '\\' in name or '\x00' in name:raise Held('Unsafe fixture path')
  raw=checked(root/name,row['sha256'],files,nodes);total+=len(raw)
  if total>MAX_BYTES:raise Held('Fixture aggregate bound')
  target=tree/name;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  with os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(raw)
  if target.read_bytes()!=raw:raise Held('Private fixture readback')
 # Admission tests name the canonical module in the parent config directory.
 raw=checked(fixes/'publication_reader_admission.py',cohort['modules']['publication_reader_admission']['sha256'],files,nodes)
 with os.fdopen(os.open(private/'publication_reader_admission.py',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(raw)
 if (private/'publication_reader_admission.py').read_bytes()!=raw:raise Held('Private admission readback')
 # The real host-lease fixtures consume the exact existing Writer source.
 raw=checked(fixes/'media_writer.py',cohort['existing_sdk_closure']['media_writer']['tracked_source_sha256'],files,nodes)
 with os.fdopen(os.open(private/'media_writer.py',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(raw)
 if (private/'media_writer.py').read_bytes()!=raw:raise Held('Private Writer readback')
 # The fixed installer locator also names this canonical sibling. Its cohort
 # digest is mandatory, never the optional expected=None manifest read mode.
 scope_pin=cohort['modules']['publication_native_configured_scope']['sha256']
 if type(scope_pin) is not str or re.fullmatch('[a-f0-9]{64}',scope_pin) is None:raise Held('Explicit canonical scope source pin required')
 raw=checked(fixes/'publication_native_configured_scope.py',scope_pin,files,nodes)
 with os.fdopen(os.open(private/'publication_native_configured_scope.py',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(raw)
 if (private/'publication_native_configured_scope.py').read_bytes()!=raw:raise Held('Private scope readback')
 # The genuine health/lifecycle regression consumes only these two canonical
 # native siblings. The existing source map supplies pins, never copy names.
 native_rows=json.loads(checked(fixes/'standalone_control_sources.json',None,files,nodes))
 native_names=('queue_control.py','worker_health.py')
 if 'genuine_archive_fixture.py' in manifest['files']:
  native_names+=('publication_guard.py','publication_archive_layout.py','publication_archive_derivative.py','publication_archive_repair.py','tagger_metadata.py')
 for name in native_names:
  pins=[row['sha256'] for row in native_rows if row.get('path')==name]
  if len(pins)!=1 or type(pins[0]) is not str or re.fullmatch('[a-f0-9]{64}',pins[0]) is None:raise Held('Explicit native health source pin required')
  raw=checked(fixes/name,pins[0],files,nodes)
  with os.fdopen(os.open(private/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(raw)
  if (private/name).read_bytes()!=raw:raise Held('Private native health readback')
 # The SourceCohort fixtures need the exact finite owning source union.
 # Copy original row paths, never target aliases or discovered directory entries.
 pins={}
 def admit(name,pin):
  if type(name)is not str:raise Held('Unsafe owning source path')
  rel=PurePosixPath(name)
  if rel.is_absolute()or '..'in rel.parts or str(rel)!=name or '\\'in name or '\x00'in name:raise Held('Unsafe owning source path')
  if type(pin)is not str or re.fullmatch('[a-f0-9]{64}',pin)is None:raise Held('Explicit owning source pin required')
  if name in pins and pins[name]!=pin:raise Held('Conflicting owning source pins')
  pins[name]=pin
 for name,row in manifest['files'].items():admit('reader_recovery/'+name,row['sha256'])
 for name in ('reader_recovery/source-manifest.json','publication_reader_cohort.json','standalone_control_sources.json'):
  admit(name,digest(checked(fixes/name,None,files,nodes)))
 admit('publication_reader_admission.py',cohort['modules']['publication_reader_admission']['sha256'])
 admit('media_writer.py',cohort['existing_sdk_closure']['media_writer']['tracked_source_sha256'])
 admit('publication_native_configured_scope.py',scope_pin)
 if type(native_rows)is not list or not 1<=len(native_rows)<=MAX_SOURCE_FILES:raise Held('Finite owning source map required')
 for row in native_rows:
  if type(row)is not dict or not {'path','sha256'}<=set(row):raise Held('Explicit owning source row required')
  admit(row['path'],row['sha256'])
 if len(pins)>MAX_SOURCE_FILES:raise Held('Owning source union bound')
 union_bytes=0
 for name,pin in pins.items():
  raw=checked(fixes/name,pin,files,nodes);union_bytes+=len(raw)
  if union_bytes>MAX_BYTES:raise Held('Fixture aggregate bound')
  target=private/name
  if target.exists():
   if target.is_symlink()or target.read_bytes()!=raw:raise Held('Private owning source conflict')
   continue
  target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  with os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')as f:f.write(raw)
  if target.read_bytes()!=raw:raise Held('Private owning source readback')
 close_original(files,nodes);return tree,files,nodes

def finish_originals(files,nodes,primary,cleanup=None):
 secondary=None
 try:
  if files is not None:close_original(files,nodes)
 except BaseException as error:secondary=error
 if cleanup is not None:
  cleanup.__cause__=secondary;secondary=cleanup
 if primary is not None:raise primary from secondary
 if secondary is not None:raise secondary

def source_inventory(fixes):
 """Derive closed declared membership without executing controls or factories."""
 fixes=Path(fixes);rows={};files=None;nodes=None;value=None;primary=None;cleanup=None
 try:
  with tempfile.TemporaryDirectory(prefix='reader-source-inventory-') as temporary:
   try:
    _,files,nodes=copy_fixtures(fixes,temporary)
    for path,before in files.items():
     raw=checked(path,None,files,nodes)
     rows[str(path.relative_to(fixes))]=dict(path=str(path),sha256=digest(raw),signature9=list(before))
    value=dict(files=rows,nodes={str(p):list(row) for p,row in nodes.items()},
               suites=[list(row) for row in SUITES],tests=sum(count for _,count in SUITES),
               controls_executed=False,installed_factory_verified=False)
   except BaseException as error:primary=error
 except BaseException as error:cleanup=error
 # Temporary cleanup and result construction are callbacks too. The last
 # original closure follows both, and never hides their primary failure.
 finish_originals(files,nodes,primary,cleanup)
 return value

def run(fixes):
 results=[];files=None;nodes=None;value=None;primary=None;cleanup=None
 try:
  with tempfile.TemporaryDirectory(prefix='reader-recovery-private-') as temporary:
   try:
    root,files,nodes=copy_fixtures(fixes,temporary)
    for name,count in SUITES:
     result=subprocess.run([sys.executable,'-I','-B',str(root/name)],capture_output=True,timeout=SUITE_TIMEOUT)
     output=result.stderr.decode('utf-8','strict');counts=re.findall(r'^Ran ([0-9]+) tests? in ',output,re.MULTILINE)
     if result.returncode or counts!=[str(count)] or '\nOK\n' not in output or re.search(r'\bskipped\b',output,re.I):
      sys.stderr.buffer.write(result.stderr);raise Held('Recovery control collection/result')
     results.append(dict(suite=name,count=count,skips=0,stdout_sha256=digest(result.stdout),stderr_sha256=digest(result.stderr)))
    value=dict(kind='private-build-only-reader-recovery-controls',tests=sum(x['count'] for x in results),suites=results,original_source_unchanged=True,installed_factory_verified=False,publication_acceptance=False,reader_resume_authority=False)
   except BaseException as error:primary=error
 except BaseException as error:cleanup=error
 finish_originals(files,nodes,primary,cleanup)
 return value

def main():
 if not sys.dont_write_bytecode:raise Held('Build controls require -B')
 print(json.dumps(run(FIXES),sort_keys=True))
if __name__=='__main__':main()
