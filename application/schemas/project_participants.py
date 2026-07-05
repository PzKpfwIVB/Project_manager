from typing import Any

from pydantic import BaseModel, ConfigDict


from application.schemas.project import Role
from application.schemas.user import User


class ProjectParticipants(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    owner: User | None = None
    contributors: list[User] = []

    @classmethod
    def from_orm(cls, obj: Any):
        model = cls()

        # [(UserProjectOrm,), ...]
        for user_project_orm_tuple in obj:
            if user_project_orm_tuple[0].role == Role.CONTRIBUTOR.value:
                model.contributors.append(
                    User.from_orm(user_project_orm_tuple[0].user)
                )
            else:
                model.owner = User.from_orm(user_project_orm_tuple[0].user)

        return model

    @property
    def user_ids(self) -> set[int]:
        """ Returns the IDs of the participants. """

        ids = {self.owner.id}
        return ids.union({contributor.id for contributor in self.contributors})
