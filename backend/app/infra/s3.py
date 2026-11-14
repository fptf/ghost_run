from typing import Any

import boto3
from botocore.config import Config as BotoConfig

from app.config import Config


def s3_client(cfg: Config, timeout_s: int | None = None) -> Any:
    timeout = timeout_s if timeout_s is not None else cfg.health_timeout_s
    return boto3.client(
        "s3",
        endpoint_url=cfg.s3_endpoint_url,
        aws_access_key_id=cfg.s3_access_key,
        aws_secret_access_key=cfg.s3_secret_key,
        region_name=cfg.s3_region,
        config=BotoConfig(
            connect_timeout=timeout,
            read_timeout=timeout,
            retries={"max_attempts": 1},
        ),
    )


def delete_prefix(cfg: Config, prefix: str) -> None:
    """Удаляет все объекты бакета с префиксом (файлы трека, пользователя)."""
    client = s3_client(cfg, timeout_s=30)
    for page in client.get_paginator("list_objects_v2").paginate(
        Bucket=cfg.s3_bucket, Prefix=prefix
    ):
        keys = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
        if keys:
            client.delete_objects(Bucket=cfg.s3_bucket, Delete={"Objects": keys})
