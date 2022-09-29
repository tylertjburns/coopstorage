from coopstorage.my_dataclasses import Resource, ResourceType

sku_a = Resource(name='a', description='aaa', type=ResourceType.DEFAULT)
sku_b = Resource(name='b', description='bbb', type=ResourceType.DEFAULT)
sku_c = Resource(name='c', description='ccc', type=ResourceType.DEFAULT)
sku_d = Resource(name='d', description='ddd', type=ResourceType.DEFAULT)
sku_e = Resource(name='e', description='eee', type=ResourceType.DEFAULT)
sku_f = Resource(name='f', description='fff', type=ResourceType.DEFAULT)
sku_g = Resource(name='g', description='ggg', type=ResourceType.DEFAULT)
raw_1 = Resource(name='h', description='hhh', type=ResourceType.DEFAULT)
raw_2 = Resource(name='i', description='iii', type=ResourceType.DEFAULT)

manifest = [
    sku_a,
    sku_b,
    sku_c,
    sku_d,
    sku_e,
    sku_f,
    sku_g,
    raw_1,
    raw_2
]