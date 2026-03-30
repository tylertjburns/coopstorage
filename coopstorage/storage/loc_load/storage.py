import logging
import pprint
import threading
import uuid

from cooptools.register import Register
from cooptools.reservation.reservationmanager import ReservationManager
import coopstorage.storage.loc_load.dcs as dcs
import coopstorage.storage.loc_load.exceptions as errs
import coopstorage.storage.loc_load.container_state_mutations as csm
from typing import Dict, Iterable, Callable, List, Type, Tuple
from cooptools.protocols import UniqueIdentifier
from coopstorage.storage.loc_load.location import Location
import coopstorage.storage.loc_load.qualifiers as qs
from coopstorage.storage.loc_load.transferRequest import TransferRequestCriteria, TransferRequest
import cooptools.common as comm
from coopstorage.storage.loc_load import data as data
from cooptools.qualifiers import PatternMatchQualifier

logger = logging.getLogger(__name__)

RESERVATION_KEY = '006ddd91-73a5-4075-b49b-baa3077d5b4a'

class Storage:
    def __init__(self,
                 data_store: data.StorageDataStore = None,
                 containers: Iterable[dcs.Container] = None,
                 locs: Iterable[Location] = None,
                 id: UniqueIdentifier = None):

        self._lock = threading.RLock()
        self._data_store = data_store if data_store is not None else data.StorageDataStore()

        self._id = id or uuid.uuid4()
        self.register_locs(locs)
        self.register_containers(containers)

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


    def _verify_container(self, id: UniqueIdentifier):
        if not id in self._data_store.ContainersData.get():
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
                container_provider=self._data_store.ContainersData.get
            )

    def register_containers(self, containers: Iterable[dcs.Container]=None):
        with self._lock:
            if containers is not None:
                self._data_store.ContainersData.add(containers)
        return self

    def get_containers(self,
                  criteria: qs.ContainerQualifier=None)->Dict[UniqueIdentifier, dcs.Container]:
        with self._lock:
            return self._data_store.ContainersData.get(qualifier=criteria)

    def add_content_to_container_at_location(self,
                                             loc_id: UniqueIdentifier,
                                             contents: List[dcs.ContainerContent]):
        with self._lock:
            self._verify_loc(loc_id)
            loc = self._data_store.LocationsData.get(ids=[loc_id])[loc_id]
            container_ids = loc.ContainerIds
            if len(container_ids) != 1:
                raise errs.UnexpectedContainerCountException(loc_id, expected=1, actual=len(container_ids))
            container_id = list(container_ids)[0]
            container = self._data_store.ContainersData.get(ids=[container_id])[container_id]
            updated = csm.add_content_to_container(container, contents)
            self._data_store.ContainersData.add_or_update([updated])

    def remove_content_from_container_at_location(self,
                                                  loc_id: UniqueIdentifier,
                                                  content: dcs.ContainerContent):
        with self._lock:
            self._verify_loc(loc_id)
            loc = self._data_store.LocationsData.get(ids=[loc_id])[loc_id]
            container_ids = loc.ContainerIds
            if len(container_ids) != 1:
                raise errs.UnexpectedContainerCountException(loc_id, expected=1, actual=len(container_ids))
            container_id = list(container_ids)[0]
            container = self._data_store.ContainersData.get(ids=[container_id])[container_id]
            updated = csm.remove_content_from_container(container, content)
            self._data_store.ContainersData.add_or_update([updated])


    def filter(self,
               filter: qs.LocationQualifier=None) -> List[Location]:
        if filter is None:
            return list(self._data_store.LocationsData.get().values())

        container_provider = self._data_store.ContainersData.get
        return [
            loc for loc in self._data_store.LocationsData.get().values()
            if filter.check_if_qualifies(loc, container_provider=container_provider)
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

        # short-circuit when all scores are equal — skip O(n log n) sort
        score_values = list(scores.values())
        if len(score_values) == 1 or all(v == score_values[0] for v in score_values):
            return options[0]

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
        elif criteria.new_container is not None and \
            criteria.dest_loc_query_args is None:
            dest = self.select_location()


        container = None
        if criteria.container_query_args is not None and source is not None:
            container = self.select_container(loc=source,
                                    filter=criteria.container_query_args)
        elif criteria.container_query_args is None and \
            criteria.new_container is not None:
            container = criteria.new_container
        elif criteria.container_query_args is not None and source is None:
            container = comm.filter(self._data_store.ContainersData.get().values(),
                               criteria.container_query_args.check_if_qualifies)[0]
            source = self.select_location(filter=qs.LocationQualifier(
                all_containers=[criteria.container_query_args]
            ))
        elif source is not None:
            container_id = list(source.get_removable_container_ids().values())[0]
            container = self._data_store.ContainersData.get(ids=[container_id])[container_id]

        return TransferRequest(
            criteria=criteria,
            container=container,
            source_loc=source,
            dest_loc=dest
        )

    def select_container(self,
                    loc: Location,
                    filter: qs.ContainerQualifier):
        containers = list(self._data_store.ContainersData.get(ids=loc.ContainerIds).values())
        ret = comm.filter(containers, qualifier=filter.check_if_qualifies)
        return ret[0]


    def _handle_transfer_request(self,
                                 transfer_request: TransferRequest):
        source_txt = ""
        if transfer_request.source_loc is not None:
            self._data_store.LocationsData.update([self._data_store.LocationsData.get(ids=[transfer_request.source_loc.get_id()])[transfer_request.source_loc.get_id()]
                                                  .remove_containers(container_ids=[transfer_request.container.id])]
                                                  )
            source_txt = f" from {transfer_request.source_loc.Id}"

        dest_txt = ""
        if transfer_request.dest_loc is not None:
            self._data_store.LocationsData.update([self._data_store.LocationsData.get(ids=[transfer_request.dest_loc.get_id()])[transfer_request.dest_loc.get_id()].store_containers(
                container_ids=[transfer_request.container.id]
            )])
            dest_txt = f" to {transfer_request.dest_loc.Id}"

        logger.info(f"Container {transfer_request.container.id} transferred{source_txt}{dest_txt}")

    def handle_transfer_requests(self, transfer_request_criteria: Iterable[TransferRequestCriteria]):
        with self._lock:
            for criteria in transfer_request_criteria:
                request = self.resolve_transfer_request_criteria(
                    criteria=criteria
                )
                self._data_store.TransferRequestsData.add([request])
                self._data_store.ContainersData.add_or_update(containers=[request.container])

                if request.Ready:
                    self._handle_transfer_request(request)
                    self._data_store.TransferRequestsData.remove(requests=[request])
                else:
                    logger.error(f"{pprint.pformat(request)}")
                    raise NotImplementedError()

    @property
    def Containers(self) -> List[dcs.Container]:
        return list(self._data_store.ContainersData.get().values())

    @property
    def ContainerLocs(self) -> Dict[dcs.Container, Location]:
        ret = {}
        loc_map = self._data_store.LocationsData.get()
        container_map = self._data_store.ContainersData.get()
        for _, loc in loc_map.items():
            for container_id in loc.ContainerIds:
                ret[container_map[container_id]] = loc

        return ret

    @property
    def LocContainers(self) -> Dict[Location, List[dcs.Container]]:
        ret = {}
        for id, loc in self._data_store.LocationsData.get().items():
            ret[loc] = list(self._data_store.ContainersData.get(ids=loc.ContainerIds).values())

        return ret

    @property
    def Locations(self) -> List[Location]:
        return self._data_store.LocationsData.get()

    @property
    def OccupiedLocs(self) -> List[Location]:
        """Locations that have at least one container stored."""
        return [loc for loc in self._data_store.LocationsData.get().values() if len(loc.ContainerIds) > 0]

    @property
    def EmptyLocs(self) -> List[Location]:
        """Locations with no containers stored."""
        return [loc for loc in self._data_store.LocationsData.get().values() if len(loc.ContainerIds) == 0]

    def content_at_location(self, loc_id: UniqueIdentifier) -> List[dcs.ContainerContent]:
        """All ContainerContent across every container at a location, aggregated by (resource, uom)."""
        from coopstorage.storage.loc_load.container_state_mutations import _merge_contents
        self._verify_loc(loc_id)
        loc = self._data_store.LocationsData.get(ids=[loc_id])[loc_id]
        all_contents = [
            c
            for container in self._data_store.ContainersData.get(ids=loc.ContainerIds).values()
            for c in container.contents
        ]
        return list(_merge_contents(all_contents))

    @property
    def InventoryByResourceUom(self) -> Dict[Tuple[dcs.Resource, dcs.UnitOfMeasure], float]:
        """Total qty of every (Resource, UoM) pair across all containers in storage."""
        ret: Dict[Tuple[dcs.Resource, dcs.UnitOfMeasure], float] = {}
        for container in self._data_store.ContainersData.get().values():
            for c in container.contents:
                key = (c.resource, c.uom)
                ret[key] = ret.get(key, 0.0) + c.qty
        return ret

    def summary(self) -> Dict[UniqueIdentifier, List[UniqueIdentifier]]:
        try:
            return {k.Id: [ld.id for ld in v] for k, v in self.LocContainers.items()}
        except Exception as e:
            print(e)
            raise e
    def __repr__(self):
        return f"{self._id}: {self.summary()}"

if __name__ == "__main__":
    from cooptools.common import LETTERS
    from cooptools.randoms import a_string
    import coopstorage.storage.loc_load.channel_processors as cps
    from coopstorage.storagemongo import TEST_DATA
    logging.basicConfig(level=logging.INFO)
    from coopstorage.storage.loc_load.data import MongoCollectionDataStore

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
                    new_container=dcs.Container(id=1),
                    dest_loc_query_args=qs.LocationQualifier(
                        at_least_capacity=1
                    )
                ),
                TransferRequestCriteria(
                    new_container=dcs.Container(id=2),
                    dest_loc_query_args=qs.LocationQualifier(
                        at_least_capacity=1
                    )
                ),
                TransferRequestCriteria(
                    new_container=dcs.Container(id=3),
                    dest_loc_query_args=qs.LocationQualifier(
                        at_least_capacity=2
                    )
                ),
                TransferRequestCriteria(
                    new_container=dcs.Container(id=4),
                    dest_loc_query_args=qs.LocationQualifier(
                        at_least_capacity=2,
                        id_pattern=PatternMatchQualifier(
                            regex='(g|e)'
                        )
                    )
                ),
                TransferRequestCriteria(
                    container_query_args=qs.ContainerQualifier(
                      pattern=PatternMatchQualifier(
                          id=1
                      )
                    )
                )
            ]
        )

        pprint(s.Containers)
        pprint(s.LocContainers)

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
                    new_container=dcs.Container(id=1),
                    dest_loc_query_args=qs.LocationQualifier(
                        at_least_capacity=1
                    )
                ),
                TransferRequestCriteria(
                    new_container=dcs.Container(id=2),
                    dest_loc_query_args=qs.LocationQualifier(
                        at_least_capacity=1
                    )
                ),
                TransferRequestCriteria(
                    new_container=dcs.Container(id=3),
                    dest_loc_query_args=qs.LocationQualifier(
                        at_least_capacity=2
                    )
                ),
                TransferRequestCriteria(
                    new_container=dcs.Container(id=4),
                    dest_loc_query_args=qs.LocationQualifier(
                        at_least_capacity=2,
                        id_pattern=PatternMatchQualifier(
                            regex='^b'
                        )
                    )
                ),
                TransferRequestCriteria(
                    container_query_args=qs.ContainerQualifier(
                      pattern=PatternMatchQualifier(
                          id=1
                      )
                    )
                )
            ]
        )




    # test_001()
    test_002()


