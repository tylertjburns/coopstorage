from coopstorage.my_dataclasses import UoM

each = UoM(name='EACH', each_qty=1)
box = UoM(name='BOX')
pallet = UoM(name='PALLET')
bottle = UoM(name='BOTTLE')
reel = UoM(name='REEl')
spool = UoM(name='SPOOL')


manifest = [
    each,
    pallet,
    bottle,
    box,
    reel
]