"""Схемы ответа, общие для нескольких роутеров."""

import uuid
from typing import Any, Literal, Self

from fastapi.responses import JSONResponse
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


class Photo(BaseModel):
    id: uuid.UUID
    url: str


def photo_url(track_id: uuid.UUID, photo_id: uuid.UUID) -> str:
    return f"/tracks/{track_id}/photos/{photo_id}"


class UploadError(BaseModel):
    code: str
    detail: str
    track_id: uuid.UUID | None = None
    retry_after_s: int | None = None


def error_response(status_code: int, code: str, detail: str, **extra: Any) -> JSONResponse:
    """Ошибка загрузки файла (трека или фото) с машинным кодом."""
    body = UploadError(code=code, detail=detail, **extra).model_dump(mode="json")
    headers = {"Retry-After": str(extra["retry_after_s"])} if extra.get("retry_after_s") else None
    return JSONResponse(status_code=status_code, content=body, headers=headers)
