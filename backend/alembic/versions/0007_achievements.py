"""Ачивки и счётчик новых попыток.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tracks", sa.Column("attempts_seen_at", sa.DateTime(timezone=True)))
    op.add_column("attempts", sa.Column("activated_at", sa.DateTime(timezone=True)))
    op.execute("UPDATE attempts SET activated_at = created_at WHERE state = 'active'")
    achievements = op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("icon", sa.String(32), nullable=False),
    )
    op.bulk_insert(
        achievements,
        [
            {
                "code": "outperformed",
                "title": "Превзошёл",
                "description": "Пробежал чужой маршрут быстрее автора",
                "icon": "bolt",
            }
        ],
    )
    op.create_table(
        "user_achievements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "achievement_id",
            sa.Integer(),
            sa.ForeignKey("achievements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "track_id", sa.Uuid(), sa.ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "awarded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("achievement_id", "track_id", name="user_achievement_once"),
    )
    op.create_index("ix_user_achievements_user", "user_achievements", ["user_id"])
    # Ачивки за уже засчитанные попытки (после пересопоставления дампа)
    op.execute("""
        INSERT INTO user_achievements (user_id, achievement_id, track_id, awarded_at)
        SELECT t.user_id, a.id, t.id, coalesce(at.activated_at, now())
        FROM attempts at
        JOIN tracks t ON t.id = at.track_id
        JOIN achievements a ON a.code = 'outperformed'
        WHERE at.state = 'active' AND at.beat AND NOT at.by_author
        """)


def downgrade() -> None:
    op.drop_table("user_achievements")
    op.drop_table("achievements")
    op.drop_column("attempts", "activated_at")
    op.drop_column("tracks", "attempts_seen_at")
