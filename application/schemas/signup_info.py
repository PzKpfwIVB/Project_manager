from pydantic import BaseModel, EmailStr, Field


class SignupInfo(BaseModel):
    username: str
    password: str
    email: EmailStr | None = Field(default=None)
    full_name: str
