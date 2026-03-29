"""
container_state_mutations.py

Functional mutations for Container content — the opt-in content tracking layer.
Storage operates on Container objects as atomic units; this module provides
add/remove operations for the fractional content within a container.

Mirrors the logic from the old load_state_mutations.py, adapted to
the storage2 domain model (Container, ContainerContent, UoMCapacity).
"""

import logging
from typing import List, Dict, Tuple

from coopstorage.storage2.loc_load.dcs import Container, ContainerContent, UoMCapacity, UnitOfMeasure, Resource

logger = logging.getLogger(__name__)


def _qty_by_resource_uom(container: Container) -> Dict[Tuple[Resource, UnitOfMeasure], float]:
    """Return total qty keyed by (resource, uom) across all contents."""
    ret: Dict[Tuple[Resource, UnitOfMeasure], float] = {}
    for c in container.contents:
        key = (c.resource, c.uom)
        ret[key] = ret.get(key, 0.0) + c.qty
    return ret


def _capacity_for_uom(container: Container, uom: UnitOfMeasure) -> float | None:
    """Return the capacity for a given UoM, or None if no capacity defined."""
    for cap in container.uom_capacities:
        if cap.uom == uom:
            return cap.capacity
    return None


def _merge_contents(contents: List[ContainerContent]) -> frozenset:
    """Merge content items with the same (resource, uom) into single entries."""
    merged: Dict[Tuple[Resource, UnitOfMeasure], float] = {}
    for c in contents:
        key = (c.resource, c.uom)
        merged[key] = merged.get(key, 0.0) + c.qty
    return frozenset(
        ContainerContent(resource=k[0], uom=k[1], qty=v)
        for k, v in merged.items()
    )


def _rebuild_container(container: Container, new_contents: frozenset) -> Container:
    """Return a new Container with updated contents, preserving all other fields."""
    return Container(
        id=container.id,
        uom=container.uom,
        weight=container.weight,
        contents=new_contents,
        uom_capacities=container.uom_capacities,
        resource_qualifier=container.resource_qualifier,
        uom_qualifier=container.uom_qualifier,
    )


def add_content_to_container(container: Container, contents: List[ContainerContent]) -> Container:
    """
    Add content items to a container. Returns a new Container instance.

    If the container has uom_capacities defined, validates:
    - The content's UoM is permitted
    - The added qty fits within remaining capacity
    """
    new_contents = list(container.contents)

    for content in contents:
        if container.resource_qualifier is not None:
            result = container.resource_qualifier.qualify([content.resource])[content.resource]
            if not result.result:
                raise ValueError(
                    f"Resource '{content.resource.name}' rejected by container '{container.id}' resource_qualifier: "
                    f"{result.failure_reasons}"
                )

        if container.uom_qualifier is not None:
            result = container.uom_qualifier.qualify([content.uom])[content.uom]
            if not result.result:
                raise ValueError(
                    f"UoM '{content.uom.name}' rejected by container '{container.id}' uom_qualifier: "
                    f"{result.failure_reasons}"
                )

        if container.uom_capacities:
            cap = _capacity_for_uom(container, content.uom)
            if cap is None:
                raise ValueError(
                    f"UoM '{content.uom.name}' is not permitted in container '{container.id}'. "
                    f"Allowed UoMs: {[c.uom.name for c in container.uom_capacities]}"
                )
            current_qty = sum(c.qty for c in new_contents if c.uom == content.uom)
            if current_qty + content.qty > cap:
                raise ValueError(
                    f"Qty {content.qty} of '{content.uom.name}' doesn't fit in container '{container.id}' "
                    f"(current={current_qty}, capacity={cap})"
                )

        new_contents.append(content)
        logger.debug(f"Added {content.qty} x {content.uom.name} ({content.resource.name}) to container {container.id}")

    return _rebuild_container(container, _merge_contents(new_contents))


def remove_content_from_container(container: Container, content: ContainerContent) -> Container:
    """
    Remove a quantity of content from a container. Returns a new Container instance.

    Removes whole ContainerContent items until the requested qty is satisfied,
    then puts back any excess (fractional removal / splitting logic).
    """
    qty_map = _qty_by_resource_uom(container)
    key = (content.resource, content.uom)
    current_qty = qty_map.get(key, 0.0)

    if current_qty < content.qty:
        raise ValueError(
            f"Not enough '{content.uom.name}' of '{content.resource.name}' in container '{container.id}': "
            f"requested={content.qty}, available={current_qty}"
        )

    # Remove whole items until we have taken at least the requested qty
    matching = [c for c in container.contents if c.resource == content.resource and c.uom == content.uom]
    remaining = list(container.contents)
    removed_qty = 0.0

    for item in matching:
        if removed_qty >= content.qty:
            break
        remaining.remove(item)
        removed_qty += item.qty

    # Put excess back (fractional split)
    delta = removed_qty - content.qty
    if delta > 0:
        excess = ContainerContent(resource=content.resource, uom=content.uom, qty=delta)
        remaining.append(excess)

    # Verify correctness
    new_container = _rebuild_container(container, _merge_contents(remaining))
    new_qty = _qty_by_resource_uom(new_container).get(key, 0.0)
    if abs((current_qty - content.qty) - new_qty) > 1e-9:
        raise ValueError(
            f"Content removal verification failed for container '{container.id}': "
            f"expected {current_qty - content.qty}, got {new_qty}"
        )

    logger.debug(f"Removed {content.qty} x {content.uom.name} ({content.resource.name}) from container {container.id}")
    return new_container
