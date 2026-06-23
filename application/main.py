from fastapi import Depends, HTTPException, FastAPI, status
from fastapi.security import OAuth2PasswordRequestForm

from application.core.security import (
    AccessTokenCreatorInterface,
    auth_required,
    authenticate_user,
    create_access_token,
    Token
)
from application.db.base import (
    get_user_by_username,
    log_user_out,
    sign_user_up,
    SignupInfo,
    User
)


app = FastAPI()


class AccessTokenCreator(AccessTokenCreatorInterface):
    def __init__(self, creator_func=create_access_token):
        self._creator_func = creator_func

    def create(self, user: User) -> str:
        return self._creator_func(user)


@app.post('/signup', status_code=status.HTTP_201_CREATED)
async def signup(signup_info: SignupInfo):

    if not (signup_info.username and signup_info.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing username or password"
        )

    if get_user_by_username(signup_info.username) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken"
        )

    user = sign_user_up(signup_info)
    access_token = create_access_token(user)

    return {'access_token': access_token, 'token_type': 'bearer'}


@app.post("/login", response_model=Token)
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        access_token_creator: AccessTokenCreatorInterface = Depends(
            AccessTokenCreator
        )
):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={'www-authenticate': 'Bearer'}
        )

    access_token = access_token_creator.create(user)

    return {'access_token': access_token, 'token_type': 'bearer'}


@app.post('/logout')
async def logout(user: User = Depends(auth_required)):
    log_user_out(user.username)
    return {'message': "Successfully logged out"}


@app.get('/auth-me')
async def auth_me(user: str = Depends(auth_required)):
    return {'message': "Authentication successful", 'user': user}
