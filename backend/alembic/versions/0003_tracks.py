"""Треки, сплиты, фото; настройки обработки.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-13
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geometry

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEED = {
    "metrics.max_point_speed_mps": 12,
    "metrics.stopped_speed_mps": 0.5,
    "metrics.elevation_noise_m": 3,
    "geometry.resample_step_m": 10,
    "geometry.simplify_tolerance_m": 5,
    "upload.max_photos": 5,
    "upload.max_photo_bytes": 10485760,
}


def _geom(kind: str) -> Geometry:
    return Geometry(geometry_type=kind, srid=4326, spatial_index=False)


def upgrade() -> None:
    op.create_table(
        "tracks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reject_reason", sa.String(32)),
        sa.Column("visibility", sa.String(16), nullable=False, server_default="private"),
        sa.Column("title", sa.String(120)),
        sa.Column("description", sa.Text()),
        sa.Column("file_format", sa.String(8), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("source_name", sa.String(255)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("distance_m", sa.Float()),
        sa.Column("total_time_s", sa.Float()),
        sa.Column("moving_time_s", sa.Float()),
        sa.Column("avg_pace_s_per_km", sa.Float()),
        sa.Column("elevation_gain_m", sa.Float()),
        sa.Column("has_elevation", sa.Boolean()),
        sa.Column("category", sa.String(8)),
        sa.Column("geometry", _geom("LINESTRINGZM")),
        sa.Column("full_display_geometry", _geom("LINESTRING")),
        sa.Column("visible_geometry", _geom("LINESTRINGM")),
        sa.Column("route_geometry", _geom("LINESTRINGM")),
        sa.Column("display_geometry", _geom("LINESTRING")),
        sa.Column("start_point", _geom("POINT")),
        sa.Column("finish_point", _geom("POINT")),
        sa.Column("visible_from_m", sa.Float()),
        sa.Column("visible_to_m", sa.Float()),
        sa.Column("fully_hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('processing', 'rejected', 'draft', 'published')", name="tracks_status_check"
        ),
        sa.CheckConstraint(
            "visibility IN ('public', 'link', 'private')", name="tracks_visibility_check"
        ),
        sa.UniqueConstraint("user_id", "file_sha256", name="tracks_user_file_unique"),
    )
    op.create_index("ix_tracks_user_id", "tracks", ["user_id"])
    op.create_index("ix_tracks_status_visibility", "tracks", ["status", "visibility"])
    for column in ("display_geometry", "start_point", "route_geometry"):
        op.create_index(f"ix_tracks_{column}", "tracks", [column], postgresql_using="gist")

    op.create_table(
        "track_splits",
        sa.Column(
            "track_id",
            sa.Uuid(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("idx", sa.Integer(), primary_key=True),
        sa.Column("distance_m", sa.Float(), nullable=False),
        sa.Column("time_s", sa.Float(), nullable=False),
    )
    op.create_table(
        "track_photos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "track_id", sa.Uuid(), sa.ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("s3_key", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_track_photos_track_id", "track_photos", ["track_id"])

    for key, value in SEED.items():
        op.execute(
            sa.text("INSERT INTO settings (key, value) VALUES (:k, CAST(:v AS jsonb))").bindparams(
                k=key, v=json.dumps(value)
            )
        )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM settings WHERE key = ANY(:keys)").bindparams(keys=list(SEED)))
    op.drop_table("track_photos")
    op.drop_table("track_splits")
    op.drop_table("tracks")
