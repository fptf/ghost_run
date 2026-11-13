"""Сопоставление маршрутов: попытки, флаги треков, порог направления.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name in ("match_excluded", "root_closed", "hidden_by_moderator"):
        op.add_column(
            "tracks", sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.false())
        )
    op.add_column("tracks", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.create_table(
        "attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "track_id",
            sa.Uuid(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "root_track_id",
            sa.Uuid(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("segment_time_s", sa.Float(), nullable=False),
        sa.Column("hidden_time_s", sa.Float(), nullable=False),
        sa.Column("result_time_s", sa.Float(), nullable=False),
        sa.Column("diff_s", sa.Float(), nullable=False),
        sa.Column("beat", sa.Boolean(), nullable=False),
        sa.Column("by_author", sa.Boolean(), nullable=False),
        sa.Column("coverage", sa.Float(), nullable=False),
        sa.Column("start_gap_m", sa.Float(), nullable=False),
        sa.Column("finish_gap_m", sa.Float(), nullable=False),
        sa.Column("direction_share", sa.Float(), nullable=False),
        sa.Column("length_ratio", sa.Float(), nullable=False),
        sa.Column("segment_distance_m", sa.Float(), nullable=False),
        sa.Column("trimmed", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("state IN ('pending', 'active', 'detached')", name="attempts_state"),
    )
    op.create_index("ix_attempts_root", "attempts", ["root_track_id", "state"])
    op.execute(
        sa.text(
            "INSERT INTO settings (key, value) "
            "VALUES ('matching.direction_min_share', '0.9'::jsonb)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM settings WHERE key = 'matching.direction_min_share'"))
    op.drop_table("attempts")
    for name in ("deleted_at", "hidden_by_moderator", "root_closed", "match_excluded"):
        op.drop_column("tracks", name)
