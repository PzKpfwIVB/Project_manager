from contextlib import contextmanager
import datetime as dt
import os
import pytest

from psycopg2.errorcodes import FOREIGN_KEY_VIOLATION, UNIQUE_VIOLATION
from psycopg2 import errors

from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import dialect as postgresql_dialect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from application.core.config import DATABASE_URL, DUMMY_FILES
from application.db.crud import (
    delete_document_from_db,
    delete_project_from_db,
    delete_token_from_db,
    get_username_by_id,
    insert_document_into_db,
    insert_project_into_db,
    insert_token_into_db,
    insert_user_into_db,
    invite_user_to_project,
    remove_user_from_project,
    revoke_token,
    select_all_project_owners,
    select_all_projects,
    select_all_users,
    select_document_by_id,
    select_project_by_id,
    select_project_participants,
    select_user_by_username,
    select_user_projects,
    update_document_in_db,
    update_project_info_in_db
)
from application.db.declarative_mapping import (
    DocumentOrm,
    ProjectOrm,
    RevokedTokenOrm,
    TokenOrm,
    UserOrm,
    UserProjectOrm
)
from application.db.load_db_with_dummy_data import LocalFileAsUploadFile
from application.schemas.document import Document
from application.schemas.project import Project, ProjectInfo
from application.schemas.token_data import TokenData
from application.schemas.user import UserSignupForm


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)


@pytest.fixture
def get_session():
    with Session() as session:
        yield session


@pytest.fixture
def engine_fixture():
    return engine


@contextmanager
def capture_sql_executed(engine_fixture):
    captures = []

    def before_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
    ):
        captures.append((statement, parameters))

    event.listen(engine, 'before_cursor_execute', before_cursor_execute)
    try:
        yield captures
    finally:
        event.remove(engine, 'before_cursor_execute', before_cursor_execute)


class DoNotTestMe:
    """ Marks a required value but one that is not to be tested. """
    def __init__(self):
        pass


class InsertionAssertions:
    """ A unified interface for defining assertions for insertion. """

    def __init__(
            self,
            table_name: str,
            params: dict,
            returns: list[str] | None = None
    ) -> None:
        """ Initializer for insertion assertions' definition.

        :param table_name: The name of the table to be inserted into. Prefer
        providing the name via attribute access of the ORM model.

        :param params: The parameters used in the insertion.

        :param returns: The expected DB-generated attributes.
        """

        self.table_name = table_name
        self.params = params
        self.values = list(self.params.keys())
        self.returns = returns

        self._starts_with = ''

    def is_insert(self, stmt: str) -> bool:
        """ Checks if the given statement is the insertion to be tested. """

        insert_into = f"INSERT INTO {self.table_name}"
        insert = f"INSERT {self.table_name}"
        if stmt.startswith(insert_into):
            self._starts_with = insert_into
            return True
        elif stmt.startswith(insert):
            self._starts_with = insert
            return True

        return False

    def assert_values(self, stmt: str) -> None:
        """ Asserts if the correct values are inserted into the database. """

        value_stmt = f"({', '.join(self.values)})"
        assert stmt.startswith(f"{self._starts_with} {value_stmt}")

    def assert_params(self, params: dict) -> None:
        """ Asserts if the passed params are the expected ones. """

        # Assert only the requested params, not all the passed ones
        for key, value in self.params.items():
            if not isinstance(value, DoNotTestMe):
                assert params[key] == value

    def assert_returns(self, stmt: str) -> None:
        """ Asserts that the DB is to generate the expected attributes. """

        if self.returns is None:
            return

        if len(self.returns) == 1:
            assert f"RETURNING {self.table_name}.{self.returns[0]}" in stmt


class TestUserHandling:
    def test_insert_user_into_db(self, engine_fixture):
        """ Tests a happy path for user insertion. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                params_user = {
                    'username': 'Dave',
                    'hashed_password': DoNotTestMe(),
                    'email': 'david@goliath.com',
                    'full_name': "David Goliath"
                }

                usf = UserSignupForm(
                    username=params_user['username'],
                    password='dave',
                    email=params_user['email'],
                    full_name=params_user['full_name']
                )

                insert_user_into_db(session, usf)
                session.flush()

        insertion_assertions = InsertionAssertions(
            table_name=UserOrm.__tablename__,
            params=params_user,
            returns=['id']
        )

        captured: list[tuple[str, dict]]
        for stmt, params in captured:
            if insertion_assertions.is_insert(stmt):
                insertion_assertions.assert_values(stmt)
                insertion_assertions.assert_params(params)
                insertion_assertions.assert_returns(stmt)
                break  # No more assertions to make

    # Other invalids prevented by endpoint/UI
    def test_insert_user_into_db_duplicate(self):
        """ Tests inserting a duplicate user. """

        usf = UserSignupForm(
            username='Bob',
            password='builder',
            email='bob@webuild.com',
            full_name='Robert Builder'
        )

        with Session() as session:
            insert_user_into_db(session, usf)
            try:
                session.flush()
            except IntegrityError as e:
                assert isinstance(e.orig, errors.lookup(UNIQUE_VIOLATION))

    def test_select_user_by_username(self, engine_fixture):
        """ Tests the user selector. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                selection = select_user_by_username(session, 'Bob')

        assert 'SELECT' in captured[0][0]
        assert f"WHERE {UserOrm.__tablename__}.username =" in captured[0][0]
        assert selection.username == 'Bob'

    def test_get_username_by_id(self, engine_fixture):
        """ Tests the username-by-id selector. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                selection = get_username_by_id(session, 2)

        assert 'SELECT' in captured[0][0]
        assert f"WHERE {UserOrm.__tablename__}.id =" in captured[0][0]
        assert selection == 'Alice'

    def test_select_all_users(self, engine_fixture):
        """ Tests the selection of all users. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                select_all_users(session)

        assert 'SELECT' in captured[0][0]
        assert f"FROM {UserOrm.__tablename__}" in captured[0][0]


class TestTokenHandling:
    def test_insert_token_into_db(self, engine_fixture):
        """ Tests inserting a token. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                expires = dt.datetime.now(tz=dt.timezone.utc)
                expires += dt.timedelta(minutes=60)
                token_params = {
                    'id': 'dummy_token_id',
                    'user_id': 1,
                    'expire': expires
                }

                token_data = TokenData(
                    username='Bob',
                    expire=expires,
                    id=token_params['id']
                )
                insert_token_into_db(session, token_data)
                session.flush()
                delete_token_from_db(session, token_data)
                session.commit()

        insertion_assertions = InsertionAssertions(
            table_name=TokenOrm.__tablename__,
            params=token_params
        )

        captured: list[tuple[str, dict]]
        for stmt, params in captured:
            if insertion_assertions.is_insert(stmt):
                insertion_assertions.assert_values(stmt)
                insertion_assertions.assert_params(params)
                break  # No more assertions to make

    def test_revoke_token(self, engine_fixture):
        """ Tests token revocation, the main part of logging out a user. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                expires = dt.datetime.now(tz=dt.timezone.utc)
                expires += dt.timedelta(minutes=60)
                token_params = {
                    'id': 'dummy_token_id'
                }
                token_data = TokenData(
                    username='Bob',
                    expire=expires,
                    id=token_params['id']
                )
                insert_token_into_db(session, token_data)
                revoke_token(session, token_data)
                delete_token_from_db(session, token_data)
                session.commit()

        insertion_assertions = InsertionAssertions(
            table_name=RevokedTokenOrm.__tablename__,
            params=token_params
        )

        captured: list[tuple[str, dict]]
        for stmt, params in captured[::-1]:
            if insertion_assertions.is_insert(stmt):
                insertion_assertions.assert_values(stmt)
                insertion_assertions.assert_params(params)
                break  # No more assertions to make

    def test_revoke_token_without_insertion(self, engine_fixture):
        """ Tests revoking a non-existent token. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                expires = dt.datetime.now(tz=dt.timezone.utc)
                expires += dt.timedelta(minutes=60)
                token_data = TokenData(
                    username='Bob',
                    expire=expires,
                    id='dummy_token_id'
                )
                try:
                    revoke_token(session, token_data)
                except IntegrityError as e:
                    assert isinstance(
                        e.orig, errors.lookup(FOREIGN_KEY_VIOLATION)
                    )

    def test_delete_token_from_db_by_id(self, engine_fixture):
        """ Tests deleting a token by token ID. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                expires = dt.datetime.now(tz=dt.timezone.utc)
                expires += dt.timedelta(minutes=60)
                token_params = {
                    'id': 'dummy_token_id',
                    'user_id': 1,
                    'expire': expires
                }

                token_data = TokenData(
                    username='Bob',
                    expire=expires,
                    id=token_params['id']
                )
                insert_token_into_db(session, token_data)
                session.flush()
                delete_token_from_db(session, token_data)
                session.commit()

        deletion_stmt_start = f"DELETE FROM {TokenOrm.__tablename__}"\
                              f" WHERE {TokenOrm.__tablename__}.id ="
        assert any(stmt.startswith(deletion_stmt_start) for stmt, _ in captured)

    def test_delete_token_from_db_by_username(self, engine_fixture):
        """ Tests deleting a token by username. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                expires = dt.datetime.now(tz=dt.timezone.utc)
                expires += dt.timedelta(minutes=60)
                token_params = {
                    'id': 'dummy_token_id',
                    'user_id': 1,
                    'expire': expires
                }

                token_data = TokenData(
                    username='Bob',
                    expire=expires,
                    id=token_params['id']
                )
                insert_token_into_db(session, token_data)
                session.flush()
                delete_token_from_db(session, token_data, by_username=True)
                session.commit()

        del_stmt_start = f"DELETE FROM {TokenOrm.__tablename__} WHERE EXISTS"
        del_stmt_from = f"FROM {TokenOrm.__tablename__}"
        del_stmt_where = f"WHERE {UserOrm.__tablename__}.id = " \
                         f"{TokenOrm.__tablename__}.user_id"

        assert any(stmt.startswith(del_stmt_start) for stmt, _ in captured)
        assert any(del_stmt_from in stmt for stmt, _ in captured)
        assert any(del_stmt_where in stmt for stmt, _ in captured)


class TestProjectHandling:
    def test_insert_project(self, engine_fixture):
        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                owner = select_user_by_username(session, 'Bob')

                params_project = {
                    'name': "Test project",
                    'description': "Just a test",
                    'created_at': dt.datetime.now(tz=dt.timezone.utc)
                }
                params_user_project = {
                    'user_id': 1,
                    'project_id': DoNotTestMe(),
                    'role': 'Owner'
                }
                project = Project(
                    name=params_project['name'],
                    description=params_project['description'],
                    owner=owner,
                    created_at=params_project['created_at'],
                    participants=[owner],
                )
                project_orm = insert_project_into_db(session, project)
                session.commit()  # Removes the folder further down
                delete_project_from_db(session, project_orm.id)
                session.commit()

        insertion_assertions_coll = [
            InsertionAssertions(
                table_name=ProjectOrm.__tablename__,
                params=params_project,
                returns=['id']
            ),
            InsertionAssertions(
                table_name=UserProjectOrm.__tablename__,
                params=params_user_project
            ),
        ]

        ia_idx = 0
        captured: list[tuple[str, dict]]
        for stmt, params in captured:
            try:
                insertion_assertions = insertion_assertions_coll[ia_idx]
            except IndexError:
                break  # No more assertions to make

            if insertion_assertions.is_insert(stmt):
                insertion_assertions.assert_values(stmt)
                insertion_assertions.assert_params(params)
                insertion_assertions.assert_returns(stmt)
                ia_idx += 1

    def test_select_project_by_id(self, engine_fixture):
        """ Tests the project selector. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                selection = select_project_by_id(session, 1)

        assert 'SELECT' in captured[0][0]
        assert f"FROM {ProjectOrm.__tablename__}" in captured[0][0]
        assert f"WHERE {ProjectOrm.__tablename__}.id =" in captured[0][0]
        assert selection.id == 1

    def test_select_all_project_owners(self, engine_fixture):
        """ Tests selecting all project owners. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                selection = select_all_project_owners(session)

        assert 'SELECT' in captured[0][0]
        assert f"FROM {UserProjectOrm.__tablename__}" in captured[0][0]
        assert f"WHERE {UserProjectOrm.__tablename__}.role =" in captured[0][0]
        assert len(list(selection.keys())) == 2
        assert selection[1].username == 'Bob'
        assert selection[2].username == 'Alice'

    def test_select_all_projects(self, engine_fixture):
        """ Tests selecting all the projects. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                select_all_projects(session)

        assert 'SELECT' in captured[0][0]
        assert f"FROM {ProjectOrm.__tablename__}" in captured[0][0]
        assert f"ORDER BY {ProjectOrm.__tablename__}.id" in captured[0][0]

    def test_delete_project_from_db(self, engine_fixture):
        """ Tests deleting a project from the database. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                owner = select_user_by_username(session, 'Bob')
                project = Project(
                    name="Test project",
                    description="Just a test",
                    owner=owner,
                    created_at=dt.datetime.now(tz=dt.timezone.utc),
                    participants=[owner],
                )
                project_orm = insert_project_into_db(session, project)
                session.commit()

                delete_project_from_db(session, project_orm.id)
                session.commit()

        del_stmt_start = f"DELETE FROM {ProjectOrm.__tablename__}"
        del_stmt_where = f"WHERE {ProjectOrm.__tablename__}.id ="
        assert captured[-1][0].startswith(del_stmt_start)
        assert del_stmt_where in captured[-1][0]

    def test_update_project_info_in_db(self, engine_fixture):
        """ Tests updating a project's basic information in the database. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                update_project_info_in_db(session, 1, ProjectInfo(
                    name='NAME',
                    description='DESC'
                ))
                session.flush()

        assert captured[0][0].startswith(f"UPDATE {ProjectOrm.__tablename__}")
        assert 'SET' in captured[0][0]
        assert f"WHERE {ProjectOrm.__tablename__}.id =" in captured[0][0]

    @pytest.mark.asyncio
    async def test_insert_document_into_db(self, engine_fixture):
        """ Tests inserting a valid document into the database. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                async with LocalFileAsUploadFile('default.png') as u_file:
                    params_doc = {
                        'project_id': 1,
                        'path': 'default.png',
                        'size_bytes': 643,
                        'uploaded_by_user_id': 1,
                        'uploaded_by_username': 'Bob',
                        'created_at': DoNotTestMe()
                    }
                    document = Document(
                        project_id=1,
                        path='default.png',
                        size_bytes=-1,
                        uploaded_by_user_id=-1,
                        uploaded_by_username='',
                        created_at=dt.datetime.now(tz=dt.timezone.utc)
                    )
                    document.uploaded_by_user_id = 1
                    document.uploaded_by_username = 'Bob'
                    document.size_bytes = os.path.getsize(
                        os.path.join(DUMMY_FILES, u_file.filename)
                    )
                    insert = insert_document_into_db(session, document, u_file)
                    session.commit()
                    delete_document_from_db(session, insert.id)
                    session.commit()

        insertion_assertions = InsertionAssertions(
            table_name=DocumentOrm.__tablename__,
            params=params_doc,
            returns=['id']
        )

        if insertion_assertions.is_insert(captured[0][0]):
            insertion_assertions.assert_values(captured[0][0])
            insertion_assertions.assert_params(captured[0][1])
            insertion_assertions.assert_returns(captured[0][0])

    @pytest.mark.asyncio
    async def test_insert_document_into_db_duplicate(self, engine_fixture):
        """ Tests inserting a duplicate document into the database. """

        # Other invalids prevented by endpoint/UI
        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                async with LocalFileAsUploadFile('default.png') as u_file:
                    document = Document(
                        project_id=1,
                        path='default.png',
                        size_bytes=-1,
                        uploaded_by_user_id=-1,
                        uploaded_by_username='',
                        created_at=dt.datetime.now(tz=dt.timezone.utc)
                    )
                    document.uploaded_by_user_id = 1
                    document.uploaded_by_username = 'Bob'
                    document.size_bytes = os.path.getsize(
                        os.path.join(DUMMY_FILES, u_file.filename)
                    )
                    insert = insert_document_into_db(session, document, u_file)
                    session.commit()
                    try:
                        insert_document_into_db(session, document, u_file)
                        session.commit()
                    except IntegrityError as e:
                        assert isinstance(
                            e.orig, errors.lookup(UNIQUE_VIOLATION)
                        )

                    session.rollback()
                    delete_document_from_db(session, insert.id)
                    session.commit()

    def test_select_document_by_id(self, engine_fixture):
        """ Tests the document selector. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                selection = select_document_by_id(session, 2)

        assert captured[0][0].startswith('SELECT')
        assert f"FROM {DocumentOrm.__tablename__}" in captured[0][0]
        assert f"WHERE {DocumentOrm.__tablename__}.id =" in captured[0][0]
        assert selection.id == 2

    @pytest.mark.asyncio
    async def test_update_document_in_db(self, engine_fixture):
        """ Tests updating a document in the database. """

        with Session() as session:
            async with LocalFileAsUploadFile('default.png') as u_file_1:
                document_1 = Document(
                    project_id=1,
                    path='default.png',
                    size_bytes=-1,
                    uploaded_by_user_id=-1,
                    uploaded_by_username='',
                    created_at=dt.datetime.now(tz=dt.timezone.utc)
                )
                document_1.uploaded_by_user_id = 1
                document_1.uploaded_by_username = 'Bob'
                document_1.size_bytes = os.path.getsize(
                    os.path.join(DUMMY_FILES, u_file_1.filename)
                )
                insert = insert_document_into_db(
                    session, document_1, u_file_1
                )
                session.commit()

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                async with LocalFileAsUploadFile('default.png') as u_file_2:
                    document_2 = Document(
                        project_id=1,
                        path='default.txt',
                        size_bytes=-1,
                        uploaded_by_user_id=-1,
                        uploaded_by_username='',
                        created_at=dt.datetime.now(tz=dt.timezone.utc)
                    )
                    document_2.uploaded_by_user_id = 1
                    document_2.uploaded_by_username = 'Bob'
                    document_2.size_bytes = os.path.getsize(
                        os.path.join(DUMMY_FILES, u_file_2.filename)
                    )

                    update_document_in_db(
                        session, insert.id, document_2, u_file_2
                    )
                    session.commit()

                    delete_document_from_db(session, insert.id)
                    session.commit()

        update_stmt_start = f"UPDATE {DocumentOrm.__tablename__} SET"
        update_stmt_where = f"WHERE {DocumentOrm.__tablename__}.id ="
        assert captured[0][0].startswith(update_stmt_start)
        assert update_stmt_where in captured[0][0]

    @pytest.mark.asyncio
    async def test_delete_document_from_db(self, engine_fixture):
        """ Tests deleting a document from the database. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                async with LocalFileAsUploadFile('default.png') as u_file:
                    params_doc = {
                        'project_id': 1,
                        'path': 'default.png',
                        'size_bytes': 643,
                        'uploaded_by_user_id': 1,
                        'uploaded_by_username': 'Bob',
                        'created_at': DoNotTestMe()
                    }
                    document = Document(
                        project_id=1,
                        path='default.png',
                        size_bytes=-1,
                        uploaded_by_user_id=-1,
                        uploaded_by_username='',
                        created_at=dt.datetime.now(tz=dt.timezone.utc)
                    )
                    document.uploaded_by_user_id = 1
                    document.uploaded_by_username = 'Bob'
                    document.size_bytes = os.path.getsize(
                        os.path.join(DUMMY_FILES, u_file.filename)
                    )
                    insert = insert_document_into_db(session, document, u_file)
                    session.commit()
                    delete_document_from_db(session, insert.id)
                    session.commit()

        del_stmt_start = f"DELETE FROM {DocumentOrm.__tablename__}" \
                         f" WHERE {DocumentOrm.__tablename__}.id ="
        assert captured[-1][0].startswith(del_stmt_start)


class TestUserProjectParticipation:
    def test_invite_user_to_project(self, engine_fixture):
        """ Tests user invitation to project. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                alice = select_user_by_username(session, 'Alice')
                invite_user_to_project(session, 1, alice)
                session.commit()
                remove_user_from_project(session, 1, 'Alice')

        params_user_project = {
            'user_id': 2,
            'project_id': 1,
            'role': 'Contributor'
        }
        insertion_assertions = InsertionAssertions(
            table_name=UserProjectOrm.__tablename__,
            params=params_user_project
        )

        for stmt, params in captured:
            if insertion_assertions.is_insert(stmt):
                insertion_assertions.assert_values(stmt)
                insertion_assertions.assert_params(params)

    def test_remove_user_from_project(self, engine_fixture):
        """ Tests user removal from project. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                alice = select_user_by_username(session, 'Alice')
                invite_user_to_project(session, 1, alice)
                session.commit()
                remove_user_from_project(session, 1, 'Alice')

        del_stmt_start = f"DELETE FROM {UserProjectOrm.__tablename__}" \
                         f" WHERE {UserProjectOrm.__tablename__}.user_id ="
        assert captured[-1][0].startswith(del_stmt_start)

    def test_select_project_participants(self, engine_fixture):
        """ Tests the collection of project's participants. """

        with (capture_sql_executed(engine_fixture) as captured):
            with Session() as session:
                select_project_participants(session, 1)

            selection_stmt_from = f"FROM {UserProjectOrm.__tablename__}"
            selection_stmt_where = f"WHERE {UserProjectOrm.__tablename__}" \
                                   f".project_id ="
            assert captured[0][0].startswith('SELECT')
            assert selection_stmt_from in captured[0][0]
            assert selection_stmt_where in captured[0][0]

    def test_select_user_projects(self, engine_fixture):
        """ Tests the collection of a user's projects. """

        with capture_sql_executed(engine_fixture) as captured:
            with Session() as session:
                select_user_projects(session, 1)

        selection_stmt_from = f"FROM {UserProjectOrm.__tablename__}"
        selection_stmt_where = f"WHERE {UserProjectOrm.__tablename__}" \
                               f".user_id ="
        assert captured[0][0].startswith('SELECT')
        assert selection_stmt_from in captured[0][0]
        assert selection_stmt_where in captured[0][0]

