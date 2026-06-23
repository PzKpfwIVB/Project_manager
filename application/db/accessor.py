from abc import ABC, abstractmethod
import datetime as dt
from typing import ClassVar

from pydantic import BaseModel


class DatabaseConnectionInterface(ABC):
    @abstractmethod
    def __init__(self):
        self.user_db = ...
        self.active_users = ...
        self.revoked_tokens = ...


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


class User(BaseModel):
    username: str
    hashed_password: str | None = None
    email: str | None = None
    full_name: str | None = None
    token_data: TokenDataDb | None = None


class DummyDatabaseConnection(DatabaseConnectionInterface):
    def __init__(self):
        self.user_db = {
            'Bob': {
                'username': 'Bob',  # password: builder
                'hashed_password': 'f52318a05e518a5596012af2ed38de68ac26a468',
                'email': 'bob@webuild.com',
                'full_name': "Robert Builder",
                'token_data': None
            }
        }

        self.active_users: dict[str, User] = {}
        self.revoked_tokens: [int, TokenDataDb] = {}


class DatabaseAccessor:
    def __init__(self, connector: DatabaseConnectionInterface):
        self._connector = connector

    @property
    def user_db(self):
        return self._connector.user_db

    @property
    def active_users(self):
        return self._connector.active_users

    @property
    def revoked_tokens(self):
        return self._connector.revoked_tokens

    @revoked_tokens.setter
    def revoked_tokens(self, new_revoked_tokens):
        self._connector.revoked_tokens = new_revoked_tokens
