from abc import ABC
import datetime as dt
from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class TokenDataInterface(ABC):
    username: ClassVar[str | None]
    expire: ClassVar[dt.datetime | None]
    id: ClassVar[str | None]


class TokenData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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

    @classmethod
    def from_dict(cls, data: dict):
        """ Create from an unencoded JWT payload dict. """
        return cls(
            username=data.get('sub'),
            expire=data.get('exp'),
            id=data.get('jti')
        )
