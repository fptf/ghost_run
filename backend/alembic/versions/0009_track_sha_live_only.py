"""Повтор файла запрещён только среди неудалённых треков.

Мягко удалённый исходный трек (ФТ-9) остаётся в базе ради группы — но не должен
мешать загрузить тот же файл снова.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("tracks_user_file_unique", "tracks", type_="unique")
    op.create_index(
        "tracks_user_file_unique",
        "tracks",
        ["user_id", "file_sha256"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("tracks_user_file_unique", table_name="tracks")
    op.create_unique_constraint("tracks_user_file_unique", "tracks", ["user_id", "file_sha256"])
