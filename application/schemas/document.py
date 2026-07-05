from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


ALLOWED_MIME_TYPES = [
    'application/json',
    'application/msword',
    'application/pdf',
    'application/vnd.ms-excel',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'image/jpeg',
    'image/png',
    'image/tiff',
    'text/plain',
    'text/csv',
    'text/html'
]


class Document(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    project_id: int
    path: str
    size_bytes: int
    uploaded_by_user_id: int
    uploaded_by_username: str
    created_at: datetime

    # @classmethod
    # def from_orm_custom(cls, obj: Any, username: str):
    #     document = super().from_orm(obj)
    #     document.uploaded_by_username = username
    #
    #     return document
