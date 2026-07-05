from abc import ABC, abstractmethod

from application.schemas.token_data import TokenData
from application.schemas.user import User


class DatabaseConnectionInterface(ABC):
    @abstractmethod
    def __init__(self):
        self.user_db = ...
        self.active_users = ...
        self.revoked_tokens = ...


class DummyDatabaseConnection(DatabaseConnectionInterface):
    def __init__(self):
        self.user_db = {
            'Bob': {
                'username': 'Bob',  # password: builder
                'hashed_password': '$argon2id$v=19$m=65536,t=3,p=4$26WH59/'
                                   'J79rflyr/zqXRPA$yU1y2lGlTqYszF1oLoWlLI'
                                   '+HL3uSEOPJjDV/qzpYdjs',
                'email': 'bob@webuild.com',
                'full_name': "Robert Builder",
                'token_data': None
            }
        }

        self.active_users: dict[str, User] = {}
        self.revoked_tokens: [int, TokenData] = {}


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
