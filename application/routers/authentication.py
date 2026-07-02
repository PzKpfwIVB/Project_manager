from typing import Annotated

from pydantic import ValidationError

from fastapi import APIRouter, Depends, HTTPException, Request, status
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


router = APIRouter(tags=['authentication'])
templates = Jinja2Templates(directory='application/templates')


async def auth_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED \
            and request.url.path != '/login':
        msg = LoginSignupMessage(
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

    def create(self, user: User) -> str:
        return self._creator_func(user)


@router.get('/auth', response_class=HTMLResponse)
async def auth(request: Request, message_data: str | None = None):
    message = LoginSignupMessage.deserialize(message_data)

    return templates.TemplateResponse(
        request=request,
        name='auth/signup.html',
        context={'message': message}
    )


@router.post('/auth', response_class=RedirectResponse)
async def sign_up(form_data: Annotated[SignupForm, Depends()]):
    msg = LoginSignupMessage(is_error=True, content="")

    try:
        signup_info = SignupInfo(
            username=form_data.username,
            password=form_data.password,
            email=form_data.email,
            full_name=form_data.full_name
        )
    except ValidationError:
        msg.content = "Invalid email address format"
        return RedirectResponse(url=f'/auth?{msg.urlencoded}',
                                status_code=status.HTTP_303_SEE_OTHER)

    if get_user_by_username(signup_info.username) is not None:
        msg.content = "Username already taken"
        return RedirectResponse(url=f'/auth?{msg.urlencoded}',
                                status_code=status.HTTP_303_SEE_OTHER)

    user = sign_user_up(signup_info)
    create_access_token(user)

    msg.is_error = False
    msg.content = "User was successfully created"
    return RedirectResponse(
        url=f'/login?{msg.urlencoded}',
        status_code=status.HTTP_201_CREATED
    )


@router.get('/login', response_class=HTMLResponse)
async def get_login_page(request: Request, message_data: str | None = None):
    message = LoginSignupMessage.deserialize(message_data)
    return templates.TemplateResponse(
        request=request,
        name='auth/login.html',
        context={'message': message}
    )


@router.post('/login', response_model=Token, response_class=RedirectResponse)
async def login(
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
        access_token_creator: Annotated[AccessTokenCreatorInterface, Depends(
            AccessTokenCreator
        )]
):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        msg = LoginSignupMessage(
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
        value=access_token_creator.create(user),
        httponly=True,
        secure=False,
        samesite='lax',
        path='/'
    )

    return resp


@router.post('/logout')
async def logout(user: Annotated[User, Depends(auth_required)]):
    log_user_out(user.username)
    msg = LoginSignupMessage(
        is_error=False,
        content="Successfully logged out"
    )
    resp = RedirectResponse(
        url=f'/login?{msg.urlencoded}',
        status_code=status.HTTP_303_SEE_OTHER
    )
    resp.delete_cookie('access_token', path='/')

    return resp
