from typing import Iterable, Any, Hashable, Union, List
from coopstorage.my_dataclasses import UnitOfMeasure, UoMCapacity, ContainerState, Content
from coopstorage.exceptions import *

def fits_qty(capacity, current_qty, new_qty) -> bool:
    if current_qty + new_qty > capacity:
        return False

    return True

comparable = Union[Iterable[Hashable], Hashable]

def verify_whitelist(check: comparable, whitelist: comparable) -> bool:

    if not isinstance(check, Iterable):
        check = [check]

    if not isinstance(whitelist, Iterable):
        whitelist = [whitelist]

    if whitelist is None or \
            not all([x in whitelist for x in check]):
        return False

    return True


def verify_blacklist(check: comparable, blacklist: comparable) -> bool:
    if not isinstance(check, Iterable):
        check = [check]

    if not isinstance(blacklist, Iterable):
        blacklist = [blacklist]

    if blacklist is not None and \
            any([x in blacklist for x in check]):
        return False

    return True

def check_raise_uom_capacity_match(check_uoms: List[UnitOfMeasure], uom_capacities: List[UoMCapacity]):
    if not verify_whitelist(check_uoms, [x.uom for x in uom_capacities]):
        raise cevents.StorageException(
            cevents.OnUoMsDontMatchUoMCapacityDefinitionExceptionEventArgs(
                uoms=check_uoms,
                uom_capacities=uom_capacities)
        )

def check_raise_uom_qty_doesnt_fit(uom: UnitOfMeasure, qty: float, current: float, capacity: float):
    if not fits_qty(capacity, current, qty):
        raise cevents.StorageException(
            cevents.OnQtyUoMDoesntFitAtDestinationExceptionEventArgs(
                uom=uom,
                new=qty,
                current=current,
                capacity=capacity
        ))

def check_raise_not_enough_content_in_container(container: ContainerState, content: Content):
    # verify amount to be removed
    existing = container.QtyResourceUoMs[content.resourceUoM]

    if existing < content.qty:
        raise cevents.StorageException(
            cevents.OnNotEnoughUoMsException_EventArgs(
                uom=content.UoM,
                qty=content.qty,
                current=container.QtyUoMs
        ))