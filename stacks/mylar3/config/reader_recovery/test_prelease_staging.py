"""Original staging guards; local filesystem is explicitly refused as NFS."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import ast,os,tempfile,unittest
import comic_negative_nfs_active_lifecycle as m
class Staging(unittest.TestCase):
 def test_prelease_creation_preserves_all_admit_guards_except_no_lease_pulse(self):
  tree=ast.parse(Path(m.__file__).read_bytes());old=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='admit_parent');new=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='_prepare_parent')
  class Strip(ast.NodeTransformer):
   def visit_Expr(self,node):
    if isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):return None
    if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and isinstance(node.value.func.value,ast.Name) and node.value.func.value.id=='lease' and node.value.func.attr=='pulse':return None
    return self.generic_visit(node)
  # Normalize only the reviewed split of full9 roots into complete file9/node5
  # vectors. Every other guard and filesystem operation must still match.
  rewritten=[]
  for node in new.body:
   if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Tuple):
    self.assertEqual(ast.unparse(node.targets[0]), '(rootstates, rootnodes)')
    self.assertEqual(ast.unparse(node.value), '_protected_vectors(roots, root_files, root_nodes)')
    node=ast.parse('rootstates = {r: stamp(r) for r in roots}').body[0]
   elif isinstance(node,ast.For) and isinstance(node.target,ast.Tuple):
    self.assertEqual(ast.unparse(node.iter), 'rootnodes.items()')
    continue
   elif isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='forbidden_ids':
    self.assertEqual(ast.unparse(node.value), '{tuple(v[:2]) for v in (*rootstates.values(), *rootnodes.values())}')
    node=ast.parse('forbidden_ids = {tuple(v[:2]) for v in rootstates.values()}').body[0]
   rewritten.append(node)
  new.body=rewritten
  strip=Strip();a=strip.visit(old);b=strip.visit(new)
  self.assertEqual([ast.dump(x,include_attributes=False) for x in a.body],[ast.dump(x,include_attributes=False) for x in b.body])
 def test_actual_local_non_nfs_input_refuses_before_birth(self):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);protected=root/'protected';protected.mkdir(mode=0o700);parent=root/('.comic-nfs-private-'+'a'*32)
   plan=dict(path=str(parent),grandparent_signature=m.stamp(root),expected_device=m.stamp(root)[0],mount_identity=dict(fstype='not-nfs4'))
   with self.assertRaisesRegex(m.Held,'actual-nfs-mount'):m.prepare_parent(plan,[protected],lambda _:self.fail('non-NFS observer must not be used'))
   self.assertFalse(os.path.lexists(parent));self.assertEqual(os.listdir(root),['protected'])
 def test_stale_grandparent_and_protected_overlap_refuse_without_birth(self):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);protected=root/'protected';protected.mkdir(mode=0o700);parent=root/('.comic-nfs-private-'+'b'*32);old=m.stamp(root)
   (root/'foreign').write_bytes(b'preserved')
   plan=dict(path=str(parent),grandparent_signature=old,expected_device=old[0],mount_identity=dict(fstype='nfs4'))
   with self.assertRaisesRegex(m.Held,'grandparent-drift'):m.prepare_parent(plan,[protected],lambda _:self.fail('drift before observer'))
   plan['path']=str(protected/parent.name)
   with self.assertRaisesRegex(m.Held,'parent-protected-overlap'):m.prepare_parent(plan,[protected],lambda _:self.fail('overlap before observer'))
   self.assertEqual((root/'foreign').read_bytes(),b'preserved');self.assertFalse(parent.exists())
if __name__=='__main__':unittest.main()
