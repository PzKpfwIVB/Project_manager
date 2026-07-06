import asyncio
import datetime as dt
import os
import shutil
from types import TracebackType
from typing import Type

from fastapi import UploadFile

from application.db.crud import (
    insert_document_into_db,
    insert_project_into_db,
    insert_user_into_db,
    invite_user_to_project,
    select_user_by_username
)
from application.core.config import DUMMY_FILES, FILE_STORAGE
from application.db.session import Session
from application.schemas.document import Document
from application.schemas.project import Project
from application.schemas.user import UserSignupForm


class LocalFileAsUploadFile:
    def __init__(self, filename: str):
        self._filename = filename
        self._file_path = os.path.join(DUMMY_FILES, filename)
        self._file = None
        self._upload_file: UploadFile | None = None

    async def __aenter__(self) -> UploadFile:
        self._file = open(self._file_path, 'rb')
        self._upload_file = UploadFile(filename=self._filename, file=self._file)
        return self._upload_file

    async def __aexit__(
            self,
            exc_type: Type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: TracebackType | None,
    ) -> None:
        if self._upload_file is not None:
            await self._upload_file.close()
        elif self._file is not None:
            self._file.close()

        self._upload_file = None
        self._file = None


def initialize_users() -> None:
    with Session() as session:
        insert_user_into_db(
            session,
            UserSignupForm(
                username='Bob',
                password='builder',
                email='bob@webuild.com',
                full_name="Robert Builder"
            )
        )
        session.commit()

        insert_user_into_db(
            session,
            UserSignupForm(
                username='Alice',
                password='wonderland',
                email='alice@wonderland.com',
                full_name="Alice Wonderland"
            )
        )
        session.commit()

        insert_user_into_db(
            session,
            UserSignupForm(
                username='EVE',
                password='robot',
                email='eve@plant.com',
                full_name="Eve Probe"
            )
        )
        session.commit()


def initialize_projects() -> int:
    for directory in os.listdir(FILE_STORAGE):
        shutil.rmtree(os.path.join(FILE_STORAGE, directory))

    with Session() as session:
        alice = select_user_by_username(session, 'Alice')
        bob = select_user_by_username(session, 'Bob')

        insert_project_into_db(session, Project(
            name="Project Projectsson",
            description="Descriptionsson",
            owner=bob,
            created_at=dt.datetime.now(tz=dt.timezone.utc),
            participants=[bob]
        ))
        session.commit()

        project = insert_project_into_db(session, Project(
            name="Project 2",
            description="Second project",
            owner=alice,
            created_at=dt.datetime.now(tz=dt.timezone.utc),
            participants=[alice]
        ))
        session.commit()

        invite_user_to_project(session, project.id, bob)
        session.commit()

        return project.id


async def initialize_files(project_id: int):
    td_1 = dt.timedelta(days=1, hours=2, minutes=3, seconds=4, microseconds=567)
    td_2 = dt.timedelta(hours=3, minutes=45, seconds=26, microseconds=1789)

    document_1 = Document(
        project_id=project_id,
        path='default.png',
        size_bytes=-1,
        uploaded_by_user_id=-1,
        uploaded_by_username='',
        created_at=dt.datetime.now(tz=dt.timezone.utc) - td_1
    )

    document_2 = Document(
        project_id=project_id,
        path='default.txt',
        size_bytes=-1,
        uploaded_by_user_id=-1,
        uploaded_by_username='',
        created_at=dt.datetime.now(tz=dt.timezone.utc) - td_2
    )

    with Session() as session:
        bob = select_user_by_username(session, 'Bob')
        eve = select_user_by_username(session, 'EVE')

        async with LocalFileAsUploadFile(filename='default.png') as u_file_1:
            document_1.uploaded_by_user_id = bob.id
            document_1.uploaded_by_username = bob.username
            document_1.size_bytes = os.path.getsize(
                os.path.join(DUMMY_FILES, u_file_1.filename)
            )
            insert_document_into_db(session, document_1, u_file_1)
            session.commit()

        async with LocalFileAsUploadFile(filename='default.txt') as u_file_2:
            document_2.uploaded_by_user_id = eve.id
            document_2.uploaded_by_username = eve.username
            document_2.size_bytes = os.path.getsize(
                os.path.join(DUMMY_FILES, u_file_2.filename)
            )
            insert_document_into_db(session, document_2, u_file_2)
            session.commit()


async def main():
    initialize_users()
    proj_id = initialize_projects()
    await initialize_files(proj_id)

if __name__ == '__main__':
    asyncio.run(main())
