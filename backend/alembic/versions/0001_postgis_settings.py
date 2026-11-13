"""PostGIS и таблица settings с начальными значениями.

Revision ID: 0001
Revises:
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Значения зафиксированы на момент миграции (копия app.domain.settings_defaults).
SEED = {
    "matching.start_finish_radius_m": 50,
    "matching.corridor_width_m": 30,
    "matching.corridor_coverage": 0.9,
    "matching.length_tolerance": 0.03,
    "matching.loop_threshold_m": 50,
    "matching.candidate_start_radius_m": 50,
    "comparison.tie_threshold_s": 1,
    "categories.bounds_m": [3000, 7500, 15000, 25000],
    "popularity.weights": {"runners": 5, "downloads": 2, "likes": 1},
    "popularity.recalc_interval_s": 3600,
    "upload.max_file_bytes": 20971520,
    "upload.min_pace_s_per_km": 150,
    "upload.rate_limit_per_hour": 20,
    "privacy.hide_radius_m": {"min": 200, "max": 500},
}


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    settings = op.create_table(
        "settings",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("value", JSONB, nullable=False),
    )
    op.bulk_insert(settings, [{"key": k, "value": v} for k, v in SEED.items()])


def downgrade() -> None:
    op.drop_table("settings")
