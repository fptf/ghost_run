"""Общие фикстуры: настоящие PostGIS, Redis и S3 (SeaweedFS) в testcontainers."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config as AlembicConfig
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import HttpWaitStrategy

from alembic import command
from app.config import Config, get_config
from app.infra.db import get_engine
from app.main import app
from app.scripts.init_storage import ensure_bucket

BACKEND_DIR = Path(__file__).resolve().parents[1]
POSTGIS_IMAGE = "postgis/postgis:16-3.5"
SEAWEEDFS_IMAGE = "chrislusf/seaweedfs:4.53"
S3_CONFIG = BACKEND_DIR.parent / "infra" / "seaweedfs" / "s3.json"


@pytest.fixture(scope="session")
def postgres() -> Iterator[PostgresContainer]:
    with PostgresContainer(POSTGIS_IMAGE, driver="psycopg") as pg:
        yield pg


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    with RedisContainer("redis:7-alpine") as r:
        yield f"redis://{r.get_container_host_ip()}:{r.get_exposed_port(6379)}/0"


@pytest.fixture(scope="session")
def s3_endpoint() -> Iterator[str]:
    container = (
        DockerContainer(SEAWEEDFS_IMAGE)
        .with_command("server -dir=/data -s3 -s3.port=8333 -s3.config=/etc/s3.json")
        .with_volume_mapping(str(S3_CONFIG), "/etc/s3.json", "ro")
        .with_exposed_ports(8333)
        .waiting_for(
            HttpWaitStrategy(8333, "/healthz").for_status_code(200).with_startup_timeout(60)
        )
    )
    with container as s3:
        yield f"http://{s3.get_container_host_ip()}:{s3.get_exposed_port(8333)}"


@pytest.fixture(scope="session")
def config(postgres: PostgresContainer, redis_url: str, s3_endpoint: str) -> Config:
    cfg = Config(
        database_url=postgres.get_connection_url(),
        redis_url=redis_url,
        s3_endpoint_url=s3_endpoint,
        s3_access_key="runners",
        s3_secret_key="runners-secret",
        s3_bucket="tracks",
    )
    ensure_bucket(cfg)
    return cfg


@pytest.fixture(scope="session")
def migrated(config: Config) -> Config:
    alembic_cfg = AlembicConfig(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", config.database_url)
    alembic_cfg.attributes["configure_logger"] = False
    command.upgrade(alembic_cfg, "head")
    return config


@pytest.fixture
def db(migrated: Config) -> Iterator[Session]:
    with sessionmaker(bind=get_engine(migrated.database_url))() as session:
        yield session


@pytest.fixture
def client(migrated: Config) -> Iterator[TestClient]:
    app.dependency_overrides[get_config] = lambda: migrated
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
