import datetime as dt
import logging
import shutil
import os

from pwdlib import PasswordHash

from sqlalchemy import and_, delete, select, update
from sqlalchemy.orm import Session

from fastapi import UploadFile

from application.core.config import FILE_STORAGE
from application.schemas.document import Document
from application.schemas.project import Project, Role, ProjectInfo
from application.schemas.project_participants import ProjectParticipants
from application.schemas.token_data import TokenData
from application.schemas.user import User, UserSignupForm
from application.schemas.user_projects import UserProjects

from application.db.declarative_mapping import (
    DocumentOrm,
    ProjectOrm,
    RevokedTokenOrm,
    TokenOrm,
    UserProjectOrm,
    UserOrm
)


password_hash = PasswordHash.recommended()


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
)


def insert_user_into_db(
        session: Session,
        user_signup_form: UserSignupForm
) -> User:
    """ Inserts a new user into the database. """

    logging.info(f"Signing up new user '{user_signup_form.username}'")

    user_orm = UserOrm(
        username=user_signup_form.username,
        hashed_password=password_hash.hash(user_signup_form.password),
        email=user_signup_form.email,
        full_name=user_signup_form.full_name
    )
    session.add(user_orm)
    session.commit()

    return User.from_orm(user_orm)


def log_user_out(session: Session, username: str) -> None:
    """ Revokes a user's token. """

    logging.info(f"Logging out user '{username}'")
    user = select_user_by_username(session, username)
    revoke_token(session, user.token_data)


def select_user_by_username(
        session: Session,
        username: str,
        get_orm_model: bool = False
) -> User | None:
    """
    Searches for a user in the DB by username and returns None if not found.
    Can be set to return the ORM model instead with `get_orm_model`
    """

    logging.info(f"SELECT user '{username}'")

    stmt = select(UserOrm).where(UserOrm.username == username)
    user_orm = session.execute(stmt).scalar_one_or_none()
    if get_orm_model:
        return user_orm

    return None if user_orm is None else User.from_orm(user_orm)


def get_username_by_id(session: Session, user_id: int) -> str | None:
    """ Gets the username belonging to the user of the requested ID. """

    logging.info(f"SELECT user.username WHERE id == {user_id}")

    stmt = select(UserOrm.username).where(UserOrm.id == user_id)
    username = session.execute(stmt).scalar_one_or_none()

    return username


def select_all_users(session: Session) -> list[User]:
    """ Selects all users from the database. """

    logging.info("SELECT all users")

    stmt = select(UserOrm)
    user_orm_list = session.execute(stmt).all()  # [(UserOrm,), ...]

    return [User.from_orm(user_orm_tup[0]) for user_orm_tup in user_orm_list]


def _purge_expired_tokens(session: Session):
    """
    Removes expired tokens as they are now invalid. Run on each token operation.
    """

    logging.info("Purging expired tokens")

    subquery = (
        select(RevokedTokenOrm.id)
        .where(
            # match only revoked tokens whose referenced token is expired
            select(TokenOrm.expire)
            .where(TokenOrm.id == RevokedTokenOrm.id)
            .scalar_subquery() <= dt.datetime.now(tz=dt.timezone.utc)
        )
    )

    session.execute(
        delete(TokenOrm).where(TokenOrm.id.in_(subquery))
    )
    session.commit()


def insert_token_into_db(session: Session, token: TokenData) -> TokenData:
    """ Inserts a new token into the database. """

    logging.info("Persisting a token")
    user_orm = select_user_by_username(
        session, token.username, get_orm_model=True
    )
    token_orm = TokenOrm(
        id=token.id,
        user_id=user_orm.id,
        expire=token.expire
    )

    session.add(token_orm)
    session.commit()

    _purge_expired_tokens(session)

    return TokenData.from_orm(token_orm)


def delete_token_from_db(
        session: Session,
        token: TokenData,
        by_username=False
) -> None:
    """
    Removes a token by ID from the database, cascading to removed ones.
    By default, it uses the ID of the token to match on, but it can be set to
    use the username instead.
    """

    logging.info("Deleting a token")

    stmt = delete(TokenOrm).where(TokenOrm.id == token.id)
    if by_username:
        stmt = (
            delete(TokenOrm)
            .where(TokenOrm.user.has(UserOrm.username == token.username))
        )

    session.execute(stmt)
    session.commit()

    _purge_expired_tokens(session)


def is_token_revoked(session: Session, token: TokenData) -> bool:
    """ Checks if a given token is among the revoked tokens. """

    logging.info("Checking a token for revocation status")

    _purge_expired_tokens(session)

    stmt = select(RevokedTokenOrm).where(RevokedTokenOrm.id == token.id)
    revoked_token = session.execute(stmt).scalar_one_or_none()

    return revoked_token is not None


def revoke_token(session: Session, token: TokenData) -> None:
    """ Revokes a token to invalidate it before it expires. """

    logging.info("Revoking a token")

    revoked_token_orm = RevokedTokenOrm(id=token.id)
    session.add(revoked_token_orm)
    session.commit()

    _purge_expired_tokens(session)


def insert_project_into_db(session: Session, project: Project) -> Project:
    """ Inserts a new project into the database. """

    logging.info(f"Persisting a project: {project}")
    project_orm = ProjectOrm(
        name=project.name,
        description=project.description,
        created_at=project.created_at
    )

    session.add(project_orm)
    session.flush()

    user_orm = select_user_by_username(
        session, project.owner.username, get_orm_model=True
    )
    user_project_orm = UserProjectOrm(
        user_id=user_orm.id,
        project_id=project_orm.id,
        role=Role.OWNER.value
    )
    session.add(user_project_orm)
    session.commit()

    os.mkdir(os.path.join(FILE_STORAGE, str(project_orm.id)))

    return Project.from_orm_custom(project_orm)


def select_project_by_id(session: Session, project_id: int) -> Project | None:
    """
    Searches for a project in the database by ID and returns None if not found.
    """

    logging.info(f"SELECT project WHERE id == {project_id}")

    project_orm = session.get(ProjectOrm, project_id)
    if project_orm is not None:
        project_participants = select_project_participants(session, project_id)
        return Project.from_orm_custom(
            project_orm,
            project_participants=project_participants
        )

    return


def select_all_project_owners(session: Session) -> dict[int, User]:
    """
    Selects the owners of each project and returns the pairs of project ID and
    project owner.
    """

    logging.info("SELECT all project owners")
    stmt = (select(UserProjectOrm)
            .where(UserProjectOrm.role == Role.OWNER.value)
            .order_by(UserProjectOrm.project_id)
            )
    up_orm_list = session.execute(stmt).all()

    return {up_orm_tuple[0].project_id: up_orm_tuple[0].user
            for up_orm_tuple in up_orm_list}


def select_all_projects(session: Session) -> list[Project]:
    """ Selects all projects from the database. """

    logging.info("SELECT all projects")

    stmt = select(ProjectOrm).order_by(Project.id)
    project_orm_list = session.execute(stmt).all()  # [(ProjectOrm,), ...]
    project_owners = select_all_project_owners(session)

    return [Project.from_orm_custom(project_orm_tup[0], owner=owner)
            for project_orm_tup, owner
            in zip(project_orm_list, project_owners.values())]


def delete_project_from_db(session: Session, project_id: int) -> None:
    """ Deletes a project from the DB, along with its associated documents. """

    logging.info(f"Deleting project of ID {project_id}")

    stmt = delete(ProjectOrm).where(ProjectOrm.id == project_id)
    session.execute(stmt)
    session.commit()

    shutil.rmtree(os.path.join(FILE_STORAGE, str(project_id)))


def update_project_info_in_db(
        session: Session,
        project_id: int,
        project_info: ProjectInfo
) -> None:
    """ Updates the name and/or description of the requested project. """

    stmt = update(ProjectOrm).where(ProjectOrm.id == project_id).values(
        name=project_info.name,
        description=project_info.description
    )
    session.execute(stmt)
    session.commit()


def insert_document_into_db(
        session: Session,
        document: Document,
        file: UploadFile
) -> Document:
    """ Inserts a new document into the database. """

    logging.info(f"INSERT document: {document}")

    doc_orm = DocumentOrm(
        project_id=document.project_id,
        path=document.path,
        size_bytes=document.size_bytes,
        uploaded_by_user_id=document.uploaded_by_user_id,
        uploaded_by_username=document.uploaded_by_username,
        created_at=document.created_at
    )
    session.add(doc_orm)
    session.commit()

    target_path = os.path.join(
        FILE_STORAGE,
        str(document.project_id),
        f'{doc_orm.id}__{document.path}'
    )
    with open(target_path, 'wb') as out_file:
        shutil.copyfileobj(file.file, out_file)

    file.close()

    return Document.from_orm(doc_orm)


def select_document_by_id(
        session: Session,
        document_id: int
) -> Document:
    """ Selects a document from the database by ID. """

    logging.info(f"SELECT document WHERE id == {document_id}")
    stmt = select(DocumentOrm).where(DocumentOrm.id == document_id)
    doc_orm = session.execute(stmt).scalar_one_or_none()

    return Document.from_orm(doc_orm)


def update_document_in_db(
        session: Session,
        original_id: int,
        document: Document,
        file: UploadFile
) -> None:
    """ Updates a document in the database. """

    logging.info(f"UPDATE document WHERE id == {original_id} BY {document}")

    stmt = update(DocumentOrm).where(DocumentOrm.id == original_id).values(
        path=document.path,
        size_bytes=document.size_bytes,
        uploaded_by_user_id=document.uploaded_by_user_id,
        uploaded_by_username=document.uploaded_by_username,
        created_at=document.created_at
    )
    session.execute(stmt)
    session.commit()

    # Remove the old file first
    project_dir = os.path.join(
        FILE_STORAGE,
        str(document.project_id)
    )
    file_rel_paths = os.listdir(project_dir)
    for file_rel_path in file_rel_paths:
        if file_rel_path.startswith(f"{original_id}__"):
            os.remove(os.path.join(project_dir, file_rel_path))

    target_path = os.path.join(
        FILE_STORAGE,
        str(document.project_id),
        f'{original_id}__{document.path}'
    )
    with open(target_path, 'wb') as out_file:
        shutil.copyfileobj(file.file, out_file)

    file.close()


def delete_document_from_db(session: Session, document_id: int) -> None:
    """ Deletes a document from the database by ID. """

    logging.info(f"DELETE document WHERE id == {document_id}")

    doc_orm = select_document_by_id(session, document_id)

    stmt = delete(DocumentOrm).where(DocumentOrm.id == document_id)
    session.execute(stmt)
    session.commit()

    removal_path = os.path.join(
        FILE_STORAGE,
        str(doc_orm.project_id),
        f"{doc_orm.id}__{doc_orm.path}",
    )
    os.remove(removal_path)


def invite_user_to_project(
        session: Session,
        project_id: int,
        user: User
) -> None:
    """ Adds a user to the requested project as a contributor. """

    logging.info(f"Inviting {user.username} to the project of ID {project_id}")
    session.add(
        UserProjectOrm(
            user_id=user.id,
            project_id=project_id,
            role=Role.CONTRIBUTOR.value
        )
    )
    session.commit()


def remove_user_from_project(
        session: Session,
        project_id: int,
        username: str
) -> None:
    """ Removes a contributor from the requested project. """

    logging.info(f"REMOVE {username} WHERE project.id == {project_id}")
    user = select_user_by_username(session, username)
    stmt = delete(UserProjectOrm).where(
        and_(
            UserProjectOrm.user_id == user.id,
            UserProjectOrm.project_id == project_id
        )
    )
    session.execute(stmt)
    session.commit()


def select_project_participants(
        session: Session,
        project_id: int
) -> ProjectParticipants:
    """ Returns the participants of the requested project with their role. """

    logging.info(f"SELECT participants WHERE project.id == {project_id}")
    stmt = select(UserProjectOrm).where(UserProjectOrm.project_id == project_id)
    user_project_orm_list = session.execute(stmt).all()

    return ProjectParticipants.from_orm(user_project_orm_list)


def select_user_projects(
        session: Session,
        user_id: int
) -> UserProjects:
    """
    Returns the projects associated with the requested user with their role in
    each project.
    """

    logging.info(f"SELECT projects OF user WHERE user.id == {user_id}")
    stmt = select(UserProjectOrm).where(UserProjectOrm.user_id == user_id)
    user_project_orm_list = session.execute(stmt).all()
    project_owners = select_all_project_owners(session)

    return UserProjects.from_orm_custom(user_project_orm_list, project_owners)
