"""Archive-only checked source protocol; builds no custody or mutation capability."""
import copy
import hashlib
from pathlib import Path
import re
# Canonical action is loaded by source pin by the eventual owning parent. This
# adjacent pure import is for public host protocol tools, not installed SDK types.
from comic_archive_repair_action import owner_request,need,encoded,ROLES


def phase_input(*,phase,request,controls,archive_scopes,operation,sdk_map,nonce,parent_sha256,selected_image,provider,input_path,execution_originals=None):
 request=owner_request(request)
 need(phase in ('execute','verify-terminal'),'repair-protocol-phase')
 need(type(controls) is dict and set(controls)==ROLES,'repair-protocol-distinct-eight-controls')
 need(type(provider) is dict and set(provider)=={'path','sha256'},'repair-protocol-provider')
 for value in (nonce,parent_sha256,provider['sha256']):need(type(value) is str and re.fullmatch('[0-9a-f]{64}',value),'repair-protocol-source-identity')
 need(type(selected_image) is str and re.fullmatch('sha256:[0-9a-f]{64}',selected_image),'repair-protocol-image')
 for ref in (*controls.values(),archive_scopes,sdk_map):
  need(type(ref) is dict and set(ref) in ({'path','sha256'},{'path','sha256','signature9'}) and type(ref['path']) is str and Path(ref['path']).is_absolute() and type(ref['sha256']) is str and re.fullmatch('[0-9a-f]{64}',ref['sha256']),'repair-protocol-explicit-ref')
 for p in (operation,input_path,provider['path']):need(type(p) is str and Path(p).is_absolute() and str(Path(p))==p and '..' not in Path(p).parts,'repair-protocol-canonical-path-shape')
 template=['/lsiopy/bin/python3','-I','-B',provider['path'],'--phase',phase,'--input',input_path,'--input-sha256','<INPUT_SHA256>','--source-sha256',provider['sha256']]
 value={'version':1,'action':'archive-one','command_template':template,'operation':operation,'sdk_map':copy.deepcopy(sdk_map),'nonce':nonce,'parent_sha256':parent_sha256,'selected_image':selected_image,'controls':copy.deepcopy(controls),'archive_scopes':copy.deepcopy(archive_scopes),'owner':request['owner'],'operation_id':request['operation_id']}
 if phase=='verify-terminal':
  need(type(execution_originals) is dict and set(execution_originals)=={'path','sha256','signature9'},'repair-protocol-original-execution')
  value['execution_originals']=copy.deepcopy(execution_originals)
 else:need(execution_originals is None,'repair-protocol-no-foreign-terminal-evidence')
 raw=encoded(value);digest=hashlib.sha256(raw).hexdigest();command=[digest if x=='<INPUT_SHA256>' else x for x in template]
 return {'input_bytes':raw,'input_sha256':digest,'actual_command':command,'mutation_authority':False,'publication_acceptance':False,'custody_produced':False}
