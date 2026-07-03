from pydantic import BaseModel


class ProjectInfo(BaseModel):
    name: str = ''
    description: str = ''
