import logging
import uuid

from cooptools.register import Register
from cooptools.reservation.reservationmanager import ReservationManager
import coopstorage.storage2.loc_load.dcs as dcs
import coopstorage.storage2.loc_load.exceptions as errs
from typing import Dict, Iterable, Callable, List, TypeVar
from cooptools.common import UniqueIdentifier
from coopstorage.storage2.loc_load.location import Location
import coopstorage.storage2.loc_load.qualifiers as qs
from coopstorage.storage2.loc_load.transferRequest import TransferRequestCriteria, TransferRequest
import cooptools.common as comm

RESERVATION_KEY = '006ddd91-73a5-4075-b49b-baa3077d5b4a'

class Storage:
    def __init__(self,
                 loads: Iterable[dcs.Load] = None,
                 locs: Iterable[Location] = None,
                 id: UniqueIdentifier = None):
        self._loads: Register[dcs.Load] = Register()
        self._locs: Register[Location] = Register()
        self._reservation = ReservationManager()
        self._open_transfer_requests: Register[TransferRequestCriteria] = Register()

        self._id = id or uuid.uuid4()
        self.register_locs(locs)
        self.register_loads(loads)

    def _verify_load(self, id: UniqueIdentifier):
        if not id in self._loads.Registry.keys():
            raise errs.UnknownLoadIdException(id)

    def _verify_loc(self, id: UniqueIdentifier):
        if id not in self._locs.Registry.keys():
            raise errs.UnknownLocationIdException(id)

    def register_locs(self, locs: Iterable[Location]=None):
        if locs is not None:
            self._locs.register(locs, [x.Id for x in locs])
        return self

    def register_loads(self, loads: Iterable[dcs.Load]=None):
        if loads is not None:
            self._locs.register(loads, [x.id for x in loads])
        return self

    def filter(self,
               filter: qs.LocationQualifier=None) -> List[Location]:
        if filter is None:
            return list(self._locs.Registry.values())

        # Filter based on location criteria
        ret = comm.filter(self._locs.Registry.values(),
                          qualifier=filter.check_if_qualifies)

        return ret


    def evaluate(self,
                 options: Iterable[Location],
                 evaluator: Callable[[Location], float]) -> Dict[Location, float]:
        return {
            x: evaluator(x) for x in options
        }

    def select(self,
               filter: qs.LocationQualifier = None,
               evaluator: Callable[[Location], float] = lambda x: 1):
        # Get filtered options
        options = self.filter(
            filter=filter
        )

        # raise if no options were found
        if len(options) == 0:
            raise errs.NoLocationsMatchFilterCriteriaException(filter)

        # score the options
        scores = self.evaluate(options, evaluator)
        ordered = sorted([(k, v) for k, v in scores.items()],
                         key=lambda tup: tup[1], reverse=True)

        # return the first one
        return ordered[0][0]

    def resolve_transfer_request_criteria(
            self,
            criteria: TransferRequestCriteria
    ) -> TransferRequest:
        source = None
        if criteria.source_loc_query_args is not None:
            source = self.select(criteria.source_loc_query_args)

        dest = None
        if criteria.dest_loc_query_args is not None:
            dest = self.select(criteria.dest_loc_query_args)
        elif criteria.new_load is not None and \
            criteria.dest_loc_query_args is None:
            dest = self.select()


        load = None
        if criteria.load_query_args is not None and source is not None:
            load = self.select_load(loc=source,
                                    filter=criteria.load_query_args)
        elif criteria.load_query_args is None and \
            criteria.new_load is not None:
            self._loads.register(to_register=[criteria.new_load],
                                 ids=[criteria.new_load.id])
            load = criteria.new_load
        elif criteria.load_query_args is not None:
            load = comm.filter(self._loads.Registry.values(),
                               criteria.load_query_args.check_if_qualifies)
        elif source is not None:
            load = source.get_removable_loads()[0]

        return TransferRequest(
            load=load,
            source_loc=source,
            dest_loc=dest
        )

    def select_load(self,
                    loc: Location,
                    filter: qs.LoadQualifier):
        ret = comm.filter(loc.LoadIds,
                          qualifier=filter)
        return ret[0]


    def handle_transfer_requests(self, transfer_request_criteria: Iterable[TransferRequestCriteria]):
        self._open_transfer_requests.register(to_register=transfer_request_criteria,
                                              ids=[x.id for x in transfer_request_criteria])

        for criteria in transfer_request_criteria:
            request = self.resolve_transfer_request_criteria(
                criteria=criteria
            )

            if request.Ready:
                request.handle()
            else:
                from pprint import pprint
                pprint(request)
                raise NotImplementedError()

    @property
    def Loads(self) -> List[dcs.Load]:
        return list(self._loads.Registry.values())

    @property
    def LoadLocs(self) -> Dict[dcs.Load, Location]:
        ret = {}
        for id, loc in self._locs.Registry.items():
            for load_id in loc.LoadIds:
                ret[self._loads.Registry[load_id]] = loc

        return ret

    @property
    def LocLoads(self) -> Dict[Location, List[dcs.Load]]:
        ret = {}
        for id, loc in self._locs.Registry.items():
            ret[loc] = self._loads.get_by_id(loc.LoadIds)

        return ret

    def summary(self) -> Dict[UniqueIdentifier, List[UniqueIdentifier]]:
        return {k.Id: [ld.id for ld in v] for k, v in self.LocLoads.items()}
    def __repr__(self):
        return f"{self._id}: {self.summary()}"

if __name__ == "__main__":
    from cooptools.common import LETTERS
    import coopstorage.storage2.loc_load.channel_processors as cps
    import cooptools.geometry_utils.vector_utils as vec
    logging.basicConfig(level=logging.INFO)
    import coopstorage.storage2.loc_load.qualifiers as qs

    def init_a_storage():
        return Storage(
            locs=[
                Location(id=LETTERS[ii],
                         location_meta=dcs.LocationMeta(
                             dims=(10, 10, 10),
                             channel_processor=cps.FIFOFlowChannelProcessor(),
                             capacity=3
                         ),
                         coords=(100, 200, 300)
                         ) for ii in range(10)],
        )

    def test_001():
        s = init_a_storage()

        s.handle_transfer_requests(
            transfer_request_criteria=[
                TransferRequestCriteria(
                    new_load=dcs.Load(id=1),
                    dest_loc_query_args=qs.LocationQualifier(
                        at_least_capacity=1
                    )
                ),
                TransferRequestCriteria(
                    new_load=dcs.Load(id=2),
                    dest_loc_query_args=qs.LocationQualifier(
                        at_least_capacity=1
                    )
                ),
                TransferRequestCriteria(
                    new_load=dcs.Load(id=3),
                    dest_loc_query_args=qs.LocationQualifier(
                        at_least_capacity=2
                    )
                ),
                TransferRequestCriteria(
                    new_load=dcs.Load(id=4),
                    dest_loc_query_args=qs.LocationQualifier(
                        at_least_capacity=2,
                        pattern=dcs.PatternMatchQuery(
                            regex='(g|e)'
                        )
                    )
                )
            ]
        )


        print(s)
    test_001()


