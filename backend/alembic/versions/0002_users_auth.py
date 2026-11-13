"""Пользователи, refresh-токены, лимит запросов к /auth.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geography

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("google_sub", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("avatar_url", sa.String(1024)),
        sa.Column("city", sa.String(100)),
        sa.Column("about", sa.Text()),
        sa.Column("role", sa.String(16), nullable=False, server_default="runner"),
        sa.Column(
            "home_point",
            Geography(geometry_type="POINT", srid=4326, spatial_index=False),
        ),
        sa.Column("hide_radius_m", sa.Integer()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("role IN ('runner', 'moderator', 'admin')", name="users_role_check"),
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    op.execute(
        "INSERT INTO settings (key, value) VALUES ('auth.rate_limit_per_minute', '10'::jsonb)"
    )


def downgrade() -> None:
    op.execute("DELETE FROM settings WHERE key = 'auth.rate_limit_per_minute'")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
