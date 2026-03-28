import logging
import pprint
import threading
import uuid

from cooptools.register import Register
from cooptools.reservation.reservationmanager import ReservationManager
import coopstorage.storage2.loc_load.dcs as dcs
import coopstorage.storage2.loc_load.exceptions as errs
from typing import Dict, Iterable, Callable, List, Type, Tuple
from cooptools.protocols import UniqueIdentifier
from coopstorage.storage2.loc_load.location import Location
import coopstorage.storage2.loc_load.qualifiers as qs
from coopstorage.storage2.loc_load.transferRequest import TransferRequestCriteria, TransferRequest
import cooptools.common as comm
from pprint import pprint
from coopstorage.storage2.loc_load import data as data
from cooptools.qualifiers import PatternMatchQualifier

logger = logging.getLogger(__name__)

RESERVATION_KEY = '006ddd91-73a5-4075-b49b-baa3077d5b4a'

class Storage:
    def __init__(self,
                 data_store: data.StorageDataStore = None,
                 loads: Iterable[dcs.Load] = None,
                 locs: Iterable[Location] = None,
                 id: UniqueIdentifier = None):

        self._lock = threading.RLock()
        self._data_store = data_store if data_store is not None else data.StorageDataStore()

        self._id = id or uuid.uuid4()
        self.register_locs(locs)
        self.register_loads(loads)

    @staticmethod
    def from_meta(location_type_counts: Iterable[Tuple[dcs.LocationMeta, int]],
                  naming_provider: Callable[[int], str],
                  data_store: data.StorageDataStore = None,
                  id: UniqueIdentifier = None
                  ):
        locations = []
        for meta, count in location_type_counts:
            locations += [Location(
                id=naming_provider(x),
                location_meta=meta,
                coords=(1, 1, 1)
            ) for x in range(count)]

        return Storage(
            data_store=data_store,
            locs=locations,
            id=id
        )


    def _verify_load(self, id: UniqueIdentifier):
        if not id in self._data_store.LoadsData.get():
            raise errs.UnknownLoadIdException(id)

    def _verify_loc(self, id: UniqueIdentifier):
        if id not in self._data_store.LocationsData.get():
            raise errs.UnknownLocationIdException(id)

    def register_locs(self, locs: Iterable[Location]=None):
        with self._lock:
            if locs is not None:
                self._data_store.LocationsData.add(locs)
        return self

    def get_locs(self,
                 criteria: qs.LocationQualifier=None) -> Dict[UniqueIdentifier, Location]:
        with self._lock:
            return self._data_store.LocationsData.get(
                criteria,
                load_provider=self._data_store.LoadsData.get
            )

    def register_loads(self, loads: Iterable[dcs.Load]=None):
        with self._lock:
            if loads is not None:
                self._data_store.LoadsData.add(loads)
        return self

    def get_loads(self,
                  criteria: qs.LoadQualifier=None)->Dict[UniqueIdentifier, dcs.Load]:
        with self._lock:
            return self._data_store.LoadsData.get(qualifier=criteria)


    def filter(self,
               filter: qs.LocationQualifier=None) -> List[Location]:
        if filter is None:
            return list(self._data_store.LocationsData.get().values())

        load_provider = self._data_store.LoadsData.get
        return [
            loc for loc in self._data_store.LocationsData.get().values()
            if filter.check_if_qualifies(loc, load_provider=load_provider)
        ]


    def evaluate(self,
                 options: Iterable[Location],
                 evaluator: Callable[[Location], float]) -> Dict[Location, float]:
        return {
            x: evaluator(x) for x in options
        }

    def select_location(self,
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
            source = self.select_location(criteria.source_loc_query_args)

        dest = None
        if criteria.dest_loc_query_args is not None:
            dest = self.select_location(criteria.dest_loc_query_args)
        elif criteria.new_load is not None and \
            criteria.dest_loc_query_args is None:
            dest = self.select_location()


        load = None
        if criteria.load_query_args is not None and source is not None:
            load = self.select_load(loc=source,
                                    filter=criteria.load_query_args)
        elif criteria.load_query_args is None and \
            criteria.new_load is not None:
            load = criteria.new_load
        elif criteria.load_query_args is not None and source is None:
            load = comm.filter(self._data_store.LoadsData.get().values(),
                               criteria.load_query_args.check_if_qualifies)[0]
            source = self.select_location(filter=qs.LocationQualifier(
                all_loads=[criteria.load_query_args]
            ))
        elif source is not None:
            load = source.get_removable_load_ids()[0]

        return TransferRequest(
            criteria=criteria,
            load=load,
            source_loc=source,
            dest_loc=dest
        )

    def select_load(self,
                    loc: Location,
                    filter: qs.LoadQualifier):
        loads = list(self._data_store.LoadsData.get(ids=loc.LoadIds).values())
        ret = comm.filter(loads, qualifier=filter.check_if_qualifies)
        return ret[0]


    def _handle_transfer_request(self,
                                 transfer_request: TransferRequest):
        source_txt = ""
        if transfer_request.source_loc is not None:
            self._data_store.LocationsData.update([self._data_store.LocationsData.get(ids=[transfer_request.source_loc.get_id()])[transfer_request.source_loc.get_id()]
                                                  .remove_loads(load_ids=[transfer_request.load.id])]
                                                  )
            source_txt = f" from {transfer_request.source_loc.Id}"

        dest_txt = ""
        if transfer_request.dest_loc is not None:
            self._data_store.LocationsData.update([self._data_store.LocationsData.get(ids=[transfer_request.dest_loc.get_id()])[transfer_request.dest_loc.get_id()].store_loads(
                load_ids=[transfer_request.load.id]
            )])
            dest_txt = f" to {transfer_request.dest_loc.Id}"

        logger.info(f"Load {transfer_request.load.id} transferred{source_txt}{dest_txt}")

    def handle_transfer_requests(self, transfer_request_criteria: Iterable[TransferRequestCriteria]):
        with self._lock:
            for criteria in transfer_request_criteria:
                request = self.resolve_transfer_request_criteria(
                    criteria=criteria
                )
                self._data_store.TransferRequestsData.add([request])
                self._data_store.LoadsData.add_or_update(loads=[request.load])

                if request.Ready:
                    self._handle_transfer_request(request)
                    self._data_store.TransferRequestsData.remove(requests=[request])
                else:
                    logger.error(f"{pprint.pformat(request)}")
                    raise NotImplementedError()

    @property
    def Loads(self) -> List[dcs.Load]:
        return list(self._data_store.LoadsData.get().values())

    @property
    def LoadLocs(self) -> Dict[dcs.Load, Location]:
        ret = {}
        loc_map = self._data_store.LocationsData.get()
        load_map = self._data_store.LoadsData.get()
        for id, loc in loc_map.items():
            for load_id in loc.LoadIds:
                ret[load_map[load_id]] = loc

        return ret

    @property
    def LocLoads(self) -> Dict[Location, List[dcs.Load]]:
        ret = {}
        for id, loc in self._data_store.LocationsData.get().items():
            ret[loc] = list(self._data_store.LoadsData.get(ids=loc.LoadIds).values())

        return ret

    @property
    def Locations(self) -> List[Location]:
        return self._data_store.LocationsData.get()

    def summary(self) -> Dict[UniqueIdentifier, List[UniqueIdentifier]]:
        try:
            return {k.Id: [ld.id for ld in v] for k, v in self.LocLoads.items()}
        except Exception as e:
            print(e)
            raise e
    def __repr__(self):
        return f"{self._id}: {self.summary()}"

if __name__ == "__main__":
    from cooptools.common import LETTERS
    from cooptools.randoms import a_string
    import coopstorage.storage2.loc_load.channel_processors as cps
    from coopstorage.storage2mongo import TEST_DATA
    logging.basicConfig(level=logging.INFO)
    from coopstorage.storage2.loc_load.data import MongoCollectionDataStore

    def init_a_storage(

    ):
        return Storage(
            data_store=data.StorageDataStore(),
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
        s = Storage.from_meta(
            location_type_counts=[(dcs.LocationMeta(
                             dims=(10, 10, 10),
                             channel_processor=cps.FIFOFlowChannelProcessor(),
                             capacity=3
                         ), 10)],
            naming_provider=lambda x: LETTERS[x],
            data_store=data.StorageDataStore(),

        )

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
                        id_pattern=PatternMatchQualifier(
                            regex='(g|e)'
                        )
                    )
                ),
                TransferRequestCriteria(
                    load_query_args=qs.LoadQualifier(
                      pattern=PatternMatchQualifier(
                          id=1
                      )
                    )
                )
            ]
        )

        pprint(s.Loads)
        pprint(s.LocLoads)

    def test_002():
        TEST_DATA.clear()

        s = Storage.from_meta(
            location_type_counts=[(dcs.LocationMeta(
                dims=(10, 10, 10),
                channel_processor=cps.FIFOFlowChannelProcessor(),
                capacity=3
            ), 100)],
            naming_provider=lambda x: a_string(k=7),
            data_store=TEST_DATA,
        )



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
                        id_pattern=PatternMatchQualifier(
                            regex='^b'
                        )
                    )
                ),
                TransferRequestCriteria(
                    load_query_args=qs.LoadQualifier(
                      pattern=PatternMatchQualifier(
                          id=1
                      )
                    )
                )
            ]
        )




    # test_001()
    test_002()


