from abc import ABC
import datetime as dt
from typing import ClassVar

from pydantic import BaseModel


class TokenDataInterface(ABC):
    username: ClassVar[str | None]
    expire: ClassVar[dt.datetime | None]
    id: ClassVar[str | None]


class TokenDataDb(BaseModel):
    username: str | None = None
    expire: dt.datetime | None = None
    id: str | None = None

    @classmethod
    def from_obj(cls, obj: TokenDataInterface):
        return cls(
            username=obj.username,
            expire=obj.expire,
            id=obj.id
        )
