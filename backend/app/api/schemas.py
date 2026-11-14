"""Схемы ответа, общие для нескольких роутеров."""

import uuid
from typing import Literal, Self

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infra.models import Achievement, Track, User


class LineGeometry(BaseModel):
    type: Literal["LineString"]
    coordinates: list[list[float]]


class Author(BaseModel):
    id: uuid.UUID
    name: str
    avatar_url: str | None


def author_of(user: User) -> Author:
    return Author(id=user.id, name=user.name, avatar_url=user.avatar_url)


class AchievementFields(BaseModel):
    """Поля ачивки в ответах; у каждого ответа своя схема-наследник (имена в OpenAPI)."""

    code: str
    title: str
    icon: str

    @classmethod
    def of(cls, achievement: Achievement) -> Self:
        return cls(code=achievement.code, title=achievement.title, icon=achievement.icon)


class RootRef(BaseModel):
    id: uuid.UUID
    title: str | None
    author: Author


def root_ref(db: Session, root_id: uuid.UUID) -> RootRef | None:
    """Ссылка на маршрут (исходный трек) с автором."""
    root = db.get(Track, root_id)
    user = db.get(User, root.user_id) if root else None
    if root is None or user is None:
        return None
    return RootRef(
        id=root.id,
        title=root.title,
        author=author_of(user),
    )
