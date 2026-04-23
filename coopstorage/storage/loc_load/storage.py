import logging
import pprint
import threading
import uuid
from dataclasses import replace

from cooptools.register import Register
from cooptools.reservation.reservationmanager import ReservationManager
import coopstorage.storage.loc_load.dcs as dcs
import coopstorage.storage.loc_load.exceptions as errs
import coopstorage.storage.loc_load.container_state_mutations as csm
import coopstorage.storage.loc_load.evaluators as evaluators
from typing import Dict, Iterable, Callable, List, Optional, Type, Tuple
from cooptools.protocols import UniqueIdentifier
from coopstorage.storage.loc_load.location import Location
import coopstorage.storage.loc_load.qualifiers as qs
from coopstorage.storage.loc_load.transferRequest import TransferRequestCriteria, TransferRequest
from coopstorage.storage.loc_load.reservation_provider import ReservationProvider, PassthroughReservationProvider, ReservationFailedError, RateLimitedError
import cooptools.common as comm
from coopstorage.storage.loc_load import data as data
from cooptools.qualifiers import PatternMatchQualifier, WhiteBlackListQualifier

from pubsub import pub
from coopstorage.enums import StorageTopic

logger = logging.getLogger(__name__)


def _build_transfer_payload(transfer_request: 'TransferRequest',
                            updated_source_loc=None,
                            updated_dest_loc=None) -> dict:
    payload = {
        'container_id':  str(transfer_request.container.id),
        'container_uom': transfer_request.container.uom.name,
        'from_loc_id': None,
        'to_loc_id':   None,
    }
    if updated_source_loc is not None:
        payload.update({
            'from_loc_id': str(updated_source_loc.Id),
            'from_slots':  updated_source_loc.Slots,
            **{f'from_{k}': v for k, v in updated_source_loc.channel_access_state().items()},
        })
    if updated_dest_loc is not None:
        payload.update({
            'to_loc_id': str(updated_dest_loc.Id),
            'to_slots':  updated_dest_loc.Slots,
            **{f'to_{k}': v for k, v in updated_dest_loc.channel_access_state().items()},
        })
    return payload

class Storage:
    def __init__(self,
                 data_store: data.StorageDataStore = None,
                 containers: Iterable[dcs.Container] = None,
                 locs: Iterable[Location] = None,
                 id: UniqueIdentifier = None,
                 location_map_tree=None,
                 reservation_provider: ReservationProvider = None):

        self._lock = threading.RLock()
        self._reservation_provider = reservation_provider or PassthroughReservationProvider()
        self._data_store = data_store if data_store is not None else data.StorageDataStore()

        self._id = id or uuid.uuid4()
        from coopstorage.location_map_tree import LocationMapTree
        self._location_map_tree = location_map_tree if location_map_tree is not None else LocationMapTree()
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
                for loc in locs:
                    try:
                        tree_path = self._location_map_tree.get_path(loc.Id)
                    except (KeyError, AttributeError):
                        tree_path = None
                    pub.sendMessage(StorageTopic.LOCATION_REGISTERED.value, payload={
                        'id': str(loc.Id),
                        'coords': list(loc.Coords),
                        'meta': {
                            'dims': list(loc.Meta.dims),
                            'channel_processor': type(loc.Meta.channel_processor).__name__,
                            'capacity': loc.Capacity,
                            'channel_axis': loc.Meta.channel_axis,
                            'delete_on_receive': loc.Meta.delete_on_receive,
                        },
                        'slot_dims':    list(loc.SlotDims),
                        'slot_offsets': [list(o) for o in loc.SlotOffsets],
                        'slots': loc.Slots,
                        **loc.channel_access_state(),
                        'containers': {},
                        'tree_path': tree_path,
                    })
        return self

    def get_locs(self,
                 criteria: qs.LocationQualifier=None) -> Dict[UniqueIdentifier, Location]:
        with self._lock:
            if criteria is not None and criteria.reserved is not None:
                _reserved_loc_ids = self.get_reserved_location_ids()
                is_reserved = lambda loc_id: str(loc_id) in _reserved_loc_ids
            else:
                is_reserved = None

            _needs_ctr = (criteria is not None and
                          (criteria.has_any_containers is not None or criteria.has_all_containers is not None))
            if _needs_ctr:
                _reserved_ctr_ids = self.get_reserved_container_ids()
                is_container_reserved = lambda cid: str(cid) in _reserved_ctr_ids
            else:
                is_container_reserved = None

            return self._data_store.LocationsData.get(
                criteria,
                container_provider=self._data_store.ContainersData.get,
                is_reserved=is_reserved,
                is_container_reserved=is_container_reserved,
            )

    def register_containers(self, containers: Iterable[dcs.Container]=None):
        with self._lock:
            if containers is not None:
                self._data_store.ContainersData.add(containers)
                for c in containers:
                    pub.sendMessage(StorageTopic.CONTAINER_REGISTERED.value, payload={
                        'id': str(c.id),
                        'uom': c.uom.name,
                        'contents': [
                            {'resource': cc.resource.name, 'uom': cc.uom.name, 'qty': cc.qty}
                            for cc in c.contents
                        ]
                    })
        return self

    def get_containers(self,
                  criteria: qs.ContainerQualifier=None)->Dict[UniqueIdentifier, dcs.Container]:
        with self._lock:
            if criteria is not None and criteria.reserved is not None:
                _reserved_ctr_ids = self.get_reserved_container_ids()
                is_reserved = lambda cid: str(cid) in _reserved_ctr_ids
            else:
                is_reserved = None
            return self._data_store.ContainersData.get(qualifier=criteria, is_reserved=is_reserved)

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
            pub.sendMessage(StorageTopic.CONTENT_CHANGED.value, payload={
                'container_id': str(container_id),
                'loc_id': str(loc_id),
                'contents': [
                    {'resource': cc.resource.name, 'uom': cc.uom.name, 'qty': cc.qty}
                    for cc in updated.contents
                ]
            })

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
            pub.sendMessage(StorageTopic.CONTENT_CHANGED.value, payload={
                'container_id': str(container_id),
                'loc_id': str(loc_id),
                'contents': [
                    {'resource': cc.resource.name, 'uom': cc.uom.name, 'qty': cc.qty}
                    for cc in updated.contents
                ]
            })


    def filter(self,
               filter: qs.LocationQualifier = None,
               container: dcs.Container = None) -> List[Location]:
        if filter is None and container is None:
            return list(self._data_store.LocationsData.iter_values())

        if filter is not None and filter.reserved is not None:
            _reserved_loc_ids = self.get_reserved_location_ids()
            is_reserved = lambda loc_id: str(loc_id) in _reserved_loc_ids
        else:
            is_reserved = None

        _needs_ctr = (filter is not None and
                      (filter.has_any_containers is not None or filter.has_all_containers is not None))
        if _needs_ctr:
            _reserved_ctr_ids = self.get_reserved_container_ids()
            is_container_reserved = lambda cid: str(cid) in _reserved_ctr_ids
        else:
            is_container_reserved = None

        container_provider = self._data_store.ContainersData.get
        return [
            loc for loc in self._data_store.LocationsData.iter_values()
            if filter is None or filter.check_if_qualifies(
                loc, container_provider=container_provider, container=container,
                is_reserved=is_reserved, is_container_reserved=is_container_reserved)
        ]


    def evaluate(self,
                 options: Iterable[Location],
                 evaluator: Callable[[Location], float]) -> Dict[Location, float]:
        return {
            x: evaluator(x) for x in options
        }

    def select_location(self,
                        filter: qs.LocationQualifier = None,
                        evaluator: Callable[[Location], float] = None,
                        container: dcs.Container = None):
        # Fast path: no custom evaluator — return the first qualifying location immediately
        if evaluator is None:
            if filter is not None and filter.reserved is not None:
                _reserved_loc_ids = self.get_reserved_location_ids()
                is_reserved = lambda loc_id: str(loc_id) in _reserved_loc_ids
            else:
                is_reserved = None

            _needs_ctr = (filter is not None and
                          (filter.has_any_containers is not None or filter.has_all_containers is not None))
            if _needs_ctr:
                _reserved_ctr_ids = self.get_reserved_container_ids()
                is_container_reserved = lambda cid: str(cid) in _reserved_ctr_ids
            else:
                is_container_reserved = None

            container_provider = self._data_store.ContainersData.get
            for loc in self._data_store.LocationsData.iter_values():
                if filter is None or filter.check_if_qualifies(
                        loc, container_provider=container_provider, container=container,
                        is_reserved=is_reserved, is_container_reserved=is_container_reserved):
                    return loc
            raise errs.NoLocationsMatchFilterCriteriaException(filter)

        # Scored path: collect all options, evaluate, and sort
        options = self.filter(filter=filter, container=container)
        if len(options) == 0:
            raise errs.NoLocationsMatchFilterCriteriaException(filter)
        scores = self.evaluate(options, evaluator)
        ordered = sorted([(k, v) for k, v in scores.items()],
                         key=lambda tup: tup[1], reverse=True)
        return ordered[0][0]

    def resolve_transfer_request_criteria(
            self,
            criteria: TransferRequestCriteria,
            dest_loc_evaluator: Callable[[Location], float] = None,
            container_evaluator: Callable[[dcs.Container], float] = None
    ) -> TransferRequest:
        # ── Source & Container (peer resolvers) ───────────────────────────────
        # Either defines the other; if both supplied, validate consistency.
        source = None
        container = None

        if criteria.source_loc_query_args is not None and criteria.container_query_args is not None:
            # Both explicit: find source first, then validate container exists there
            source = self.select_location(criteria.source_loc_query_args)
            container = self.select_container(loc=source, filter=criteria.container_query_args)

        elif criteria.source_loc_query_args is not None:
            # Source only: infer container from whichever is removable at that location
            source = self.select_location(criteria.source_loc_query_args)
            container_id = list(source.get_removable_container_ids().values())[0]
            container = self._data_store.ContainersData.get(ids=[container_id])[container_id]

        elif criteria.container_query_args is not None:
            # Container only: find a location that has a qualifying container, then
            # select the container from that location. This ensures the container and
            # source are always consistent (avoids picking a container at L1 but
            # a source at L2 when the qualifier matches multiple containers).
            source = self.select_location(filter=qs.LocationQualifier(
                has_any_containers=[criteria.container_query_args]
            ),
                evaluator=container_evaluator or evaluators.random_score
            )
            container = self.select_container(loc=source, filter=criteria.container_query_args)

        elif criteria.new_container is not None:
            # New container arriving — no source
            container = criteria.new_container

        # ── Dest (resolved after container is known; slot fit enforced) ───────
        dest = None
        if criteria.dest_loc_query_args is not None:
            dest = self.select_location(criteria.dest_loc_query_args, evaluator=dest_loc_evaluator, container=container)
        elif criteria.new_container is not None and criteria.dest_loc_query_args is None:
            dest = self.select_location(evaluator=dest_loc_evaluator, container=container)

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
        if filter.reserved is not None:
            _reserved_ctr_ids = self.get_reserved_container_ids()
            is_reserved = lambda cid: str(cid) in _reserved_ctr_ids
        else:
            is_reserved = None
        ret = comm.filter(containers, qualifier=lambda c: filter.check_if_qualifies(c, is_reserved=is_reserved))
        return ret[0]


    def _unblock(self,
                 container: dcs.Container,
                 source_loc: Location,
                 unblock_dest_evaluator: Callable[[Location], float],
                 _unblocking_ids: set) -> None:
        """Move any containers that block *container* from being removed at *source_loc*.

        Raises UnblockDeadlockError if a circular blocking chain is detected.
        """
        state = [source_loc.ContainerPositions.get(i) for i in range(source_loc.Capacity)]
        cp = source_loc.Meta.channel_processor
        blockers = cp.get_blocking_loads(container.id, state)

        for blocker_id in blockers:
            if str(blocker_id) in _unblocking_ids:
                raise errs.UnblockDeadlockError(container.id, blocker_id, _unblocking_ids)
            _unblocking_ids.add(str(blocker_id))
            self.handle_transfer_requests(
                [TransferRequestCriteria(
                    container_query_args=qs.ContainerQualifier(
                        pattern=PatternMatchQualifier(id=blocker_id)
                    ),
                    dest_loc_query_args=qs.LocationQualifier(
                        at_least_capacity=1,
                        has_addable_position=True,
                        id_pattern=PatternMatchQualifier(
                            white_list_black_list_qualifier=WhiteBlackListQualifier(
                                black_list=[str(source_loc.Id)]
                            )
                        ),
                        reserved=False,
                    ),
                )],
                dest_loc_evaluator=unblock_dest_evaluator,
                _unblocking_ids=_unblocking_ids,
            )

    def _handle_transfer_request(self, transfer_request: TransferRequest):
        updated_src = None
        source_txt = ""
        if transfer_request.source_loc is not None:
            src_id = transfer_request.source_loc.get_id()
            updated_src = (self._data_store.LocationsData.get(ids=[src_id])[src_id]
                           .remove_containers(container_ids=[transfer_request.container.id]))
            self._data_store.LocationsData.update([updated_src])
            source_txt = f" from {transfer_request.source_loc.Id}"

        updated_dst = None
        dest_txt = ""
        if transfer_request.dest_loc is not None:
            dst_id = transfer_request.dest_loc.get_id()
            updated_dst = (self._data_store.LocationsData.get(ids=[dst_id])[dst_id]
                           .store_containers(container_ids=[transfer_request.container.id]))
            self._data_store.LocationsData.update([updated_dst])
            dest_txt = f" to {transfer_request.dest_loc.Id}"

        logger.info(f"Container {transfer_request.container.id} transferred{source_txt}{dest_txt}")
        pub.sendMessage(StorageTopic.CONTAINER_MOVED.value,
                        payload=_build_transfer_payload(transfer_request, updated_src, updated_dst))
        transfer_request.release_reservations(self._reservation_provider)
        req_id = str(transfer_request.get_id())
        if transfer_request.container_reservation_token is not None:
            pub.sendMessage(StorageTopic.CONTAINER_UNRESERVED.value, payload={
                'container_id': str(transfer_request.container.id),
                'transfer_request_id': req_id,
            })
        if transfer_request.destination_reservation_token is not None:
            pub.sendMessage(StorageTopic.LOCATION_UNRESERVED.value, payload={
                'location_id': str(transfer_request.dest_loc.Id),
                'transfer_request_id': req_id,
            })

    def handle_transfer_requests(self,
                                 transfer_request_criteria: Iterable[TransferRequestCriteria],
                                 dest_loc_evaluator: Callable[[Location], float] = None,
                                 unblock_dest_evaluator: Optional[Callable[[Location], float]] = None,
                                 container_evaluator: Optional[Callable[[dcs.Container], float]] = None,
                                 _unblocking_ids: Optional[set] = None):
        _resolved_evaluator = unblock_dest_evaluator if unblock_dest_evaluator is not None else evaluators.random_score
        with self._lock:
            for criteria in transfer_request_criteria:
                # Each top-level criteria gets a fresh unblock chain; recursive calls inherit.
                unblocking = _unblocking_ids if _unblocking_ids is not None else set()

                request = self.resolve_transfer_request_criteria(
                    criteria=criteria,
                    dest_loc_evaluator=dest_loc_evaluator,
                    container_evaluator=container_evaluator
                )

                # Reserve before unblocking — dest_loc is recorded in TransferRequestsData,
                # so _unblock's reserved=False dest filter will naturally exclude it.
                try:
                    request = request.acquire_reservations(self._reservation_provider)
                except ReservationFailedError as e:
                    if isinstance(e.__cause__, RateLimitedError):
                        logger.error(
                            f"Reservation rate-limited (retryAfter={e.__cause__.retry_after:.1f}s) — "
                            f"aborting transfer request batch"
                        )
                        raise

                    #TODO: Decide what to do with the transfer request. Options include:
                    # - Skip it and continue with the rest of the batch (current behavior)
                    # - Retry with exponential backoff until it succeeds or a max retry count is reached
                    # - Fail the entire batch immediately (probably not ideal)
                    # - Queue it for later processing by a background worker that handles retries

                    #for now, we'll just log the error and skip the request
                    logger.error(f"Reservation failed — skipping request: {e}")
                    continue
                self._data_store.TransferRequestsData.add([request])
                self._data_store.ContainersData.add_or_update(containers=[request.container])
                pub.sendMessage(StorageTopic.TRANSFER_REQUEST_ADDED.value, payload={
                    'transfer_request_id': str(request.get_id()),
                    'container_id':        str(request.container.id),
                    'source_loc_id':       str(request.source_loc.Id) if request.source_loc else None,
                    'dest_loc_id':         str(request.dest_loc.Id)   if request.dest_loc   else None,
                })

                if request.source_loc is not None:
                    unblocking.add(str(request.container.id))
                    self._unblock(request.container,
                                  request.source_loc,
                                  _resolved_evaluator,
                                  unblocking)
                    # Refresh source_loc — _unblock modifies the location in the data store
                    # (removes blockers); the snapshot captured before unblocking is stale.
                    src_id = request.source_loc.get_id()
                    request = replace(request, source_loc=self._data_store.LocationsData.get(ids=[src_id])[src_id])

                if request.Ready:
                    self._handle_transfer_request(request)
                    self._data_store.TransferRequestsData.remove(requests=[request])
                    pub.sendMessage(StorageTopic.TRANSFER_REQUEST_COMPLETED.value, payload={
                        'transfer_request_id': str(request.get_id()),
                    })
                    dest_deletes = request.dest_loc is not None and request.dest_loc.Meta.delete_on_receive
                    if request.criteria.delete_container_on_transfer or dest_deletes:
                        self._data_store.ContainersData.remove(containers=[request.container])
                        pub.sendMessage(StorageTopic.CONTAINER_REMOVED.value,
                                        payload={'id': str(request.container.id)})
                else:
                    logger.error(f"Transfer request not ready: \n{pprint.pformat(request)}")
                    raise NotImplementedError()

    def clear_all(self) -> dict:
        """Remove all containers and locations, fire CONTAINER_REMOVED events,
        and reset the LocationMapTree.

        Returns counts of what was cleared.
        """
        with self._lock:
            all_containers = list(self._data_store.ContainersData.get().values())
            loc_count      = len(self._data_store.LocationsData.get())
            # Clear channel processors
            for loc in self._data_store.LocationsData.iter_values():
                loc.clear_containers()
            # Wipe all data stores
            self._data_store.clear()
            # Reset tree
            self._location_map_tree._labels.clear()
            self._location_map_tree._inverted.clear()
            self._location_map_tree._levels_order.clear()
            # Notify subscribers of each removed container
            for c in all_containers:
                pub.sendMessage(StorageTopic.CONTAINER_REMOVED.value,
                                payload={'id': str(c.id)})
        logger.info("clear_all: removed %d locations and %d containers",
                    loc_count, len(all_containers))
        return {"cleared_locations": loc_count, "cleared_containers": len(all_containers)}

    def clear_containers(self) -> int:
        """Remove all containers from every location and fire CONTAINER_REMOVED events.

        Returns the number of containers cleared.
        """
        with self._lock:
            all_containers = list(self._data_store.ContainersData.get().values())
            # Clear channel processors in every location
            for loc in self._data_store.LocationsData.iter_values():
                loc.clear_containers()
            # Wipe the data store
            self._data_store.ContainersData.clear()
            # Notify subscribers
            for c in all_containers:
                pub.sendMessage(StorageTopic.CONTAINER_REMOVED.value,
                                payload={'id': str(c.id)})
        logger.info("clear_containers: removed %d containers", len(all_containers))
        return len(all_containers)

    @property
    def Containers(self) -> List[dcs.Container]:
        return list(self._data_store.ContainersData.get().values())

    @property
    def ContainerLocs(self) -> Dict[dcs.Container, Location]:
        with self._lock:
            ret = {}
            loc_map = self._data_store.LocationsData.get()
            container_map = self._data_store.ContainersData.get()
            for _, loc in loc_map.items():
                for container_id in loc.ContainerIds:
                    if container_id in container_map:
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
    def LocationMapTree(self):
        """The LocationMapTree associated with this storage, or None if not set."""
        return self._location_map_tree

    @property
    def OccupiedLocs(self) -> List[Location]:
        """Locations that have at least one container stored."""
        return [loc for loc in self._data_store.LocationsData.get().values() if len(loc.ContainerIds) > 0]

    @property
    def EmptyLocs(self) -> List[Location]:
        """Locations with no containers stored."""
        return [loc for loc in self._data_store.LocationsData.get().values() if len(loc.ContainerIds) == 0]

    def _is_container_reserved(self, container_id) -> bool:
        return self._reservation_provider.is_reserved(str(container_id))

    def _is_location_reserved(self, location_id) -> bool:
        return self._reservation_provider.is_reserved(str(location_id))

    def get_reserved_container_ids(self) -> set:
        """Return the set of container IDs that currently have an active reservation."""
        with self._lock:
            ids = [str(k) for k in self._data_store.ContainersData.get().keys()]
            return self._reservation_provider.get_reserved_ids(ids)

    def get_reserved_location_ids(self) -> set:
        """Return the set of location IDs that currently have an active reservation."""
        with self._lock:
            ids = [str(k) for k in self._data_store.LocationsData.get().keys()]
            return self._reservation_provider.get_reserved_ids(ids)

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


