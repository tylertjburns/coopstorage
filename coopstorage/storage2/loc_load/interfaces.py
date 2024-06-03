from typing import Protocol, Iterable
import coopstorage.storage2.loc_load.dcs as dcs

class IStorer(Protocol):
    def store(self,
             loads: Iterable[dcs.Load]):
        pass

    def remove(self,
               loads: Iterable[dcs.Load]):
        pass