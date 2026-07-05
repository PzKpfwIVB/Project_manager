from abc import ABC, abstractmethod
import datetime as dt
from datetime import datetime, timedelta
from typing import Annotated
import uuid

import jwt
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from fastapi import Cookie, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer

from application.core.config import SECRET_KEY
from application.db.session import SessionDependency
from application.db.crud import (
    insert_token_into_db,
    delete_token_from_db,
    is_token_revoked,
    select_user_by_username
)
from application.schemas.user import User
from application.schemas.token_data import TokenData


ENCRYPTION_ALGORITHM = 'HS256'

password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash('dummy_password')

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/login')


class AccessTokenCreatorInterface(ABC):
    @abstractmethod
    def __init__(self, creator_func):
        self._creator_func = creator_func

    @abstractmethod
    def create(self, session: Session, user: User): ...


def verify_password(plain_password: str, stored_hash: str):
    return password_hash.verify(plain_password, stored_hash)


def authenticate_user(session: Session, username: str, password: str):
    """ Check if the user exists in the database. """

    user = select_user_by_username(session, username)
    if user is None:
        verify_password(password, DUMMY_HASH)  # Against timing attacks
        return None
    elif not verify_password(password, user.hashed_password):
        return None

    return user


def create_access_token(
        session: Session,
        user: User,
        t_delta: timedelta = timedelta(minutes=60)
) -> str:
    """
    Creates a JWT access token that's valid for an hour (by default) and adds
    the user to the active user's list.
    """

    to_encode = {
        'sub': user.username,
        'exp': datetime.now(tz=dt.timezone.utc) + t_delta,
        'jti': str(uuid.uuid4())
    }

    encoded_jwt = jwt.encode(
        payload=to_encode,
        key=SECRET_KEY,
        algorithm=ENCRYPTION_ALGORITHM
    )

    token_data = TokenData.from_dict(to_encode)
    delete_token_from_db(session, token_data, by_username=True)
    user.token_data = insert_token_into_db(session, token_data)

    return encoded_jwt


async def auth_required(
        session: SessionDependency,
        token: Annotated[str | None, Cookie(alias='access_token')] = None
) -> User | RedirectResponse:
    """ Authorizes the user and returns a `User` object. """

    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={'www-authenticate': 'Bearer'}
    )

    decoding_params = {
        'jwt': token,
        'key': SECRET_KEY,
        'algorithms': [ENCRYPTION_ALGORITHM]
    }

    try:
        payload = jwt.decode(**decoding_params)
        username: str = payload.get('sub')
        if username is None:
            raise credential_exception
    except jwt.exceptions.DecodeError:
        raise credential_exception
    except jwt.exceptions.ExpiredSignatureError:
        credential_exception.detail = "Token expired"

        # payload = jwt.decode(**decoding_params, options={'verify_exp': False})
        # username: str = payload.get('sub')
        # delete_active_user(username)  # Deactivate if token expired

        raise credential_exception

    user = select_user_by_username(session, username)
    if user is None:
        raise credential_exception

    if user.token_data is not None \
            and is_token_revoked(session, user.token_data):
        credential_exception.detail = "Token revoked"
        raise credential_exception

    return user
