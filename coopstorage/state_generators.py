from my_dataclasses import Content, Resource, ResourceUoM, StorageState, LocInvState, Location

def dummy_state():
    test_loc = Location(id='Test',
                        uom_capacities=frozenset([UoMCapacity(uom=uoms.each, capacity=100)]))
    qty = 10
    content = dummy_content(qty)
    state = LocInvState(
        location=test_loc,
        contents=frozenset([content]),
    )
    return state