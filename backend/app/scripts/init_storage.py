"""Создаёт бакет S3, если его нет: `python -m app.scripts.init_storage`."""

from botocore.exceptions import ClientError

from app.config import Config, get_config
from app.infra.s3 import s3_client


def ensure_bucket(cfg: Config) -> None:
    client = s3_client(cfg, timeout_s=60)
    try:
        client.head_bucket(Bucket=cfg.s3_bucket)
    except ClientError:
        client.create_bucket(Bucket=cfg.s3_bucket)


if __name__ == "__main__":
    ensure_bucket(get_config())
