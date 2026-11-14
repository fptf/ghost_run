"""Модели SQLAlchemy совпадают со схемой после миграций: autogenerate не находит разницы."""

from typing import Any

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text

from app.config import Config
from app.infra import models  # noqa: F401  регистрирует модели
from app.infra.db import Base, get_engine

# Таблицы расширений (PostGIS, tiger geocoder, topology) — не наши, их не сравниваем.
EXTENSION_TABLES = text("""
    SELECT c.relname FROM pg_class c
    JOIN pg_depend d ON d.objid = c.oid AND d.deptype = 'e'
    WHERE c.relkind = 'r'
""")


def test_models_match_migrations(migrated: Config) -> None:
    with get_engine(migrated.database_url).connect() as conn:
        foreign = set(conn.execute(EXTENSION_TABLES).scalars())

        def include(obj: Any, name: str | None, type_: str, reflected: bool, _: Any) -> bool:
            table = name if type_ == "table" else getattr(getattr(obj, "table", None), "name", None)
            return table not in foreign

        ctx = MigrationContext.configure(
            conn, opts={"include_object": include, "compare_type": True}
        )
        diff = compare_metadata(ctx, Base.metadata)
    assert diff == [], "\n".join(map(str, diff))
