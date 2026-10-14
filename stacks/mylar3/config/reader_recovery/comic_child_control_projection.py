"""Host-owned finite root/child controls; source copies confer no authority."""
import hashlib
import os
from pathlib import Path
import stat
import weakref
_SEALS=weakref.WeakKeyDictionary()

MAX = 64 * 1024**2
UID = GID = 1000
class Held(ValueError):pass

def need(ok, reason):
    if not ok:raise Held(reason)
def nine(z):return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
def five(z):return (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
def frozen(ref):
    need(type(ref) is dict and set(ref)=={'path','sha256','signature9'},'child-control-ref')
    p,sha,stamp=ref['path'],ref['sha256'],ref['signature9']
    need(type(p) is str and Path(p).is_absolute() and '..' not in Path(p).parts and type(sha) is str and len(sha)==64 and all(x in '0123456789abcdef' for x in sha) and type(stamp) in (list,tuple) and len(stamp)==9 and all(type(x) is int for x in stamp),'child-control-ref-values')
    return p,sha,tuple(stamp)
def reference(row):return dict(path=row[0],sha256=row[1],signature9=list(row[2]))
def ancestors(path):
    rows=[]
    for p in Path(path).parents:
        z=os.lstat(p);need(stat.S_ISDIR(z.st_mode),'child-control-ancestor');rows.append((str(p),five(z)))
    return tuple(rows)
def raw(ref, owner):
    p,sha,stamp=frozen(ref);nodes=ancestors(p)
    need(stamp[6]==owner and stat.S_ISREG(stamp[5]) and stat.S_IMODE(stamp[5])==0o600 and stamp[8]==1 and 0<stamp[2]<=MAX,'child-control-owner')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        need(nine(os.fstat(fd))==stamp and nine(os.lstat(p))==stamp,'child-control-original-FD')
        pieces=[];left=stamp[2]
        while left:
            b=os.read(fd,min(left,65536));need(bool(b),'child-control-short-read');pieces.append(b);left-=len(b)
        data=b''.join(pieces);need(hashlib.sha256(data).hexdigest()==sha and nine(os.fstat(fd))==stamp,'child-control-hash')
    finally:os.close(fd)
    close(((p,stamp),),nodes)
    return data,nodes

def close(files,nodes):
    for p,v in nodes:
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('child-control-final5')
    for p,v in files:
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('child-control-final9')

class Tree:
    """One parent creates this new child tree; all root originals stay distinct."""
    def __init__(self, root, child_root, original_operation, read_original, uid=UID, gid=GID):
        self.root=Path(root);self.child_root=Path(child_root);self.original_operation=Path(original_operation)
        need(self.root.is_absolute() and self.child_root.is_absolute() and self.original_operation.is_absolute() and not os.path.lexists(self.root),'child-tree-exclusive')
        need(type(uid) is int and type(gid) is int and uid>=0 and gid>=0 and (os.geteuid()==0 or (uid,gid)==(os.geteuid(),os.getegid())),'child-tree-owner')
        self.uid,self.gid=uid,gid;self.read_original=read_original
        self.nodes=ancestors(self.root);self.directories=();self.pairs=();self.outputs=();self.scopes=();self.nfs_controls=()
        self.identity=(str(self.root),str(self.child_root),str(self.original_operation),uid,gid,id(read_original))
        self._mkdir(self.root);self._seal()
    def _seal(self):
        _SEALS[self]=(self.identity,self.nodes,self.directories,self.pairs,self.outputs,self.scopes,self.nfs_controls)
    def _state(self):
        return (self.identity,self.nodes,self.directories,self.pairs,self.outputs,self.scopes,self.nfs_controls)
    def _append(self,field,value,expected):
        need(self._state()==expected and (str(self.root),str(self.child_root),str(self.original_operation),self.uid,self.gid,id(self.read_original))==self.identity,'child-tree-original-before-commit')
        setattr(self,field,getattr(self,field)+value);self._seal()
    def _mkdir(self,path):
        expected=self._state()
        path=Path(path);path.mkdir(mode=0o700);fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            born=five(os.fstat(fd));need(stat.S_ISDIR(born[2]) and stat.S_IMODE(born[2])==0o700 and born[3:]==(os.geteuid(),os.getegid()),'child-directory-birth')
            os.fchown(fd,self.uid,self.gid);os.fsync(fd);current=five(os.fstat(fd))
            need(current[:3]==born[:3] and current[3:]==(self.uid,self.gid) and five(os.lstat(path))==current,'child-directory-owned-transition')
        finally:os.close(fd)
        self._append('directories',((str(path),current),),expected)
        return path
    def phase(self,name):
        need(name in ('backup','prepare','execute','verify-terminal','nfs'),'child-phase-name')
        path=self.root/name
        if not any(p==str(path) for p,_ in self.directories):self._mkdir(path)
        return path
    def reserve_nfs_control(self,ref):
        original=frozen(ref);expected=self._state()
        rows=[r for r in self.nfs_controls if r[0]==original[0]]
        if rows:
            need(rows==[original],'nfs-control-original-conflict');self.check();return
        need(len(self.nfs_controls)<48,'nfs-control-declared-bound')
        data=self.read_original(reference(original));need(hashlib.sha256(data).hexdigest()==original[1],'nfs-control-original-source')
        self._append('nfs_controls',(original,),expected);self.check()

    def _pair_bound(self,original=None):
        ordinary=sum(p[0] not in self.nfs_controls for p in self.pairs)+len(self.outputs)
        need(ordinary<32 or original in self.nfs_controls,'child-control-bound')
        need(len(self.pairs)+len(self.outputs)<80,'child-control-total-bound')

    def project(self,ref):
        original=frozen(ref)
        found=[p for p in self.pairs if p[0][0]==original[0]]
        if found:
            need(len(found)==1 and found[0][0]==original,'child-original-ref-conflict');self.check();return reference(found[0][1])
        self._pair_bound(original)
        if Path(original[0]).parent==self.original_operation:
            target=self.root/Path(original[0]).name
        else:
            prefix=self.root/('control-'+hashlib.sha256(original[0].encode()).hexdigest()[:24]);self._mkdir(prefix);target=prefix/Path(original[0]).name
        expected=self._state()
        original_nodes=ancestors(original[0])
        data=self.read_original(reference(original));need(hashlib.sha256(data).hexdigest()==original[1],'child-root-original-hash')
        need(nine(os.lstat(original[0]))==original[2],'child-root-original9')
        fd=os.open(target,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        try:
            born=nine(os.fstat(fd));need(stat.S_ISREG(born[5]) and stat.S_IMODE(born[5])==0o600 and born[6:]==(os.geteuid(),os.getegid(),1) and born[:2]!=original[2][:2],'child-copy-exclusive')
            view=memoryview(data)
            while view:
                n=os.write(fd,view);need(n>0,'child-copy-short-write');view=view[n:]
            os.fsync(fd);written=nine(os.fstat(fd));need(written[:2]==born[:2] and written[5:]==born[5:] and written[2]==len(data),'child-copy-written')
            os.fchown(fd,self.uid,self.gid);stamp=nine(os.fstat(fd));need(stamp[:4]==written[:4] and stamp[5]==written[5] and stamp[6:]==(self.uid,self.gid,1),'child-copy-own-transition')
            os.lseek(fd,0,0);back=os.read(fd,len(data)+1);need(back==data and nine(os.fstat(fd))==stamp,'child-copy-readback')
        finally:os.close(fd)
        child=(str(target),original[1],stamp);pair=(original,child,original_nodes,ancestors(target))
        # Include immutable facts before checks; failed evidence is retained, never rebaselined.
        self._append('pairs',(pair,),expected);self.check()
        return reference(child)
    def projected(self,ref):
        original=frozen(ref);outputs=[r for r in self.outputs if r[3]==original]
        if outputs:
            need(len(outputs)==1,'child-output-projected-unique');self.check();return reference(outputs[0][4])
        host=self.project(ref);return dict(host,path=str(self.child_root/Path(host['path']).relative_to(self.root)))
    def original(self,ref):
        p,sha,stamp=frozen(ref);host=self.host(p)
        rows=[row[0] for row in self.pairs if row[1]==(host,sha,stamp)]
        rows += [row[3] for row in self.outputs if row[4]==(p,sha,stamp)]
        need(len(rows)==1,'child-pair-original-binding');self.check();return reference(rows[0])
    def child(self,path):
        path=Path(path)
        scoped=[r for r in self.scopes if path==Path(r[2]) or Path(r[2]) in path.parents]
        if scoped:
            need(len(scoped)==1,'child-private-scope-path-unique');r=scoped[0]
            prefix=self.child_root/('scope-'+r[4]+'-'+hashlib.sha256(r[0].encode()).hexdigest()[:16])
            return str(prefix/path.relative_to(r[2]))
        pairs=[p for p in self.pairs if p[0][0]==str(path)]
        if pairs:return str(self.child_root/Path(pairs[0][1][0]).relative_to(self.root))
        if path==self.root or self.root in path.parents:return str(self.child_root/path.relative_to(self.root))
        if path==self.original_operation or self.original_operation in path.parents:return str(self.child_root/path.relative_to(self.original_operation))
        return None
    def host(self,path):
        path=Path(path)
        for r in self.scopes:
            prefix=self.child_root/('scope-'+r[4]+'-'+hashlib.sha256(r[0].encode()).hexdigest()[:16])
            if path==prefix or prefix in path.parents:return str(Path(r[2])/path.relative_to(prefix))
        need(path==self.child_root or self.child_root in path.parents,'child-tree-path')
        return str(self.root/path.relative_to(self.child_root))
    def original_host(self, path):
        path=str(path)
        rows=[p for p in self.pairs if p[1][0]==path]
        if rows:
            need(len(rows)==1,'child-original-host-unique');self.check();return rows[0][0][0]
        outputs=[r for r in self.outputs if r[0]==path]
        if outputs:
            need(len(outputs)==1,'child-output-host-unique');self.check();return outputs[0][3][0]
        return path
    def scope(self, original_path, role):
        need(role in ('scratch','retention_root'),'child-private-scope-role')
        expected=self._state()
        original_path=Path(original_path);before=five(os.lstat(original_path));nodes=ancestors(original_path)
        need(stat.S_ISDIR(before[2]) and stat.S_IMODE(before[2])==0o700,'child-private-scope-original')
        rows=[r for r in self.scopes if r[0]==str(original_path)]
        if rows:
            need(len(rows)==1 and rows[0][1]==before and rows[0][4]==role,'child-private-scope-conflict');self.check();return rows[0][2]
        direct=before[3:]==(self.uid,self.gid)
        if not direct:need(not os.listdir(original_path),'child-private-scope-nonempty-original')
        placeholder=self.root/('scope-'+role+'-'+hashlib.sha256(str(original_path).encode()).hexdigest()[:16])
        self._mkdir(placeholder);expected=self._state()
        target=original_path if direct else placeholder;stamp=before if direct else five(os.lstat(target))
        self._append('scopes',((str(original_path),before,str(target),stamp,role,nodes),),expected);self.check()
        return str(target)
    def scope_owner(self,path):
        path=str(path);rows=[r for r in self.scopes if r[2]==path]
        need(len(rows)==1,'child-private-scope-owned-binding');self.check();return self.uid
    def output(self,ref,expected_path,role):
        need(role in ('native_scope','report','terminal','factual_record'),'child-output-role')
        child=frozen(ref);need(child[0]==str(expected_path),'child-output-exact-path')
        existing=[r for r in self.outputs if r[4][0]==child[0]]
        if existing:
            need(len(existing)==1 and existing[0][4]==child and existing[0][5]==role,'child-output-original-conflict');self.check()
            data,_=raw(reference(existing[0][3]),os.geteuid());self.check();return data,reference(existing[0][3])
        self._pair_bound()
        expected=self._state()
        host=self.host(child[0]);hoststamp=nine(os.lstat(host))
        need(hoststamp==child[2],'child-output-returned-original9')
        hostref=dict(path=host,sha256=child[1],signature9=list(hoststamp))
        data,nodes=raw(hostref,self.uid)
        folder=self.original_operation/'child-output-views'
        if not any(path==str(folder) for path,_ in self.nodes):
            folder.mkdir(mode=0o700);folder_fd=os.open(folder,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            try:
                folder_stamp=five(os.fstat(folder_fd));need(stat.S_ISDIR(folder_stamp[2]) and stat.S_IMODE(folder_stamp[2])==0o700 and folder_stamp[3:]==(os.geteuid(),os.getegid()),'child-output-folder-creator')
                need(five(os.lstat(folder))==folder_stamp,'child-output-folder-path')
            finally:os.close(folder_fd)
            self._append('nodes',((str(folder),folder_stamp),),expected);expected=self._state()
        rootpath=folder/(hashlib.sha256(host.encode()).hexdigest()+'.json')
        fd=os.open(rootpath,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        try:
            born=nine(os.fstat(fd));need(stat.S_ISREG(born[5]) and stat.S_IMODE(born[5])==0o600 and born[6:]==(os.geteuid(),os.getegid(),1),'child-output-view-birth')
            view=memoryview(data)
            while view:
                n=os.write(fd,view);need(n>0,'child-output-view-write');view=view[n:]
            os.fsync(fd);stamp=nine(os.fstat(fd));need(stamp[:2]==born[:2] and stamp[5:]==born[5:] and stamp[2]==len(data),'child-output-view-creator')
            os.lseek(fd,0,0);need(os.read(fd,len(data)+1)==data and nine(os.fstat(fd))==stamp,'child-output-view-readback')
        finally:os.close(fd)
        viewref=(str(rootpath),child[1],stamp)
        self._append('outputs',((host,child[1],hoststamp,viewref,child,role,nodes,ancestors(rootpath)),),expected);self.check()
        return data,reference(viewref)
    def readonly_files(self):
        return tuple((p[1][0],self.child(p[1][0])) for p in self.pairs if not p[0][0].endswith('.lifecycle.json'))
    def check(self):
        sealed=_SEALS.get(self)
        need(sealed==(self.identity,self.nodes,self.directories,self.pairs,self.outputs,self.scopes,self.nfs_controls),'child-tree-logical-seal')
        need((str(self.root),str(self.child_root),str(self.original_operation),self.uid,self.gid,id(self.read_original))==self.identity,'child-tree-original-identity')
        pairs=self.pairs;directories=self.directories;outputs=self.outputs;nodes=self.nodes
        files=tuple((p[0][0],p[0][2]) for p in pairs)+tuple((p[1][0],p[1][2]) for p in pairs)+tuple((r[0],r[2]) for r in outputs)+tuple((r[3][0],r[3][2]) for r in outputs)
        all_nodes=nodes+directories+tuple(n for p in pairs for n in (*p[2],*p[3]))+tuple(n for r in outputs for n in (*r[6],*r[7]))+tuple((r[0],r[1]) for r in self.scopes)+tuple((r[2],r[3]) for r in self.scopes)+tuple(n for r in self.scopes for n in r[5])
        root_required={Path(p).name for p,_ in directories if Path(p).parent==self.root}|{Path(p[1][0]).name for p in pairs if Path(p[1][0]).parent==self.root}|{Path(r[0]).name for r in outputs if Path(r[0]).parent==self.root}
        root_allowed=set(root_required)
        root_allowed.update(Path(p[1][0]).with_suffix('.native-scope.json').name for p in pairs if Path(p[1][0]).parent==self.root and p[1][0].endswith('-input.json'))
        namespaces=tuple((path,tuple(sorted(Path(p[1][0]).name for p in pairs if Path(p[1][0]).parent==Path(path)))) for path,_ in directories if Path(path).name.startswith('control-'))
        viewfolder=self.original_operation/'child-output-views'
        if any(p==str(viewfolder) for p,_ in nodes):namespaces+=((str(viewfolder),tuple(sorted(Path(r[3][0]).name for r in outputs))),)
        close(files,all_nodes)
        actual_root=set(os.listdir(self.root))
        if not root_required<=actual_root<=root_allowed:raise Held('child-tree-root-namespace')
        for path,expected_names in namespaces:
            if tuple(sorted(os.listdir(path)))!=expected_names:raise Held('child-tree-control-namespace')
        # Original tuple facts survive all replaceable helpers above.
        for path,v in all_nodes:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('child-tree-original5')
        for path,v in files:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('child-tree-original9')
        if sealed!=(self.identity,self.nodes,self.directories,self.pairs,self.outputs,self.scopes,self.nfs_controls) or _SEALS.get(self)!=sealed:raise Held('child-tree-logical-final')
