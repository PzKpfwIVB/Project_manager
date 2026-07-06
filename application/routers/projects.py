import datetime as dt
import os.path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Request,
    status,
    UploadFile,
)
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from application.core.config import FILE_STORAGE
from application.core.security import auth_required
from application.db.crud import (
    delete_document_from_db,
    delete_project_from_db,
    invite_user_to_project,
    insert_document_into_db,
    insert_project_into_db,
    remove_user_from_project,
    select_all_users,
    select_document_by_id,
    select_project_by_id,
    select_project_participants,
    select_user_by_username,
    select_user_projects,
    update_document_in_db,
    update_project_info_in_db
)
from application.db.session import SessionDependency
from application.schemas.document import ALLOWED_MIME_TYPES, Document
from application.schemas.project import ProjectInfo, Project
from application.schemas.redirect_context_message import RedirectContextMessage
from application.schemas.user import User


router = APIRouter(tags=['projects'], dependencies=[Depends(auth_required)])
templates = Jinja2Templates(directory='application/templates')


def check_document_validity(file: UploadFile) -> RedirectContextMessage:
    """ Checks if the document is valid for uploading. """

    msg = RedirectContextMessage(is_error=True, content='')
    if file.content_type not in ALLOWED_MIME_TYPES:
        msg.content = "Unsupported file type"
    elif file.size > 5 * 1024 * 1024:
        msg.content = "File size must not exceed 5 MB"
    else:
        msg.is_error = False

    return msg


@router.get('/projects', response_class=HTMLResponse)
async def get_projects_dashboard(
        session: SessionDependency,
        request: Request,
        user: Annotated[User, Depends(auth_required)],
        message: RedirectContextMessage = Depends()
):
    return templates.TemplateResponse(
        request=request,
        name='projects/dashboard.html',
        context={
            'projects': select_user_projects(session, user.id).all_projects,
            'current_user': user,
            'message': message
        }
    )


@router.get('/projects/', response_class=HTMLResponse)
async def get_project_creator_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name='projects/project_editor.html',
        context={
            'project': ProjectInfo(),
            'message': RedirectContextMessage(),
            'operation': 'create'
        }
    )


@router.post('/projects')
async def create_new_project(
        session: SessionDependency,
        project_info: ProjectInfo = Form(),
        user: User = Depends(auth_required)
):
    insert_project_into_db(session, Project(
        name=project_info.name,
        description=project_info.description,
        owner=user,
        created_at=dt.datetime.now(tz=dt.timezone.utc),
        participants=[user]
    ))
    session.commit()

    msg = RedirectContextMessage(
        is_error=False,
        content="Project created successfully"
    )
    return RedirectResponse(
        url=f'/projects?{msg.urlencoded}',
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.get('/projects/{project_id}/info', response_class=HTMLResponse)
async def get_project_info_page(
        session: SessionDependency,
        project_id: int,
        request: Request,
        message: RedirectContextMessage = Depends()
):
    return templates.TemplateResponse(
        request=request,
        name='projects/project_editor.html',
        context={
            'project': select_project_by_id(session, project_id),
            'message': message,
            'operation': 'update'
        }
    )


@router.post('/projects/{project_id}/info')  # Jinja2 templates have no PUT
async def update_project_info(
        session: SessionDependency,
        project_id: int,
        project_info: ProjectInfo = Form()
):
    update_project_info_in_db(session, project_id, project_info)
    session.commit()

    msg = RedirectContextMessage(
        is_error=False,
        content="Project info updated successfully"
    )
    return RedirectResponse(
        url=f'/projects/{project_id}/info?{msg.urlencoded}',
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.post('/projects/{project_id}')  # Jinja2 templates have no DELETE
async def delete_project(session: SessionDependency, project_id: int):
    delete_project_from_db(session, project_id)

    msg = RedirectContextMessage(
        is_error=False,
        content="Project deleted successfully"
    )
    return RedirectResponse(
        url=f'/projects?{msg.urlencoded}',
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.get(
    '/projects/{project_id}/documents',
    response_class=HTMLResponse,
    name='project_documents'
)
async def get_project_documents_page(
    session: SessionDependency,
    project_id: int,
    request: Request,
    message: RedirectContextMessage = Depends()
):
    return templates.TemplateResponse(
        request=request,
        name='projects/project_documents.html',
        context={
            'project': select_project_by_id(session, project_id),
            'message': message
        }
    )


@router.post('/projects/{project_id}/documents')
async def upload_document_to_project(
        session: SessionDependency,
        user: Annotated[User, Depends(auth_required)],
        project_id: int,
        file: UploadFile = File(...)
):
    msg = check_document_validity(file)
    if not msg.is_error:
        msg.content = "Document uploaded successfully"
        new_doc = Document(
            project_id=project_id,
            path=file.filename,
            size_bytes=file.size,
            uploaded_by_user_id=user.id,
            uploaded_by_username=user.username,
            created_at=dt.datetime.now(tz=dt.timezone.utc)
        )
        insert_document_into_db(session, new_doc, file)
        session.commit()

    return RedirectResponse(
        url=f'/projects/{project_id}/documents?{msg.urlencoded}',
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/projects/{project_id}/documents/{document_id}")
async def download_project_document(
        session: SessionDependency,
        project_id: int,
        document_id: int
):
    document = select_document_by_id(session, document_id)
    doc_absolute_path = os.path.join(
        FILE_STORAGE,
        str(project_id),
        f'{document_id}__{document.path}'
    )
    return FileResponse(
        path=str(doc_absolute_path),
        media_type='application/octet-stream',
        filename=document.path
    )


@router.get(
    '/projects/{project_id}/documents/{document_id}/modify',
    response_class=HTMLResponse
)
async def modify_project_document_page(
        session: SessionDependency,
        project_id: int,
        document_id: int,
        request: Request,
        message: RedirectContextMessage = Depends()
):
    """ A page for updating/deleting a document """

    return templates.TemplateResponse(
        request=request,
        name='projects/document_editor.html',
        context={
            'project': select_project_by_id(session, project_id),
            'document': select_document_by_id(session, document_id),
            'message': message
        }
    )


# Jinja2 templates have neither PUT nor DELETE, this is a workaround
@router.post('/projects/{project_id}/documents/{document_id}')
async def modify_project_document(
        session: SessionDependency,
        project_id: int,
        document_id: int,
        operation: str = Form(...),
        file: UploadFile = File(default=None),
        user: User = Depends(auth_required)
):
    msg = RedirectContextMessage(is_error=False)
    if operation == 'update':
        msg = check_document_validity(file)
        if not msg.is_error:
            msg.content = "Document updated successfully"
            doc = Document(
                project_id=project_id,
                path=file.filename,
                size_bytes=file.size,
                uploaded_by_user_id=user.id,
                uploaded_by_username=user.username,
                created_at=dt.datetime.now(tz=dt.timezone.utc)
            )
            update_document_in_db(session, document_id, doc, file)
            session.commit()
    elif operation == 'delete':
        delete_document_from_db(session, document_id)
        session.commit()
        msg.content = "Document deleted successfully"

    return RedirectResponse(
        url=f'/projects/{project_id}/documents?{msg.urlencoded}',
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.get('/projects/{project_id}/participants', name='project_participants')
async def get_project_participants_page(
        session: SessionDependency,
        project_id: int,
        request: Request,
        current_user: Annotated[User, Depends(auth_required)],
        message: RedirectContextMessage = Depends()
):
    users = select_all_users(session)
    participants = select_project_participants(session, project_id)
    users = [user for user in users if user.id not in participants.user_ids]

    return templates.TemplateResponse(
        request=request,
        name='projects/project_participants.html',
        context={
            'project': select_project_by_id(session, project_id),
            'current_user': current_user,
            'users': users,
            'participants': participants,
            'message': message
        }
    )


@router.post('/projects/{project_id}/invite')
async def project_invite_participant(
        session: SessionDependency,
        project_id: int,
        user: str = Form(...)
):
    # `user` for username, as per requested by the task
    msg = RedirectContextMessage(
        is_error=True,
        content="Please select user from the dropdown menu"
    )

    user_obj = select_user_by_username(session, user)
    if user_obj is not None:
        participants = select_project_participants(session, project_id).user_ids
        if user_obj.id not in participants:
            invite_user_to_project(session, project_id, user_obj)
            session.commit()
            msg = RedirectContextMessage(
                is_error=False,
                content=f"{user_obj.username} "
                        f"is now a participant in the project!"
            )

    return RedirectResponse(
        url=f'/projects/{project_id}/participants?{msg.urlencoded}',
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.post('/projects/{project_id}/remove')  # Jinja2 templates have no DELETE
async def project_remove_participant(
        session: SessionDependency,
        project_id: int,
        username: str = Form(...)
):
    remove_user_from_project(session, project_id, username)
    msg = RedirectContextMessage(
        is_error=False,
        content=f"{username} successfully removed from the project!"
    )
    return RedirectResponse(
        url=f'/projects/{project_id}/participants?{msg.urlencoded}',
        status_code=status.HTTP_303_SEE_OTHER
    )
