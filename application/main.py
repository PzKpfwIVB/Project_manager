from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from application.core.security import auth_required
from application.schemas.user import User
from application.routers import authentication, projects


app = FastAPI()

app.include_router(authentication.router)
app.include_router(projects.router)
app.mount('/static',
          StaticFiles(directory='application/static'),
          name='static')

app.add_exception_handler(HTTPException, authentication.auth_exception_handler)


@app.get('/auth-me')
async def auth_me(user: Annotated[User, Depends(auth_required)]):
    return {'message': "Authentication successful", 'user': user}
