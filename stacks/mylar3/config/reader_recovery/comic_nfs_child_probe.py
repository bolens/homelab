"""Finite probe requests on the retained child Channel; no Docker client."""
import base64
import copy
import subprocess


class Held(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise Held(reason)


class ChildProbe:
    def __init__(self, channel, input_ref):
        # The source-pinned ChildLeaseInterface must construct this with its
        # original actual __main__.Channel; this helper conveys facts only.
        self.channel = channel
        self.input_ref = copy.deepcopy(input_ref)
        self.prepared = False
        self.created = False
        self.started = False

    def prepare(self):
        need(not self.prepared, 'child-probe-no-reprepare')
        self.prepared = True
        seq = self.channel.send('nfs-probe', dict(operation='initialize', input=self.input_ref))
        value = self.channel.receive(seq)
        need(type(value) is dict and set(value) == {'name', 'argv', 'mounts'}, 'child-probe-original-prebirth-spec')
        return value

    def create(self):
        need(self.prepared, 'child-probe-requires-original-spec')
        need(not self.created, 'child-probe-no-rebirth')
        self.created = True
        seq = self.channel.send('nfs-probe', dict(operation='create', input=None))
        value = self.channel.receive(seq)
        need(type(value) is dict and set(value) == {'id', 'name', 'argv', 'mounts', 'profile'}, 'child-probe-original-spec-facts')
        return value

    def start_prepare(self):
        need(self.created and not self.started,'child-probe-original-prestart');self.started=True
        seq=self.channel.send('nfs-probe',dict(operation='start_prepare',input=None));value=self.channel.receive(seq)
        need(type(value) is dict and value.get('prepared') is True and value.get('native_grant') is False and value.get('publication_authority') is False,'child-probe-original-prepared')
        return value
    def execute_local(self):
        need(self.started,'child-probe-local-prepared')
        seq=self.channel.send('nfs-probe',dict(operation='execute_local',input=None));value=self.channel.receive(seq)
        need(type(value) is dict and value.get('kernel_finished') is True and value.get('local_exit_verified') is True and value.get('terminal_profile_verified') is False and value.get('profile') is None,'child-probe-local-kernel-result')
        out=base64.b64decode(value['stdout'],validate=True);err=base64.b64decode(value['stderr'],validate=True)
        need(len(out)<=8*1024**2 and len(err)<=4*1024**2,'child-probe-output-bound')
        return subprocess.CompletedProcess(['original-local-nfs-kernel'],0,out,err)
    def finish_after_release(self):
        need(self.started,'child-probe-original-finish')
        seq=self.channel.send('nfs-probe',dict(operation='finish',input=None));value=self.channel.receive(seq)
        need(type(value) is dict and set(value)=={'stdout','stderr','profile'},'child-probe-original-terminal-facts')
        out=base64.b64decode(value['stdout'],validate=True);err=base64.b64decode(value['stderr'],validate=True)
        need(len(out)<=8*1024**2 and len(err)<=4*1024**2,'child-probe-output-bound')
        return subprocess.CompletedProcess(['original-postlease-nfs-kernel'],0,out,err),value['profile']
