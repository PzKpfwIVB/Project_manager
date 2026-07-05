from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from application.schemas.token_data import TokenData


class UserBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str = ''
    full_name: str = ''


class User(UserBase):
    id: int | None = None
    username: str
    hashed_password: str | None = None
    token_data: TokenData | None = None

    @classmethod
    def from_orm(cls, obj: Any):
        user = super().from_orm(obj)

        token = getattr(obj, 'token', None)  # Relationship on UserOrm
        if token is not None:
            user.token_data = TokenData.from_orm(token)

        return user


class UserSignupForm(UserBase):
    username: str = Field(..., description="Required")
    password: str = Field(..., description="Required")
