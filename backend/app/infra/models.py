import enum
import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography, Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)


class Role(enum.StrEnum):
    runner = "runner"
    moderator = "moderator"
    admin = "admin"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('runner', 'moderator', 'admin')", name="users_role_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(String(1024))
    city: Mapped[str | None] = mapped_column(String(100))
    about: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16), default=Role.runner.value)
    home_point: Mapped[Any | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    hide_radius_m: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrackStatus(enum.StrEnum):
    processing = "processing"
    rejected = "rejected"
    draft = "draft"
    published = "published"


class Visibility(enum.StrEnum):
    public = "public"
    link = "link"
    private = "private"


def _geom(kind: str) -> Geometry:
    return Geometry(geometry_type=kind, srid=4326, spatial_index=False)


class Track(Base):
    __tablename__ = "tracks"
    __table_args__ = (
        # один и тот же файл у бегуна — один раз, не считая мягко удалённых (миграция 0009)
        Index(
            "tracks_user_file_unique",
            "user_id",
            "file_sha256",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default=TrackStatus.processing.value)
    reject_reason: Mapped[str | None] = mapped_column(String(32))
    visibility: Mapped[str] = mapped_column(String(16), default=Visibility.private.value)
    title: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    file_format: Mapped[str] = mapped_column(String(8))
    file_size: Mapped[int] = mapped_column(Integer)
    file_sha256: Mapped[str] = mapped_column(String(64))
    source_name: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    distance_m: Mapped[float | None] = mapped_column(Float)
    total_time_s: Mapped[float | None] = mapped_column(Float)
    moving_time_s: Mapped[float | None] = mapped_column(Float)
    avg_pace_s_per_km: Mapped[float | None] = mapped_column(Float)
    elevation_gain_m: Mapped[float | None] = mapped_column(Float)
    has_elevation: Mapped[bool | None] = mapped_column(Boolean)
    category: Mapped[str | None] = mapped_column(String(8))
    geometry: Mapped[Any | None] = mapped_column(_geom("LINESTRINGZM"))
    full_display_geometry: Mapped[Any | None] = mapped_column(_geom("LINESTRING"))
    visible_geometry: Mapped[Any | None] = mapped_column(_geom("LINESTRINGM"))
    route_geometry: Mapped[Any | None] = mapped_column(_geom("LINESTRINGM"))
    display_geometry: Mapped[Any | None] = mapped_column(_geom("LINESTRING"))
    start_point: Mapped[Any | None] = mapped_column(_geom("POINT"))
    finish_point: Mapped[Any | None] = mapped_column(_geom("POINT"))
    visible_from_m: Mapped[float | None] = mapped_column(Float)
    visible_to_m: Mapped[float | None] = mapped_column(Float)
    fully_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_track_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tracks.id", ondelete="SET NULL")
    )
    match_excluded: Mapped[bool] = mapped_column(Boolean, default=False)  # «Не засчитывать»
    root_closed: Mapped[bool] = mapped_column(Boolean, default=False)  # не принимает попыток
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hidden_by_moderator: Mapped[bool] = mapped_column(Boolean, default=False)
    # Когда автор маршрута последний раз открывал группу — для счётчика новых попыток.
    attempts_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrackSplit(Base):
    __tablename__ = "track_splits"

    track_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    idx: Mapped[int] = mapped_column(Integer, primary_key=True)
    distance_m: Mapped[float] = mapped_column(Float)
    time_s: Mapped[float] = mapped_column(Float)


class TrackPhoto(Base):
    __tablename__ = "track_photos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    track_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    s3_key: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TrackDownload(Base):
    __tablename__ = "track_downloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    track_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AttemptState(enum.StrEnum):
    pending = "pending"  # найдено после обработки, ждёт публикации
    active = "active"  # в группе
    detached = "detached"  # отвязана или вышла из группы


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    track_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), unique=True
    )
    root_track_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    state: Mapped[str] = mapped_column(String(16), default=AttemptState.pending.value)
    segment_time_s: Mapped[float] = mapped_column(Float)
    hidden_time_s: Mapped[float] = mapped_column(Float)
    result_time_s: Mapped[float] = mapped_column(Float)
    diff_s: Mapped[float] = mapped_column(Float)
    beat: Mapped[bool] = mapped_column(Boolean, default=False)
    by_author: Mapped[bool] = mapped_column(Boolean, default=False)
    coverage: Mapped[float] = mapped_column(Float)
    start_gap_m: Mapped[float] = mapped_column(Float)
    finish_gap_m: Mapped[float] = mapped_column(Float)
    direction_share: Mapped[float] = mapped_column(Float)
    length_ratio: Mapped[float] = mapped_column(Float)
    segment_distance_m: Mapped[float] = mapped_column(Float)
    trimmed: Mapped[bool] = mapped_column(Boolean, default=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(32))


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("achievement_id", "track_id", name="user_achievement_once"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    achievement_id: Mapped[int] = mapped_column(ForeignKey("achievements.id", ondelete="CASCADE"))
    track_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PopularityScore(Base):
    __tablename__ = "popularity_scores"

    track_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    period: Mapped[str] = mapped_column(String(16), primary_key=True, default="all")
    category: Mapped[str] = mapped_column(String(8))
    runners: Mapped[int] = mapped_column(Integer)
    downloads: Mapped[int] = mapped_column(Integer)
    likes: Mapped[int] = mapped_column(Integer)
    value: Mapped[float] = mapped_column(Float)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
