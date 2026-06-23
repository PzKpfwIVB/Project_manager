from contextlib import ExitStack
from datetime import timedelta
import pytest
from unittest.mock import patch
from fastapi import status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.testclient import TestClient

import application.db.base
from application.main import app, AccessTokenCreator
import application

from application.core.security import (
    AccessTokenCreatorInterface,
    auth_required,
    create_access_token
)
from application.db.base import (
    DB_ACCESSOR,
    User
)


DEFAULT_USER = User(
    username='Bob',  # password: builder
    hashed_password='f52318a05e518a5596012af2ed38de68ac26a468',
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
        return self._creator_func(user, t_delta=timedelta(seconds=0))


class OAuth2PasswordRequestFormMock:
    def __init__(self):
        self.username = 'Bob'
        self.password = 'builder'


@pytest.fixture
def client():
    return TestClient(app)


class TestSignup:
    r""" Tests the `\\signup` endpoint. """

    def test_signup_happy_path(self, client):
        payload = {
            "username": "Alice",
            "password": "alice_pwd",
            "email": "alice@wonderland.com",
            "full_name": "Alice Wonderland"
        }
        response = client.post('/signup', json=payload)

        assert response.status_code == status.HTTP_201_CREATED
        assert payload["username"] in DB_ACCESSOR.user_db
        assert payload["username"] in DB_ACCESSOR.active_users

    @pytest.mark.parametrize(('field_to_empty', 'exp_status', 'exp_in_db'), [
        ("username", status.HTTP_400_BAD_REQUEST, False),
        ("password", status.HTTP_400_BAD_REQUEST, False),
        ("email", status.HTTP_422_UNPROCESSABLE_CONTENT, False),
        ("full_name", status.HTTP_201_CREATED, True)
    ])
    def test_signup_empty_field(
            self,
            client: TestClient,
            field_to_empty: str,
            exp_status: status,
            exp_in_db: bool
    ):
        """ Checks one by one what happens when a field is missing.

        :param client: FastAPI test client.
        :param field_to_empty: The field to set to empty.
        :param exp_status: The expected HTTP response.
        :param exp_in_db: The expectation of whether the resource is created.
        """

        # noinspection PyDictCreation
        payload = {
            "username": "Alice",
            "password": "alice_pwd",
            "email": "alice@wonderland.com",
            "full_name": "Alice Wonderland"
        }

        payload[field_to_empty] = ""
        response = client.post('/signup', json=payload)

        assert response.status_code == exp_status
        assert (payload["username"] in DB_ACCESSOR.user_db) is exp_in_db
        assert (payload["username"] in DB_ACCESSOR.active_users) is exp_in_db

    def test_double_sign_up(self, client):
        """ Tests that a user cannot sign up twice. """

        payload = {
            "username": "Alice",
            "password": "alice_pwd",
            "email": "alice@wonderland.com",
            "full_name": "Alice Wonderland"
        }
        _ = client.post('/signup', json=payload)
        response = client.post('/signup', json=payload)

        assert response.status_code == status.HTTP_409_CONFLICT


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

        app.dependency_overrides[
            OAuth2PasswordRequestForm
        ] = OAuth2PasswordRequestFormMock
        payload = {
            "username": "Bob",
            "password": "builder"
        }
        response = client.post('/login', json=payload)

        app.dependency_overrides.clear()

        assert response.status_code == status.HTTP_200_OK
        assert "access_token" in response.json()
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

        app.dependency_overrides[
            OAuth2PasswordRequestForm
        ] = OAuth2PasswordRequestFormMock
        app.dependency_overrides[auth_required] = lambda: DEFAULT_USER

        payload = {
            "username": "Bob",
            "password": "builder"
        }
        _ = client.post("/login", json=payload)
        token_id = DB_ACCESSOR.active_users['Bob'].token_data.id

        response = client.post('/logout')
        app.dependency_overrides.clear()

        assert response.status_code == status.HTTP_200_OK
        assert 'Bob' not in DB_ACCESSOR.active_users
        assert token_id in DB_ACCESSOR.revoked_tokens


class TestAuthenticatedEndpoint:
    """ Tests an endpoint that requires authentication. """

    def test_token_when_valid(self):
        """ Tests if the token is accepted while it's still valid. """

        app.dependency_overrides[auth_required] = lambda: DEFAULT_USER
        client = TestClient(app)

        payload = {
            "username": "Bob",
            "password": "builder"
        }
        _ = client.post("/login", json=payload)

        response = client.get('/auth-me')

        app.dependency_overrides.clear()

        assert response.status_code == status.HTTP_200_OK

    def test_token_expiry(self):
        """ Tests if the token expires correctly. """

        app.dependency_overrides[AccessTokenCreator] = AccessTokenCreatorMock
        app.dependency_overrides[
            OAuth2PasswordRequestForm
        ] = OAuth2PasswordRequestFormMock
        client = TestClient(app)

        try:
            payload = {
                "username": "Bob",
                "password": "builder"
            }
            _ = client.post("/login", json=payload)

            response = client.get('/auth-me')

            assert response.status_code == status.HTTP_401_UNAUTHORIZED
        finally:
            app.dependency_overrides.clear()
