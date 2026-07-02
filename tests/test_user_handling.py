from contextlib import ExitStack
from datetime import timedelta
import pytest
from unittest.mock import patch
from fastapi import status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.testclient import TestClient

import application.db.base
from application.main import app
from application.routers.authentication import AccessTokenCreator
import application

from application.core.security import (
    AccessTokenCreatorInterface,
    auth_required,
    create_access_token
)
from application.db.base import DB_ACCESSOR
from application.schemas.user import User
from application.utils.override_dependencies import OverrideDependencies


DEFAULT_USER = User(
    username='Bob',  # password: builder
    hashed_password='$argon2id$v=19$m=65536,t=3,p=4$26WH59/J79rflyr/'
                    'zqXRPA$yU1y2lGlTqYszF1oLoWlLI+HL3uSEOPJjDV/qzpYdjs',
    email='bob@webuild.com',
    full_name="Robert Builder",
    token_data=None
)


@pytest.fixture(autouse=True)
def mock_db_accessor():
    """ Fixture to mock the db_accessor. """

    with ExitStack() as stack:
        stack.enter_context(
            patch.dict(application.db.base.DB_ACCESSOR.user_db, {})
        )
        stack.enter_context(
            patch.dict(application.db.base.DB_ACCESSOR.active_users, {})
        )
        stack.enter_context(
            patch.dict(application.db.base.DB_ACCESSOR.revoked_tokens, {})
        )
        yield


class AccessTokenCreatorMock(AccessTokenCreatorInterface):
    def __init__(self, creator_func=create_access_token):
        self._creator_func = creator_func

    def create(self, user: User) -> str:
        return self._creator_func(user, t_delta=timedelta(minutes=0))


class OAuth2PasswordRequestFormMock:
    def __init__(self):
        self.username = 'Bob'
        self.password = 'builder'


@pytest.fixture
def client():
    return TestClient(app)


class TestSignup:
    r""" Tests the `\\auth` endpoint. """

    def test_signup_happy_path(self, client):
        payload = {
            "username": "Alice",
            "password": "alice_pwd",
            "email": "alice@wonderland.com",
            "full_name": "Alice Wonderland"
        }
        response = client.post('/auth', data=payload)

        assert response.status_code == status.HTTP_201_CREATED
        assert payload["username"] in DB_ACCESSOR.user_db
        assert payload["username"] in DB_ACCESSOR.active_users

    def test_double_sign_up(self, client):
        """ Tests that a user cannot sign up twice. """

        payload = {
            "username": "Alice",
            "password": "alice_pwd",
            "email": "alice@wonderland.com",
            "full_name": "Alice Wonderland"
        }

        _ = client.post('/auth', data=payload)
        response = client.post('/auth', data=payload)

        exp_query = b'message_data=%7B%22is_error%22%3A+true%2C+%22'\
                    b'content%22%3A+%22Username+already+taken%22%7D'
        assert response.url.query == exp_query


class TestLogInOut:
    r""" Tests the `\\login` and `\\logout` endpoints. """

    def setup_class(self):
        self._oauth_mock = OAuth2PasswordRequestFormMock()

    # noinspection PyMethodMayBeStatic
    def setup_method(self):
        DB_ACCESSOR.user_db.update({
            DEFAULT_USER.username: DEFAULT_USER.model_dump()
        })

    def test_login_happy_path(self, client):
        """ Tests successful login. """

        with OverrideDependencies(app, overrides={
            OAuth2PasswordRequestForm: OAuth2PasswordRequestFormMock
        }):
            payload = {
                "username": "Bob",
                "password": "builder"
            }
            response = client.post('/login', data=payload)

        assert response.url.path == '/projects'
        assert 'Bob' in DB_ACCESSOR.active_users

    @pytest.mark.parametrize(('username', 'password'), [
        ('Bob', ''),
        ('', 'builder'),
        ('', '')
    ])
    def test_login_wrong_credentials(
            self,
            client: TestClient,
            username: str,
            password: str
    ):
        """ Tests login with wrong credentials. """
        payload = {
            "username": username,
            "password": password
        }
        response = client.post('/login', json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_logout(self, client):
        """ Tests successful logout. """

        with OverrideDependencies(app, overrides={
            OAuth2PasswordRequestForm: OAuth2PasswordRequestFormMock,
            auth_required: lambda: DEFAULT_USER
        }):
            payload = {
                "username": "Bob",
                "password": "builder"
            }
            _ = client.post('/login', json=payload)
            token_id = DB_ACCESSOR.active_users['Bob'].token_data.id

            response = client.post('/logout')

        assert response.status_code == status.HTTP_200_OK
        assert 'Bob' not in DB_ACCESSOR.active_users
        assert token_id in DB_ACCESSOR.revoked_tokens


class TestAuthenticatedEndpoint:
    """ Tests an endpoint that requires authentication. """

    def test_token_when_valid(self, client):
        """ Tests if the token is accepted while it's still valid. """

        with OverrideDependencies(app, overrides={
            auth_required: lambda: DEFAULT_USER
        }):
            payload = {
                "username": "Bob",
                "password": "builder"
            }
            _ = client.post('/login', json=payload)

            response = client.get('/auth-me')

        assert response.status_code == status.HTTP_200_OK

    def test_token_expiry(self, client):
        """ Tests if the token expires correctly. """

        with OverrideDependencies(app, overrides={
            AccessTokenCreator: AccessTokenCreatorMock,
            OAuth2PasswordRequestForm: OAuth2PasswordRequestFormMock
        }):
            payload = {
                "username": "Bob",
                "password": "builder"
            }
            _ = client.post('/login', json=payload)
            DB_ACCESSOR.active_users.update(
                {DEFAULT_USER.username: DEFAULT_USER}
            )

            response = client.get('/auth-me')

        exp_query = b'message_data=%7B%22is_error%22%3A+true%2C+%22' \
                    b'content%22%3A+%22Could+not+validate+credentials%22%7D'
        assert response.url.query == exp_query
