import uuid
from typing import Union

def try_resolve_guid(id: str) -> Union[str, uuid.UUID]:
    try:
        return uuid.UUID(id)
    except:
        return id

def split_strip(txt: str):
    return [x.strip() for x in txt.split(',')]
