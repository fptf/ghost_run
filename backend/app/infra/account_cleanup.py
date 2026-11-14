"""Реестр очистки данных пользователя при удалении аккаунта.

Каждое изменение, которое добавляет данные пользователя вне каскада БД (файлы в S3, внешние
индексы и т. п.), регистрирует здесь свою функцию и покрывает её тестом.
"""

import uuid
from collections.abc import Callable

from app.config import Config
from app.infra.s3 import delete_prefix

Cleanup = Callable[[Config, uuid.UUID], None]
CLEANUPS: list[Cleanup] = []


def register(fn: Cleanup) -> Cleanup:
    CLEANUPS.append(fn)
    return fn


def user_s3_prefix(user_id: uuid.UUID) -> str:
    return f"users/{user_id}/"


@register
def delete_user_files(cfg: Config, user_id: uuid.UUID) -> None:
    delete_prefix(cfg, user_s3_prefix(user_id))


def run_cleanups(cfg: Config, user_id: uuid.UUID) -> None:
    for fn in CLEANUPS:
        fn(cfg, user_id)
