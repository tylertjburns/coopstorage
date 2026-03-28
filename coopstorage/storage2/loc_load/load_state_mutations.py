"""
load_state_mutations.py

Functional mutations for Load content — the opt-in content tracking layer.
Storage operates on Load objects as atomic units; this module provides
add/remove operations for the fractional content within a load.

Mirrors the logic from the old container_state_mutations.py, adapted to
the storage2 domain model (Load, LoadContent, UoMCapacity).
"""

import logging
from typing import List, Dict, Tuple

from coopstorage.storage2.loc_load.dcs import Load, LoadContent, UoMCapacity, UnitOfMeasure, Resource

logger = logging.getLogger(__name__)


def _qty_by_resource_uom(load: Load) -> Dict[Tuple[Resource, UnitOfMeasure], float]:
    """Return total qty keyed by (resource, uom) across all contents."""
    ret: Dict[Tuple[Resource, UnitOfMeasure], float] = {}
    for c in load.contents:
        key = (c.resource, c.uom)
        ret[key] = ret.get(key, 0.0) + c.qty
    return ret


def _capacity_for_uom(load: Load, uom: UnitOfMeasure) -> float | None:
    """Return the capacity for a given UoM, or None if no capacity defined."""
    for cap in load.uom_capacities:
        if cap.uom == uom:
            return cap.capacity
    return None


def _merge_contents(contents: List[LoadContent]) -> frozenset:
    """Merge content items with the same (resource, uom) into single entries."""
    merged: Dict[Tuple[Resource, UnitOfMeasure], float] = {}
    for c in contents:
        key = (c.resource, c.uom)
        merged[key] = merged.get(key, 0.0) + c.qty
    return frozenset(
        LoadContent(resource=k[0], uom=k[1], qty=v)
        for k, v in merged.items()
    )


def _rebuild_load(load: Load, new_contents: frozenset) -> Load:
    """Return a new Load with updated contents, preserving all other fields."""
    return Load(
        id=load.id,
        uom=load.uom,
        weight=load.weight,
        contents=new_contents,
        uom_capacities=load.uom_capacities,
    )


def add_content_to_load(load: Load, contents: List[LoadContent]) -> Load:
    """
    Add content items to a load. Returns a new Load instance.

    If the load has uom_capacities defined, validates:
    - The content's UoM is permitted
    - The added qty fits within remaining capacity
    """
    new_contents = list(load.contents)

    for content in contents:
        if load.uom_capacities:
            cap = _capacity_for_uom(load, content.uom)
            if cap is None:
                raise ValueError(
                    f"UoM '{content.uom.name}' is not permitted in load '{load.id}'. "
                    f"Allowed UoMs: {[c.uom.name for c in load.uom_capacities]}"
                )
            current_qty = sum(c.qty for c in new_contents if c.uom == content.uom)
            if current_qty + content.qty > cap:
                raise ValueError(
                    f"Qty {content.qty} of '{content.uom.name}' doesn't fit in load '{load.id}' "
                    f"(current={current_qty}, capacity={cap})"
                )

        new_contents.append(content)
        logger.debug(f"Added {content.qty} x {content.uom.name} ({content.resource.name}) to load {load.id}")

    return _rebuild_load(load, _merge_contents(new_contents))


def remove_content_from_load(load: Load, content: LoadContent) -> Load:
    """
    Remove a quantity of content from a load. Returns a new Load instance.

    Removes whole LoadContent items until the requested qty is satisfied,
    then puts back any excess (fractional removal / splitting logic).
    """
    qty_map = _qty_by_resource_uom(load)
    key = (content.resource, content.uom)
    current_qty = qty_map.get(key, 0.0)

    if current_qty < content.qty:
        raise ValueError(
            f"Not enough '{content.uom.name}' of '{content.resource.name}' in load '{load.id}': "
            f"requested={content.qty}, available={current_qty}"
        )

    # Remove whole items until we have taken at least the requested qty
    matching = [c for c in load.contents if c.resource == content.resource and c.uom == content.uom]
    remaining = list(load.contents)
    removed_qty = 0.0

    for item in matching:
        if removed_qty >= content.qty:
            break
        remaining.remove(item)
        removed_qty += item.qty

    # Put excess back (fractional split)
    delta = removed_qty - content.qty
    if delta > 0:
        excess = LoadContent(resource=content.resource, uom=content.uom, qty=delta)
        remaining.append(excess)

    # Verify correctness
    new_load = _rebuild_load(load, _merge_contents(remaining))
    new_qty = _qty_by_resource_uom(new_load).get(key, 0.0)
    if abs((current_qty - content.qty) - new_qty) > 1e-9:
        raise ValueError(
            f"Content removal verification failed for load '{load.id}': "
            f"expected {current_qty - content.qty}, got {new_qty}"
        )

    logger.debug(f"Removed {content.qty} x {content.uom.name} ({content.resource.name}) from load {load.id}")
    return new_load
