from typing import Annotated

from pydantic import ValidationError

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from application.core.security import (
    AccessTokenCreatorInterface,
    auth_required,
    authenticate_user,
    create_access_token
)
from application.db.crud import (
    insert_user_into_db,
    log_user_out,
    select_user_by_username)
from application.db.session import SessionDependency
from application.schemas.redirect_context_message import RedirectContextMessage
from application.schemas.signup_info import SignupInfo
from application.schemas.token import Token
from application.schemas.user import User, UserSignupForm
from application.utils.signup import SignupForm


router = APIRouter(tags=['authentication'])
templates = Jinja2Templates(directory='application/templates')


async def auth_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED \
            and request.url.path != '/login':
        msg = RedirectContextMessage(
                is_error=True,
                content="Could not validate credentials"
        )
        return RedirectResponse(
            url=f'/login?{msg.urlencoded}',
            status_code=status.HTTP_303_SEE_OTHER,
        )


class AccessTokenCreator(AccessTokenCreatorInterface):
    def __init__(self, creator_func=create_access_token):
        self._creator_func = creator_func

    def create(self, session: Session, user: User) -> str:
        return self._creator_func(session, user)


@router.get('/auth', response_class=HTMLResponse)
async def auth(request: Request, message: RedirectContextMessage = Depends()):
    return templates.TemplateResponse(
        request=request,
        name='auth/signup.html',
        context={'message': message}
    )


@router.post('/auth', response_class=RedirectResponse)
async def sign_up(
        session: SessionDependency,
        form_data: Annotated[SignupForm, Depends()]
):
    msg = RedirectContextMessage(is_error=True, content="")

    try:
        signup_info = SignupInfo(
            username=form_data.username,
            password=form_data.password,
            email=form_data.email,
            full_name=form_data.full_name
        )
        user_signup_form = UserSignupForm(
            username=form_data.username,
            password=form_data.password,
            email=form_data.email,
            full_name=form_data.full_name
        )
    except ValidationError:
        msg.content = "Invalid email address format"
        return RedirectResponse(url=f'/auth?{msg.urlencoded}',
                                status_code=status.HTTP_303_SEE_OTHER)

    if select_user_by_username(session, signup_info.username) is not None:
        msg.content = "Username already taken"
        return RedirectResponse(url=f'/auth?{msg.urlencoded}',
                                status_code=status.HTTP_303_SEE_OTHER)

    insert_user_into_db(session, user_signup_form)
    session.commit()

    msg.is_error = False
    msg.content = "User was successfully created"
    return RedirectResponse(
        url=f'/login?{msg.urlencoded}',
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.get('/login', response_class=HTMLResponse)
async def get_login_page(
        request: Request,
        message: RedirectContextMessage = Depends()
):
    return templates.TemplateResponse(
        request=request,
        name='auth/login.html',
        context={'message': message}
    )


@router.post('/login', response_model=Token, response_class=RedirectResponse)
async def login(
        session: SessionDependency,
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
        access_token_creator: Annotated[AccessTokenCreatorInterface, Depends(
            AccessTokenCreator
        )]
):
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        msg = RedirectContextMessage(
            is_error=True,
            content="Invalid username or password"
        )
        return RedirectResponse(
            url=f'/login?{msg.urlencoded}',
            status_code=status.HTTP_303_SEE_OTHER
        )

    resp = RedirectResponse(
        url='/projects',
        status_code=status.HTTP_303_SEE_OTHER
    )
    resp.set_cookie(
        key='access_token',
        value=access_token_creator.create(session, user),
        httponly=True,
        secure=False,
        samesite='lax',
        path='/'
    )

    return resp


@router.post('/logout')
async def logout(
        session: SessionDependency,
        user: Annotated[User, Depends(auth_required)]
):
    log_user_out(session, user.username)
    msg = RedirectContextMessage(
        is_error=False,
        content="Successfully logged out"
    )
    resp = RedirectResponse(
        url=f'/login?{msg.urlencoded}',
        status_code=status.HTTP_303_SEE_OTHER
    )
    resp.delete_cookie('access_token', path='/')

    return resp
