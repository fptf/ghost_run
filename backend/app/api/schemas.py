"""Схемы ответа, общие для нескольких роутеров."""

import uuid
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infra.models import Track, User


class LineGeometry(BaseModel):
    type: Literal["LineString"]
    coordinates: list[list[float]]


class Author(BaseModel):
    id: uuid.UUID
    name: str
    avatar_url: str | None


class RootRef(BaseModel):
    id: uuid.UUID
    title: str | None
    author: Author


def root_ref(db: Session, root_id: uuid.UUID) -> RootRef | None:
    """Ссылка на маршрут (исходный трек) с автором."""
    root = db.get(Track, root_id)
    author = db.get(User, root.user_id) if root else None
    if root is None or author is None:
        return None
    return RootRef(
        id=root.id,
        title=root.title,
        author=Author(id=author.id, name=author.name, avatar_url=author.avatar_url),
    )
