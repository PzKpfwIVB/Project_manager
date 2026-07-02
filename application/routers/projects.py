import json
from typing import Annotated

from pydantic import ValidationError

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates

from application.core.security import (
    AccessTokenCreatorInterface,
    auth_required,
    authenticate_user,
    create_access_token
)
from application.db.base import (
    get_user_by_username,
    log_user_out,
    sign_user_up
)
from application.schemas.signup_info import SignupInfo
from application.schemas.token import Token
from application.schemas.user import User
from application.utils.signup import LoginSignupMessage, SignupForm


router = APIRouter(tags=['projects'], dependencies=[Depends(auth_required)])
templates = Jinja2Templates(directory='application/templates')


class Project:
    def __init__(self, project_id: int, name: str, description: str, is_owner: bool, created_at: str, documents: list | None):
        self.project_id = project_id
        self.name = name
        self.description = description
        self.is_owner = is_owner
        self.created_at = created_at
        self.documents = documents if documents else []
        self.participants = ['Anonymous']
        self.documents_count = len(self.documents),
        self.participants_count = len(self.participants)


@router.get('/projects', response_class=HTMLResponse)
async def get_projects_dashboard(request: Request):
    dummy_projects = [
        Project(
            project_id=1,
            name="Project Projectsson",
            description="Descriptionsson",
            is_owner=True,
            created_at="2002/02/20 02:20:22",
            documents=None
        ),
        Project(
            project_id=2,
            name="Project 2",
            description="Second project",
            is_owner=False,
            created_at="2009/09/09 09:09:09",
            documents=["proj2.proj", "test.txt"]
        )
    ]

    return templates.TemplateResponse(
        request=request,
        name='projects/dashboard.html',
        context={'projects': dummy_projects, 'username': 'Bob'}
    )


@router.post('/projects', name='projects')
async def create_new_project():
    pass


@router.delete('/projects/{project_id}', name='projects')
async def delete_project(project_id: int):
    pass


@router.get('/projects/{project_id}', name='invite')
async def get_invitation_page():
    pass


@router.get('/projects/{project_id}/documents', name='project_documents')
async def get_project_documents_page(project_id: int):
    pass


@router.get('/projects/{project_id}/participants', name='project_participants')
async def get_project_participants_page(project_id: int):
    pass


@router.get('/projects/{project_id}/info', name='project_editor')
async def get_project_info_page(project_id: int):
    pass
