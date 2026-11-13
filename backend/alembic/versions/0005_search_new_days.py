"""Настройка «новых» треков для поиска.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("INSERT INTO settings (key, value) VALUES ('search.new_days', '7'::jsonb)"))


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM settings WHERE key = 'search.new_days'"))
