"""Поиск по карте: parent_track_id, скачивания, pg_trgm, настройки карты.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-13
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEED = {"map.cluster_max_zoom": 11, "map.max_lines": 300}


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column("parent_track_id", sa.Uuid(), sa.ForeignKey("tracks.id", ondelete="SET NULL")),
    )
    op.create_index("ix_tracks_parent_track_id", "tracks", ["parent_track_id"])
    op.create_table(
        "track_downloads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "track_id", sa.Uuid(), sa.ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_track_downloads_track_id", "track_downloads", ["track_id"])
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX ix_tracks_title_trgm ON tracks USING gin (title gin_trgm_ops)")
    op.execute("CREATE INDEX ix_users_name_trgm ON users USING gin (name gin_trgm_ops)")
    op.execute("CREATE INDEX ix_users_city_trgm ON users USING gin (city gin_trgm_ops)")
    for key, value in SEED.items():
        op.execute(
            sa.text("INSERT INTO settings (key, value) VALUES (:k, CAST(:v AS jsonb))").bindparams(
                k=key, v=json.dumps(value)
            )
        )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM settings WHERE key = ANY(:keys)").bindparams(keys=list(SEED)))
    op.execute("DROP INDEX IF EXISTS ix_users_city_trgm")
    op.execute("DROP INDEX IF EXISTS ix_users_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_tracks_title_trgm")
    op.drop_table("track_downloads")
    op.drop_index("ix_tracks_parent_track_id", "tracks")
    op.drop_column("tracks", "parent_track_id")
