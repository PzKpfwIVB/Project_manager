import datetime as dt
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Request,
    UploadFile,
    status
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from application.core.security import auth_required
from application.schemas.project import ProjectInfo
from application.schemas.redirect_context_message import RedirectContextMessage
from application.schemas.user import User


router = APIRouter(tags=['projects'], dependencies=[Depends(auth_required)])
templates = Jinja2Templates(directory='application/templates')


ALLOWED_MIME_TYPES = [
    'application/json',
    'application/msword',
    'application/pdf',
    'application/vnd.ms-excel',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'image/jpeg',
    'image/png',
    'image/tiff',
    'text/plain',
    'text/csv',
    'text/html'
]


class Document:
    def __init__(
            self,
            project_id: int,
            name: str,
            size_bytes: int,
            uploaded_by: User,
            created_at: str
    ):
        self.project_id = project_id
        self.name = name
        self.size_bytes = size_bytes
        self.uploaded_by = uploaded_by
        self.created_at = created_at


class Project:
    def __init__(
            self,
            project_id: int,
            name: str,
            description: str,
            owner: User,
            created_at: str,
            documents: list[Document] | None,
            participants: list[User]
    ):
        self.project_id = project_id
        self.name = name
        self.description = description
        self.owner = owner
        self.created_at = created_at
        self.documents = documents if documents else []
        self.participants = participants
        self.documents_count = len(self.documents)
        self.participants_count = len(self.participants)

    def invite_participant(self, user: User):
        self.participants.append(user)
        self.participants_count = len(self.participants)

    def remove_participant(self, user: User):
        self.participants.remove(user)
        self.participants_count = len(self.participants)


dummy_users = [
    User(username='Bob'),
    User(username='Alice'),
    User(username='Eve')
]


dummy_projects = {
    1: Project(
        project_id=1,
        name="Project Projectsson",
        description="Descriptionsson",
        owner=User(username='Bob'),
        created_at="2002/02/20 02:20:22",
        documents=None,
        participants=[dummy_users[0]]
    ),
    2: Project(
        project_id=2,
        name="Project 2",
        description="Second project",
        owner=User(username='Alice'),
        created_at="2009/09/09 09:09:09",
        documents=[
            Document(
                project_id=2,
                name='proj2.proj',
                size_bytes=234,
                uploaded_by=User(username='Bob'),
                created_at="2010/10/10 10:10:10"
            ),
            Document(
                project_id=2,
                name='test.txt',
                size_bytes=345,
                uploaded_by=User(username='Bob'),
                created_at="2011/11/11 11:11:11"
            )
        ],
        participants=dummy_users[0:2]
    )
}


@router.get('/projects', response_class=HTMLResponse)
async def get_projects_dashboard(
        request: Request,
        user: Annotated[User, Depends(auth_required)],
        message: RedirectContextMessage = Depends()
):
    return templates.TemplateResponse(
        request=request,
        name='projects/dashboard.html',
        context={
            'projects': list(dummy_projects.values()),
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
        project_info: ProjectInfo = Form(),
        user: User = Depends(auth_required)
):
    new_project = Project(
        project_id=list(dummy_projects.keys())[-1] + 1,
        name=project_info.name,
        description=project_info.description,
        owner=user,
        created_at=(dt.datetime.now(tz=dt.timezone.utc)
                    .strftime("%Y/%m/%d %H:%M:%S")),
        documents=None,
        participants=[user]
    )
    dummy_projects.update({new_project.project_id: new_project})
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
        project_id: int,
        request: Request,
        message: RedirectContextMessage = Depends()
):
    return templates.TemplateResponse(
        request=request,
        name='projects/project_editor.html',
        context={
            'project': dummy_projects[project_id],
            'message': message,
            'operation': 'update'
        }
    )


@router.post('/projects/{project_id}/info')  # Jinja2 templates have no PUT
async def update_project_info(
        project_id: int,
        project_info: ProjectInfo = Form()
):
    dummy_projects[project_id].name = project_info.name
    dummy_projects[project_id].description = project_info.description

    msg = RedirectContextMessage(
        is_error=False,
        content="Project info updated successfully"
    )
    return RedirectResponse(
        url=f'/projects/{project_id}/info?{msg.urlencoded}',
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.post('/projects/{project_id}')  # Jinja2 templates have no DELETE
async def delete_project(project_id: int):
    project = dummy_projects.pop(project_id)
    msg = RedirectContextMessage(
        is_error=False,
        content=f"Project {project.name} deleted successfully"
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
async def get_project_documents_page(project_id: int, request: Request):
    return templates.TemplateResponse(
        request=request,
        name='projects/project_documents.html',
        context={'project': dummy_projects[project_id]}
    )


@router.post('/projects/{project_id}/documents', name='project_documents')
async def upload_documents_to_project(
        project_id: int,
        file: UploadFile = File(...)
):
    msg = RedirectContextMessage(is_error=True, content='')
    if file.content_type not in ALLOWED_MIME_TYPES:
        msg.content = "Unsupported file type"
    elif file.size > 5 * 1024 * 1024:
        msg.content = "File size must not exceed 5 MB"
    else:
        msg.is_error = False
        msg.content = "File uploaded successfully"

    return RedirectResponse(
        url=f'/projects/{project_id}/documents?{msg.urlencoded}',
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.get('/projects/{project_id}/documents/{document_name}')
async def download_project_document(project_id: int, document_name: str):
    pass


@router.get('/projects/{project_id}/participants', name='project_participants')
async def get_project_participants_page(
        project_id: int,
        request: Request,
        current_user: Annotated[User, Depends(auth_required)],
        message: RedirectContextMessage = Depends()
):
    return templates.TemplateResponse(
        request=request,
        name='projects/project_participants.html',
        context={
            'project': dummy_projects[project_id],
            'current_user': current_user,
            'users': dummy_users,
            'message': message
        }
    )


@router.post('/projects/{project_id}/invite')
async def project_invite_participant(project_id: int, user: str = Form(...)):
    # user = get_user_by_username(user)
    for u in dummy_users:
        if u.username == user:
            user = u

    if not user:
        msg = RedirectContextMessage(
            is_error=True,
            content="User not found, please select user from the dropdown menu"
        )
    else:
        dummy_projects[project_id].invite_participant(user)
        msg = RedirectContextMessage(
            is_error=False,
            content=f"{user.username} is now a participant in the project!"
        )

    return RedirectResponse(
        url=f'/projects/{project_id}/participants?{msg.urlencoded}',
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.post('/projects/{project_id}/remove')  # Jinja2 templates have no DELETE
async def project_remove_participant(
        project_id: int,
        username: str = Form(...)
):
    # user = get_user_by_username(username)
    for u in dummy_users:
        if u.username == username:
            user = u
    dummy_projects[project_id].remove_participant(user)

    msg = RedirectContextMessage(
        is_error=False,
        content=f"{username} successfully removed from the project!"
    )
    return RedirectResponse(
        url=f'/projects/{project_id}/participants?{msg.urlencoded}',
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.get('/projects/{project_id}/info', name='project_editor')
async def get_project_info_page(project_id: int):
    pass
