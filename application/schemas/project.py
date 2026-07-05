from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict

from application.schemas.document import Document
from application.schemas.user import User


class Role(Enum):
    OWNER = 'Owner'
    CONTRIBUTOR = 'Contributor'


class ProjectInfo(BaseModel):
    name: str = ''
    description: str = ''


class Project(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    name: str
    description: str
    owner: User | None = None  # So from_orm can call super before setting this
    created_at: datetime
    documents: list[Document] | None = None
    participants: list[User]

    @classmethod
    def from_orm_custom(
            cls,
            obj: Any,
            *,
            owner: Any = None,
            project_participants: Any = None
    ):
        # Avoiding circular imports with Any
        project = super().from_orm(obj)

        participants = getattr(obj, 'participants', None)  # RS on ProjectOrm
        if len(participants) == 1:
            project.owner = User.from_orm(participants[0])
        elif owner is not None:
            project.owner = owner
        else:
            project.owner = project_participants.owner

        return project

    @property
    def documents_count(self) -> int:
        """ Returns the number of project-associated documents. """

        return len(self.documents)

    @property
    def participants_count(self) -> int:
        """ Returns the number of users associated with the project. """

        return len(self.participants)

