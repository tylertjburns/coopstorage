from coopstorage.my_dataclasses import Location, LocInvState, Content, loc_inv_state_factory, content_factory, merge_content
from coopstorage.exceptions import *

def add_content_to_loc(inv_state: LocInvState, content: Content) -> LocInvState:
    # verify content matches uom capacity
    if inv_state.location.uom_capacities and \
        content.uom not in [x.uom for x in inv_state.location.uom_capacities]:
        raise ContentDoesntMatchLocationException(location=inv_state.location, content=content)

    # verify the uom matches loc designated uom
    designated_uom_types = inv_state.ActiveUoMDesignations
    if len(designated_uom_types) > 0 and content.uom not in designated_uom_types:
        raise ContentDoesntMatchLocationActiveDesignationException(content=content, loc_inv=inv_state)

    # verify capacity
    qty_at_loc = inv_state.qty_uom(content.resourceUoM.uom)
    if qty_at_loc + content.qty > inv_state.location.UoMCapacities[content.uom]:
        raise NoRoomAtLocationException(loc_inv=inv_state)

    # add content and merge at location
    new_contents = list(inv_state.contents)
    new_contents.append(content)
    new_contents = merge_content(new_contents)

    # create new state
    new_state = loc_inv_state_factory(
        loc_inv_state=inv_state,
        contents=frozenset(new_contents),
    )

    return new_state

def _remove_content_from_location(inv_state: LocInvState, content: Content) -> LocInvState:
    if content not in inv_state.contents:
        raise MissingContentException(loc_inv=inv_state)

    contents = list(inv_state.contents)
    idx_of_content = contents.index(content)
    removed = contents.pop(idx_of_content)

    new_state = loc_inv_state_factory(
        loc_inv_state=inv_state,
        contents=frozenset(contents)
    )

    return new_state

def remove_content_from_location(inv_state: LocInvState, content: Content) -> LocInvState:
    # verify amount to be removed
    existing = inv_state.qty_resource_uom(content.resourceUoM)

    if existing < content.qty:
        raise MissingContentException(loc_inv=inv_state)

    cnt_at_loc = inv_state.content(resource_uom_filter=[content.resourceUoM], aggregate=False)
    removed_cnt = []
    new_state = inv_state
    while sum(x.qty for x in removed_cnt) < content.qty:
        cntnt_to_remove = next(x for x in cnt_at_loc if x not in removed_cnt)
        new_state = _remove_content_from_location(inv_state=new_state, content=cntnt_to_remove)
        removed_cnt.append(cntnt_to_remove)

    # reconcile removed content
    delta = sum(x.qty for x in removed_cnt) - content.qty
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
        new_state = add_content_to_loc(inv_state=new_state, content=to_put_back_cntnt)

    # Verify
    if inv_state.qty_resource_uom(content.resourceUoM) - content.qty != new_state.qty_resource_uom(content.resourceUoM):
        raise ValueError(f"The qty returned does not match the qty requested")

    return new_state