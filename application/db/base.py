from abc import ABC
import datetime as dt
from hashlib import sha1
import logging
from typing import ClassVar


from application.db.accessor import (
    DatabaseAccessor,
    DummyDatabaseConnection,
)
from application.schemas.signup_info import SignupInfo
from application.schemas.token_data import TokenData
from application.schemas.user import User


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
)


DB_ACCESSOR = DatabaseAccessor(DummyDatabaseConnection())


class TokenDataInterface(ABC):
    username: ClassVar[str | None]
    expire: ClassVar[dt.datetime | None]
    id: ClassVar[str | None]


def get_user_by_username(username, db_accessor=DB_ACCESSOR) -> User | None:
    """ Searches for a user in the DB and returns None if not found. """

    logging.info(f"Request accepted for user '{username}'")
    try:
        return User(**db_accessor.user_db[username])
    except KeyError:
        return None


def sign_user_up(signup_info: SignupInfo, db_accessor=DB_ACCESSOR):
    """ Stores a user in the DB. """

    new_user = signup_info.model_dump()
    password = new_user.pop('password')
    new_user.update({
        'hashed_password': sha1(password.encode()).hexdigest(),
        'token_data': None
    })

    logging.info(f"Signing up new user '{new_user}'")
    db_accessor.user_db.update({new_user['username']: new_user})

    return User(**new_user)


def log_user_out(username: str) -> None:
    """ Inactivates a user and revokes their token. """

    logging.info(f"Logging out user '{username}'")
    user = delete_active_user(username)
    post_revoked_token(user.token_data)


def post_active_user(user: User, db_accessor=DB_ACCESSOR):
    """ Adds a user to the list of active users. """

    logging.info(f"Adding user '{user.username}' to the list of active users")
    db_accessor.user_db.update({user.username: user.model_dump()})
    db_accessor.active_users.update({user.username: user})


def delete_active_user(username: str, db_accessor=DB_ACCESSOR) -> User:
    """ Deletes a user from the list of active users. """

    logging.info(f"Removing user '{username}' from the list of active users")
    return db_accessor.active_users.pop(username)


def _purge_expired_tokens_from_revoked_tokens(db_accessor=DB_ACCESSOR):
    """
    Removes expired tokens from the list of revoked tokens, as they are then
    invalid anyway.
    """

    db_accessor.revoked_tokens = {
        _id: t for _id, t in db_accessor.revoked_tokens.items()
        if t.expire > dt.datetime.now(tz=dt.timezone.utc)
    }


def is_token_revoked(
        token_data: TokenData | None,
        db_accessor=DB_ACCESSOR
) -> bool:
    """ Checks if an active token is revoked. """

    _purge_expired_tokens_from_revoked_tokens()

    try:
        _ = db_accessor.revoked_tokens[token_data.id]
        return True
    except KeyError:
        return False


def post_revoked_token(
        token_data: TokenData,
        db_accessor=DB_ACCESSOR
) -> None:
    """ Adds a revoked token to the list of revoked tokens. """

    logging.info(
        f"Adding revoked token for user '{token_data.username}' to the list "
        f"of revoked tokens"
    )

    db_accessor.revoked_tokens[token_data.id] = token_data

    _purge_expired_tokens_from_revoked_tokens()
