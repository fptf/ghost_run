"""Реестр очистки данных пользователя при удалении аккаунта.

Каждое изменение, которое добавляет данные пользователя вне каскада БД (файлы в S3, внешние
индексы и т. п.), регистрирует здесь свою функцию и покрывает её тестом.
"""

import uuid
from collections.abc import Callable

from app.config import Config
from app.infra.s3 import s3_client

Cleanup = Callable[[Config, uuid.UUID], None]
CLEANUPS: list[Cleanup] = []


def register(fn: Cleanup) -> Cleanup:
    CLEANUPS.append(fn)
    return fn


def user_s3_prefix(user_id: uuid.UUID) -> str:
    return f"users/{user_id}/"


@register
def delete_user_files(cfg: Config, user_id: uuid.UUID) -> None:
    client = s3_client(cfg, timeout_s=30)
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=cfg.s3_bucket, Prefix=user_s3_prefix(user_id)):
        keys = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
        if keys:
            client.delete_objects(Bucket=cfg.s3_bucket, Delete={"Objects": keys})


def run_cleanups(cfg: Config, user_id: uuid.UUID) -> None:
    for fn in CLEANUPS:
        fn(cfg, user_id)
