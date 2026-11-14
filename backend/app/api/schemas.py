"""Схемы ответа, общие для нескольких роутеров."""

import uuid
from typing import Any, Literal, Self

from pydantic import BaseModel

from app.infra.models import Achievement, Track, User


class LineGeometry(BaseModel):
    type: Literal["LineString"]
    coordinates: list[list[float]]


def line_geometry(geojson: dict[str, Any] | None) -> LineGeometry | None:
    return LineGeometry.model_validate(geojson) if geojson else None


def as_literal[L: str](value: str, allowed: tuple[L, ...]) -> L:
    """Строка из БД как значение Literal-типа схемы ответа (allowed — get_args этого типа)."""
    for option in allowed:
        if option == value:
            return option
    raise ValueError(f"unexpected value {value!r}")


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


def root_ref(root: Track, user: User) -> RootRef:
    """Ссылка на маршрут (исходный трек) с автором."""
    return RootRef(id=root.id, title=root.title, author=author_of(user))
