from pydantic import BaseModel

from application.schemas.token_data import TokenDataDb


class User(BaseModel):
    username: str
    hashed_password: str | None = None
    email: str | None = None
    full_name: str | None = None
    token_data: TokenDataDb | None = None
