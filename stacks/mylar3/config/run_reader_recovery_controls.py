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
SUITES=(('test_negative_reader_action.py',33),('test_negative_reader_partial_rollback.py',13),('test_negative_reader_preimage.py',7),('test_negative_terminal_observer.py',21),('test_reader_proof_producer.py',10),('test_reader_proof_admission.py',52),('test_reader_proof_timestamp_summary.py',13),('test_reader_lifecycle_parent.py',86),('test_native_evidence.py',39),('test_reader_phase_custody.py',25),('test_terminal_reconstruction.py',11),('test_terminal_observation_producer.py',19),('test_terminal_phase_custody.py',5),('test_archive_repair_protocol.py',28),('test_archive_repair_flow.py',15),('test_nfs_current_source.py',35),('test_hardlink_nfs_probe.py',29),('test_nfs_factual_successor.py',13),('test_nfs_public_geometry.py',9),('test_archive_proof_producer.py',25),('test_archive_nfs_readiness.py',8))
SUITES=SUITES+(('test_archive_backup_action.py',8),('test_archive_backup_bootstrap.py',3),('test_archive_parent_composition.py',12),('test_archive_terminal_vectors.py',12),('test_archive_native_geometry.py',4),('test_archive_parent_admission.py',4),('test_archive_same_child_parent.py',13),('test_archive_same_child_producer.py',6))
MAX_FILES=256
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
 if manifest['version']!=1 or type(manifest['files']) is not dict or not 1<=len(manifest['files'])<=MAX_FILES:raise Held('Explicit fixture manifest required')
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
 close_original(files,nodes);return tree,files,nodes

def run(fixes):
 results=[]
 with tempfile.TemporaryDirectory(prefix='reader-recovery-private-') as temporary:
  root,files,nodes=copy_fixtures(fixes,temporary)
  for name,count in SUITES:
   result=subprocess.run([sys.executable,'-I','-B',str(root/name)],capture_output=True,timeout=120)
   output=result.stderr.decode('utf-8','strict');counts=re.findall(r'^Ran ([0-9]+) tests? in ',output,re.MULTILINE)
   if result.returncode or counts!=[str(count)] or '\nOK\n' not in output or re.search(r'\bskipped\b',output,re.I):
    sys.stderr.buffer.write(result.stderr);raise Held('Recovery control collection/result')
   results.append(dict(suite=name,count=count,skips=0,stdout_sha256=digest(result.stdout),stderr_sha256=digest(result.stderr)))
  close_original(files,nodes)
 return dict(kind='private-build-only-reader-recovery-controls',tests=sum(x['count'] for x in results),suites=results,original_source_unchanged=True,installed_factory_verified=False,publication_acceptance=False,reader_resume_authority=False)
def main():
 if not sys.dont_write_bytecode:raise Held('Build controls require -B')
 print(json.dumps(run(FIXES),sort_keys=True))
if __name__=='__main__':main()
