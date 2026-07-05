from typing import Any

from pydantic import BaseModel, ConfigDict


from application.schemas.project import Project, Role
from application.schemas.user import User


class UserProjects(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    owner: list[Project] = []
    contributor: list[Project] = []

    @classmethod
    def from_orm_custom(cls, obj: Any, project_owners: dict[int, User]):
        model = cls()

        # [(UserProjectOrm,), ...]
        for user_project_orm_tuple in obj:
            owner = project_owners[user_project_orm_tuple[0].project_id]
            if user_project_orm_tuple[0].role == Role.CONTRIBUTOR.value:
                model.contributor.append(
                    Project.from_orm_custom(
                        user_project_orm_tuple[0].project,
                        owner=owner
                    )
                )
            else:
                model.owner.append(
                    Project.from_orm_custom(
                        user_project_orm_tuple[0].project,
                        owner=owner
                    )
                )

        return model

    @property
    def project_ids(self) -> set[int]:
        """ Returns the IDs of the projects the user participates in. """

        ids = {project.id for project in self.owner}
        ids.union({project.id for project in self.contributor})

        return ids

    @property
    def all_projects(self) -> list[Project]:
        """ Returns all the projects in a unified list. """

        return self.owner + self.contributor
