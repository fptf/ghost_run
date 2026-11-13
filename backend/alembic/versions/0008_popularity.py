"""Популярность маршрутов для рейтингов.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "popularity_scores",
        sa.Column(
            "track_id",
            sa.Uuid(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("period", sa.String(16), primary_key=True),
        sa.Column("category", sa.String(8), nullable=False),
        sa.Column("runners", sa.Integer(), nullable=False),
        sa.Column("downloads", sa.Integer(), nullable=False),
        sa.Column("likes", sa.Integer(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_popularity_category_value", "popularity_scores", ["period", "category", "value"]
    )


def downgrade() -> None:
    op.drop_table("popularity_scores")
