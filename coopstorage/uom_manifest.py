from coopstorage.my_dataclasses import UnitOfMeasure

each = UnitOfMeasure(name='EACH', each_qty=1)
box = UnitOfMeasure(name='BOX')
pallet = UnitOfMeasure(name='PALLET')
bottle = UnitOfMeasure(name='BOTTLE')
reel = UnitOfMeasure(name='REEl')
spool = UnitOfMeasure(name='SPOOL')


manifest = [
    each,
    pallet,
    bottle,
    box,
    reel
]