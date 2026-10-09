"""Exact typed reversed-terminal consumer; receipts never mint capabilities."""
import threading
import weakref
from pathlib import Path
from mylar import publication_archive_adoption as adoption
from mylar import publication_archive_owned as owned
from mylar import publication_archive_reader as reader

_KEY=object();_SEALS=weakref.WeakKeyDictionary()

def installed():
    adoption.installed()
    path=Path(__file__)
    owned.check(path==Path('/app/mylar3/mylar/publication_archive_rollback.py') and path.resolve()==path,'installed-repair-rollback')

class RepairRollbackTerminal:
    __slots__=('adoption','preparation','reader','writer','_thread','_ids','__weakref__')
    def __init__(self,key,cap):
        owned.check(key is _KEY,'rollback-owning-factory')
        self.adoption=cap;self.preparation=cap.preparation;self.reader=cap.reader;self.writer=cap.preparation._writer;self._thread=threading.get_ident()
        self._ids=(id(cap),id(self.preparation),id(self.reader),id(self.writer))
        _SEALS[self]=(self._thread,self._ids)
    def close(self):
        original=_SEALS.get(self)
        owned.check(original==(self._thread,self._ids) and self._thread==threading.get_ident() and self._ids==(id(self.adoption),id(self.preparation),id(self.reader),id(self.writer)) and self.adoption.preparation is self.preparation and self.adoption.reader is self.reader and self.preparation._writer is self.writer,'rollback-owning-lifetime')
        owned.check(type(self.adoption) is adoption.RepairAdoption and type(self.preparation) is owned.RepairPreparation and type(self.reader) is reader.RepairReaderLease,'rollback-exact-types')
        self.adoption.close()
        owned.check(self.adoption._phase in ('reversed','rollback-complete'),'rollback-exact-phase')
    def clear(self):
        self.close();owned.check(self.adoption._phase=='reversed','rollback-no-replay')
        # The owning method returns only after its final raw closure and restores
        # the durable successor on uncertainty. No callback follows that boundary.
        return self.adoption.complete_reversed()
    @property
    def binding(self):
        self.close();return self.adoption.binding

def from_reversed(cap):
    installed();owned.check(type(cap) is adoption.RepairAdoption,'rollback-exact-adoption')
    cap.close();owned.check(cap._phase=='reversed','rollback-reversed-required')
    value=RepairRollbackTerminal(_KEY,cap);value.close();return value
