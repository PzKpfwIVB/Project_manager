from abc import ABC, abstractmethod
import datetime as dt
from datetime import datetime, timedelta
from hashlib import sha1
from typing import Annotated
import uuid

import jwt

from fastapi import Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from application.core.config import SECRET_KEY
from application.db.base import (
    get_user_by_username,
    post_active_user,
    delete_active_user,
    is_token_revoked
)
from application.schemas.user import User


ENCRYPTION_ALGORITHM = 'HS256'


class AccessTokenCreatorInterface(ABC):
    @abstractmethod
    def __init__(self, creator_func): ...
    @abstractmethod
    def create(self, user: User): ...


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None
    expire: datetime | None = None
    id: str | None = None

    @classmethod
    def from_dict(cls, data: dict):
        """ Create from an unencoded JWT payload dict. """
        return cls(
            username=data.get('sub'),
            expire=data.get('exp'),
            id=data.get('jti')
        )


oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/login')


def authenticate_user(username: str, password: str):
    """ Check if the user exists in the database. """

    user = get_user_by_username(username)
    if user is None:
        return None
    elif sha1(password.encode()).hexdigest() != user.hashed_password:
        return None

    return user


def create_access_token(user: User, t_delta: timedelta = timedelta(minutes=60)):
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
        algorithm=ENCRYPTION_ALGORITHM)

    user.token_data = TokenData.from_dict(to_encode)
    post_active_user(user)

    return encoded_jwt


async def auth_required(
        token: Annotated[str, Depends(oauth2_scheme)]
) -> User | RedirectResponse:
    """ Authorizes the user and returns a `User` object. """

    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={'www-authenticate': 'Bearer'}
    )

    try:
        payload = jwt.decode(
            jwt=token,
            key=SECRET_KEY,
            algorithms=[ENCRYPTION_ALGORITHM]
        )
        username: str = payload.get('sub')
        if username is None:
            raise credential_exception
    except jwt.exceptions.DecodeError:
        raise credential_exception
    except jwt.exceptions.ExpiredSignatureError:
        credential_exception.detail = "Token expired"

        delete_active_user(username)  # Deactivate if token expired

        raise credential_exception

    user = get_user_by_username(username)
    if user is None:
        raise credential_exception

    if user.token_data is not None and is_token_revoked(user.token_data):
        credential_exception.detail = "Token revoked"
        raise credential_exception

    return user
