from coopstorage.my_dataclasses import Content, ContainerState, container_factory, content_factory, merge_content
import coopstorage.storage.cubing as cubing
from typing import List

def add_content_to_container(container: ContainerState, contents: List[Content]) -> ContainerState:
    new_container = container
    for content in contents:

        # verify content matches uom capacity
        cubing.check_raise_uom_capacity_match([content.UoM], list(container.uom_capacities))

        # verify qty fits
        current_qty = sum(x.qty for x in container.contents)
        cubing.check_raise_uom_qty_doesnt_fit(uom=content.UoM, qty=content.qty, current=current_qty, capacity=container.UoMCapacities[content.UoM])

        # add content and merge at location
        new_contents = list(container.contents)
        new_contents.append(content)
        new_contents = merge_content(new_contents)

        new_container = container_factory(new_container, contents=frozenset(new_contents))

    return new_container

def remove_content_from_container(container: ContainerState, content: Content) -> ContainerState:
    # verify amount to be removed
    cubing.check_raise_not_enough_content_in_container(container=container, content=content)

    # iterate and remove content from container until AT LEAST enough content has been removed to satisfy requirement
    cnt_at_loc = [x for x in container.contents if x.resourceUoM.uom == content.UoM]
    removed_cnt = []
    cntnr_after_removing = container
    while sum(x.qty for x in removed_cnt) < content.qty:
        cntnt_to_remove = next(x for x in cnt_at_loc if x not in removed_cnt)
        contents = list(cntnr_after_removing.contents)
        idx_of_content_to_remove = contents.index(cntnt_to_remove)
        removed = contents.pop(idx_of_content_to_remove)
        cntnr_after_removing = container_factory(
            container=cntnr_after_removing,
            contents=frozenset(contents)
        )
        removed_cnt.append(removed)

    # reconcile removed content
    delta = sum(x.qty for x in removed_cnt) - content.qty
    cntnr_after_adding_back = cntnr_after_removing
    if delta > 0:
        # remove split from location
        to_split = next(x for x in removed_cnt if x.qty >= delta)
        removed_cnt.remove(to_split)

        # decide what to keep out and what to put back
        if to_split.qty == delta:
            to_put_back_cntnt = to_split
        else:

            to_keep_cntnt = content_factory(to_split, qty=to_split.qty - delta)
            removed_cnt.append(to_keep_cntnt)
            to_put_back_cntnt = content_factory(to_split, qty=delta)

        # put back content
        cntnr_after_adding_back = add_content_to_container(container=cntnr_after_removing, contents=[to_put_back_cntnt])

    # Verify
    if container.QtyResourceUoMs[content.resourceUoM] - content.qty != cntnr_after_adding_back.QtyResourceUoMs[content.resourceUoM]:
        raise ValueError(f"The qty returned does not match the qty requested")

    return cntnr_after_adding_back

if __name__ == "__main__":
    from coopstorage.my_dataclasses import UnitOfMeasure, UoMCapacity
    uom_to_store = UnitOfMeasure("each")
    uom_capacity = UoMCapacity(uom_to_store, capacity=100)
    container_state = ContainerState(lpn="test", uom=UnitOfMeasure("CNTNR"), uom_capacities=frozenset([uom_capacity]))

    content = content_factory(resource_name="a", qty=5, uom=uom_to_store)
    new_container_state = add_content_to_container(container_state, content)
    print(new_container_state.QtyResourceUoMs)
    to_remove = content_factory(resource_name="a", qty=3, uom=uom_to_store)
    new_container_state = remove_content_from_container(new_container_state, to_remove)
    print(new_container_state.QtyResourceUoMs)
