from json import dumps
from dataclasses import asdict, dataclass

@dataclass(frozen=True)
class BaseDC:
    @property
    def __dict__(self):
        """
        get a python dictionary
        """
        return asdict(self)

    @property
    def json(self):
        """
        get the json formated string
        """
        return dumps(self.__dict__)