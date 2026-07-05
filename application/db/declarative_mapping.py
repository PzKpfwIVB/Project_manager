from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    create_engine,
    DateTime,
    ForeignKey,
    func,
    Integer,
    Text,
    UniqueConstraint
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker
)

from application.core.config import DATABASE_URL


def orm_repr(obj) -> str:
    """
    A common repr format for ORM models containing information on all mapped
    columns and relationships.
    """

    def basic_repr(retrieved_obj):
        """
        A basic representation for ORM models to avoid infinite recursion.
        """

        if isinstance(retrieved_obj, DeclarativeBase):
            return f"{obj.__class__.__name__}<...>"

        return retrieved_obj

    mapper = obj.__class__.__mapper__

    parts = []
    for col_attr in mapper.column_attrs:  # mapped columns
        key = col_attr.key
        parts.append(f"[#MC]{key}={basic_repr(getattr(obj, key))}")

    for rel in mapper.relationships:  # relationships
        key = rel.key
        parts.append(f"[#RS]{key}={basic_repr(getattr(obj, key))}")

    return f"{obj.__class__.__name__}< " + ", ".join(parts) + " >"


class Base(DeclarativeBase):
    pass


class UserOrm(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(Text)
    full_name: Mapped[Optional[str]] = mapped_column(Text)

    token: Mapped[TokenOrm] = relationship(
        'TokenOrm',
        back_populates='user',
        lazy='selectin',
    )

    projects: Mapped[list[ProjectOrm]] = relationship(
        'ProjectOrm',
        secondary='user_project',
        back_populates='participants',
        lazy='selectin',
        viewonly=True,
        overlaps='project_links'
    )

    project_links: Mapped[list[UserProjectOrm]] = relationship(
        'UserProjectOrm',
        back_populates='user',
        cascade="all, delete-orphan",
        lazy='selectin'
    )

    def __repr__(self) -> str:
        return orm_repr(self)


class ProjectOrm(Base):
    __tablename__ = 'projects'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    documents: Mapped[list[DocumentOrm]] = relationship(
        'DocumentOrm',
        back_populates='project',
        cascade="all, delete-orphan",
        lazy='selectin'
    )

    participants: Mapped[list[UserOrm]] = relationship(
        'UserOrm',
        secondary='user_project',
        back_populates='projects',
        lazy='selectin',
        viewonly=True,
        overlaps='user_links'
    )

    user_links: Mapped[list[UserProjectOrm]] = relationship(
        'UserProjectOrm',
        back_populates='project',
        cascade="all, delete-orphan",
        lazy='selectin'
    )

    def __repr__(self) -> str:
        return orm_repr(self)


class UserProjectOrm(Base):
    __tablename__ = 'user_project'

    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'),
        primary_key=True,
        index=True
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey('projects.id', ondelete='CASCADE'),
        primary_key=True,
        index=True
    )

    user: Mapped[UserOrm] = relationship(
        'UserOrm',
        back_populates='project_links'
    )
    project: Mapped[ProjectOrm] = relationship(
        'ProjectOrm',
        back_populates='user_links'
    )

    role: Mapped[str] = mapped_column(Text)

    def __repr__(self) -> str:
        return orm_repr(self)


class TokenOrm(Base):
    __tablename__ = 'tokens'

    id: Mapped[str] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id'),
        nullable=False,
        unique=True,
        index=True
    )
    user: Mapped[UserOrm] = relationship(back_populates='token')

    expire: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    def __repr__(self) -> str:
        return orm_repr(self)


class DocumentOrm(Base):
    __tablename__ = 'documents'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    project_id: Mapped[int] = mapped_column(
        ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    project: Mapped[ProjectOrm] = relationship(back_populates='documents')

    path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    uploaded_by_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by_username: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            'project_id',
            'path',
            name='uc_documents_project_path'),
    )

    def __repr__(self) -> str:
        return orm_repr(self)


class RevokedTokenOrm(Base):
    __tablename__ = 'revoked_tokens'

    id: Mapped[int] = mapped_column(
        ForeignKey('tokens.id', ondelete='CASCADE'),
        primary_key=True
    )

    def __repr__(self) -> str:
        return orm_repr(self)


if __name__ == '__main__':
    engine = create_engine(DATABASE_URL)

    Session = sessionmaker(bind=engine)
    session = Session()

    # Create all tables in the database which are defined by Base's subclasses
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(engine)
