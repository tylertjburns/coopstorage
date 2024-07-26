from coopstorage.storage2.loc_load.types import *
from dataclasses import dataclass, field, asdict
import coopstorage.storage2.loc_load.dcs as dcs
import coopstorage.storage2.loc_load.qualifiers as lq
from coopstorage.storage2.loc_load.location import Location
import logging
from pprint import pformat

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True, kw_only=True)
class TransferRequest(dcs.BaseIdentifiedDataClass):
    load: dcs.Load = None
    source_loc: Location = None
    dest_loc: Location = None

    def verify(self):
        # source empty, firm load, dest firm --> store new load at dest
        if self.source_loc is None and \
            self.load is not None and \
            self.dest_loc is not None:
            return True

        # source firm, firm load, dest query --> transfer load
        if self.source_loc is not None and \
            self.load is not None and \
            self.dest_loc is not None:
            return True

        # source empty, firm load, dest empty --> remove load
        if self.source_loc is None and \
            self.load is not None and \
            self.dest_loc is None:
            return True

        raise ValueError(f"Unhandled Transfer Request \n{pformat(self)}")

    @property
    def Ready(self) -> bool:
        # is load ready to be removed
        try:
            if self.source_loc is None:
                pass
            else:
                self.source_loc.verify_removable(self.load)
        except:
            return False

        # is destination clear
        if len(self.dest_loc.get_addable_positions()) == 0:
            return False

        return True

    def handle(self):

        source_txt = ""
        if self.source_loc is not None:
            self.source_loc.remove_loads(
                load_ids=[self.load.id]
            )
            source_txt = f" from {self.source_loc.Id}"

        dest_txt = ""
        if self.dest_loc is not None:
            self.dest_loc.store_loads(
                load_ids=[self.load.id]
            )
            dest_txt = f" to {self.dest_loc.Id}"

        logger.info(f"Load {self.load.id} transferred{source_txt}{dest_txt}")


    def __post_init__(self):
        self.verify()

@dataclass(frozen=True, slots=True, kw_only=True)
class TransferRequestCriteria(dcs.BaseIdentifiedDataClass):
    load_query_args: lq.LoadQualifier = None
    source_loc_query_args: lq.LocationQualifier = None
    dest_loc_query_args: lq.LocationQualifier = None
    new_load: dcs.Load = None



