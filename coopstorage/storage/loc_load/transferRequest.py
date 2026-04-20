from dataclasses import dataclass, field, asdict, replace
import coopstorage.storage.loc_load.dcs as dcs
import coopstorage.storage.loc_load.qualifiers as lq
from coopstorage.storage.loc_load.location import Location
import logging
from pprint import pformat
from typing import Callable, Optional, Self, Dict
from coopstorage.storage.loc_load.reservation_provider import ReservationProvider
from pubsub import pub
from coopstorage.enums import StorageTopic

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True, kw_only=True)
class TransferRequestCriteria(dcs.BaseIdentifiedDataClass):
    container_query_args: lq.ContainerQualifier = None
    source_loc_query_args: lq.LocationQualifier = None
    dest_loc_query_args: lq.LocationQualifier = None
    new_container: dcs.Container = None
    delete_container_on_transfer: bool = False

    def __post_init__(self):
        if self.delete_container_on_transfer and self.dest_loc_query_args is not None:
            raise ValueError(
                "delete_container_on_transfer=True is invalid when dest_loc_query_args is set"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class TransferRequest(dcs.BaseIdentifiedDataClass):
    criteria: TransferRequestCriteria
    container: dcs.Container = None
    source_loc: Location = None
    dest_loc: Location = None
    container_reservation_token: Optional[str] = None
    destination_reservation_token: Optional[str] = None

    def verify(self):
        # source empty, firm container, dest firm --> store new container at dest
        if self.source_loc is None and \
            self.container is not None and \
            self.dest_loc is not None:
            return True

        # source firm, firm container, dest query --> transfer container
        if self.source_loc is not None and \
            self.container is not None and \
            self.dest_loc is not None:
            return True

        # source empty, firm container, dest empty --> remove container
        if self.source_loc is not None and \
            self.container is not None and \
            self.dest_loc is None:
            return True

        raise ValueError(f"Unhandled Transfer Request \n{pformat(self)}")

    def release_reservations(self, reservation_provider: ReservationProvider) -> None:
        requester = str(self.get_id())
        if self.container_reservation_token is not None:
            reservation_provider.unreserve(self.container_reservation_token, requester)
            pub.sendMessage(StorageTopic.CONTAINER_UNRESERVED.value, payload={
                'container_id': str(self.container.id),
                'transfer_request_id': requester,
            })
        if self.destination_reservation_token is not None:
            reservation_provider.unreserve(self.destination_reservation_token, requester)
            pub.sendMessage(StorageTopic.LOCATION_UNRESERVED.value, payload={
                'location_id': str(self.dest_loc.Id),
                'transfer_request_id': requester,
            })

    def try_acquire_reservations(self, reservation_provider: ReservationProvider) -> 'TransferRequest':
        requester = str(self.get_id())
        container_id = str(self.container.id)
        logger.debug(f"Reserving container={container_id} requester={requester}")
        container_token = reservation_provider.reserve(container_id, requester, resource_type="container")
        if container_token is not None:
            logger.debug(f"Container reservation OK: container={container_id} token={container_token}")
            pub.sendMessage(StorageTopic.CONTAINER_RESERVED.value, payload={
                'container_id': container_id,
                'transfer_request_id': requester,
            })
        else:
            logger.warning(f"Container reservation FAILED: container={container_id} requester={requester}")
            pub.sendMessage(StorageTopic.RESERVATION_FAILED.value, payload={
                'transfer_request_id': requester,
                'failed_resource': 'container',
            })

        dest_token = None
        if self.dest_loc is not None:
            dest_id = str(self.dest_loc.Id)
            logger.debug(f"Reserving dest_loc={dest_id} requester={requester}")
            dest_token = reservation_provider.reserve(dest_id, requester, resource_type="location")
            if dest_token is not None:
                logger.debug(f"Dest reservation OK: dest_loc={dest_id} token={dest_token}")
                pub.sendMessage(StorageTopic.LOCATION_RESERVED.value, payload={
                    'location_id': dest_id,
                    'transfer_request_id': requester,
                })
            else:
                logger.warning(f"Dest reservation FAILED: dest_loc={dest_id} requester={requester}")
                pub.sendMessage(StorageTopic.RESERVATION_FAILED.value, payload={
                    'transfer_request_id': requester,
                    'failed_resource': 'destination',
                })

        return replace(
            self,
            container_reservation_token=container_token,
            destination_reservation_token=dest_token,
        )

    @property
    def Ready(self) -> bool:
        if self.container_reservation_token is None:
            return False
        if self.dest_loc is not None and self.destination_reservation_token is None:
            return False

        # is container ready to be removed
        try:
            if self.source_loc is None:
                pass
            else:
                self.source_loc.verify_removable(self.container.id)
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
            'container': asdict(obj.container),
            'source_loc': Location.to_jsonable_dict(obj.source_loc) if obj.source_loc else "",
            'dest_loc': Location.to_jsonable_dict(obj.dest_loc) if obj.dest_loc else ""
        }

    @classmethod
    def from_jsonable_dict(cls, obj: Dict) -> Self:
        return TransferRequest(
            criteria=TransferRequestCriteria(**obj['criteria']),
            container=dcs.Container(**obj['container']),
            source_loc=Location.from_jsonable_dict(obj['source_loc']) if obj.get('source_loc') else None,
            dest_loc=Location.from_jsonable_dict(obj['dest_loc']) if obj.get('dest_loc') else None
        )
