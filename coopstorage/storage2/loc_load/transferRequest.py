from dataclasses import dataclass, field, asdict
import coopstorage.storage2.loc_load.dcs as dcs
import coopstorage.storage2.loc_load.qualifiers as lq
from coopstorage.storage2.loc_load.location import Location
import logging
from pprint import pformat
from typing import Self, Dict

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True, kw_only=True)
class TransferRequestCriteria(dcs.BaseIdentifiedDataClass):
    load_query_args: lq.LoadQualifier = None
    source_loc_query_args: lq.LocationQualifier = None
    dest_loc_query_args: lq.LocationQualifier = None
    new_load: dcs.Load = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TransferRequest(dcs.BaseIdentifiedDataClass):
    criteria: TransferRequestCriteria
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
        if self.source_loc is not None and \
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
                self.source_loc.verify_removable(self.load.id)
        except:
            return False

        # is destination clear
        if self.dest_loc is None:
            pass
        elif len(self.dest_loc.get_addable_positions()) == 0:
            return False

        return True

    def __post_init__(self):
        if type(self.dest_loc) == dict:
            object.__setattr__(self, 'dest_loc', Location(**self.dest_loc))

        if type(self.source_loc) == dict:
            object.__setattr__(self, 'source_loc', Location(**self.source_loc))

        self.verify()

    def id(self):
        return self.id

    @classmethod
    def to_jsonable_dict(cls, obj: Self) -> Dict:
        return {
            'id': obj.get_id(),
            'criteria': asdict(obj.criteria),
            'load': asdict(obj.load),
            'source_loc': Location.to_jsonable_dict(obj.source_loc) if obj.source_loc else "",
            'dest_loc': Location.to_jsonable_dict(obj.dest_loc) if obj.dest_loc else ""
        }

    @classmethod
    def from_jsonable_dict(cls, obj: Dict) -> Self:
        return TransferRequest(
            criteria=TransferRequestCriteria(**obj['criteria']),
            load=dcs.Load(**obj['load']),
            source_loc=Location.from_jsonable_dict(obj['source_loc']),
            dest_loc=Location.from_jsonable_dict(obj['dest_loc'])
        )
