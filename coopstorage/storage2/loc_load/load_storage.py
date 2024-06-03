from cooptools.register import Register
from cooptools.reservation.reservationmanager import ReservationManager
from coopstorage.storage2.loc_load.types import *
import coopstorage.storage2.loc_load.dcs as dcs
import coopstorage.storage2.loc_load.exceptions as errs
from typing import Dict, Iterable, Callable
import coopstorage.storage2.loc_load.interfaces as inter
from coopstorage.storage2.loc_load.types import UniqueId

class LoadStorage:
    def __init__(self,
                 storer_resolver: Callable[[], UniqueId]):
        self._loads: Register[dcs.Load] = Register()
        self._storers: Register[inter.IStorer] = Register()
        self._storage_by_load_map: Dict[UniqueId, UniqueId] = {}
        self._reservation = ReservationManager()
        self._storer_resolver = storer_resolver

    def _verify_load(self, id: UniqueId):
        if not id in self._loads.Registry.keys():
            raise errs.UnknownLoadIdException(id)

    def _verify_storer(self, id: UniqueId):
        if id not in self._storers.Registry.keys():
            raise errs.UnknownStorerIdException(id)

    def _verify_transfer_request(self, request: dcs.TransferRequest):
        self._verify_storer(request.source_loc_id)
        self._verify_storer(request.dest_loc_id)
        self._verify_load(request.load_id)

    def register_loads(self, loads: Iterable[dcs.Load]):
        self._loads.register(loads, [load.id for load in loads])

    def add_load(self, load: dcs.Load, storer_id: UniqueId = None):
        """Register the load"""
        self.register_loads([load])

        """Choose storer id"""
        if storer_id is not None:
            storer_id = self._storer_resolver()

        """ get storer """
        self._verify_storer(storer_id)
        storer = self._storers.Registry[storer_id]

        """ store load"""
        storer.store([load])

    def add_loads(self, loads: Dict[dcs.Load, ]):
        self._loads.register(loads, ids=[x.id for x in loads])


    def handle_transfer_requests(self, requests: Iterable[dcs.TransferRequest]):
        for request in requests:
            self._verify_transfer_request(request)


    def remove_loads(self,
                     loads: Iterable[dcs.Load] = None,
                     ids: Iterable[UniqueId] = None):
        if loads is not None:
            ids = [load.id for load in loads]
        self._loads.unregister(ids=ids)

        for lpn in ids:
            if lpn

    def reserve_loads(self, ):
        pass

    @property
    def Loads(self) -> List[Load]:
        return list(self._loads.Registry.values())
