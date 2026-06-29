from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles

from application.core.security import auth_required
from application.routers import authentication, projects


app = FastAPI()

app.include_router(authentication.router)
app.include_router(projects.router)
app.mount('/static',
          StaticFiles(directory='application/static'),
          name='static')


@app.get('/auth-me')
async def auth_me(user: str = Depends(auth_required)):
    return {'message': "Authentication successful", 'user': user}
