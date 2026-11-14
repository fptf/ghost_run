"""Поиск треков по карте: фильтры, сортировки, кластеры и линии."""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal

from sqlalchemy import ColumnElement, Select, and_, func, literal, or_, select
from sqlalchemy.orm import Session, aliased

from app.infra.geo_types import GEOGRAPHY, GEOMETRY
from app.infra.models import PopularityScore, Track, TrackDownload, User
from app.infra.tracks_repo import group_runners, public_root

Sort = Literal["popular", "distance", "pace", "date", "attempts"]


@dataclass(frozen=True)
class SearchQuery:
    bbox: tuple[float, float, float, float] | None = None  # west, south, east, north
    zoom: float = 12
    category: str | None = None
    dist_min_m: float | None = None
    dist_max_m: float | None = None
    time_min_s: float | None = None
    time_max_s: float | None = None
    pace_min_s: float | None = None
    pace_max_s: float | None = None
    date_from: date | None = None
    date_to: date | None = None
    has_attempts: bool | None = None
    new_since: datetime | None = None  # «новые»: опубликованные не раньше
    q: str | None = None
    sort: Sort = "popular"
    limit: int = 20
    offset: int = 0


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


Child = aliased(Track)
ATTEMPTS = (
    select(func.count()).where(Child.parent_track_id == Track.id).correlate(Track).scalar_subquery()
)
RUNNERS = group_runners()
# Популярность — из почасового пересчёта (ratings_service); трек без строки ещё не пересчитан — 0.
POPULARITY = func.coalesce(
    select(PopularityScore.value)
    .where(PopularityScore.track_id == Track.id, PopularityScore.period == "all")
    .correlate(Track)
    .scalar_subquery(),
    0,
)


def _conditions(q: SearchQuery) -> list[ColumnElement[bool]]:
    cond: list[ColumnElement[bool]] = [public_root(), Track.display_geometry.is_not(None)]
    if q.q:
        pattern = f"%{_escape_like(q.q.strip())}%"
        cond.append(
            or_(
                Track.title.ilike(pattern, escape="\\"),
                User.name.ilike(pattern, escape="\\"),
                User.city.ilike(pattern, escape="\\"),
            )
        )
    elif q.bbox:
        cond.append(Track.display_geometry.op("&&")(func.ST_MakeEnvelope(*q.bbox, 4326)))
    if q.category:
        cond.append(Track.category == q.category)
    if q.dist_min_m is not None:
        cond.append(Track.distance_m >= q.dist_min_m)
    if q.dist_max_m is not None:
        cond.append(Track.distance_m <= q.dist_max_m)
    if q.time_min_s is not None:
        cond.append(Track.total_time_s >= q.time_min_s)
    if q.time_max_s is not None:
        cond.append(Track.total_time_s <= q.time_max_s)
    if q.pace_min_s is not None:
        cond.append(Track.avg_pace_s_per_km >= q.pace_min_s)
    if q.pace_max_s is not None:
        cond.append(Track.avg_pace_s_per_km <= q.pace_max_s)
    if q.date_from is not None:
        cond.append(Track.started_at >= datetime.combine(q.date_from, time.min, UTC))
    if q.date_to is not None:
        end = datetime.combine(q.date_to + timedelta(days=1), time.min, UTC)
        cond.append(Track.started_at < end)
    if q.new_since is not None:
        cond.append(Track.published_at >= q.new_since)
    if q.has_attempts is True:
        cond.append(ATTEMPTS > 0)
    elif q.has_attempts is False:
        cond.append(ATTEMPTS == 0)
    return cond


def _base(q: SearchQuery, *columns: Any) -> Select[Any]:
    return (
        select(*columns)
        .select_from(Track)
        .join(User, User.id == Track.user_id)
        .where(and_(*_conditions(q)))
    )


def _order(q: SearchQuery) -> list[Any]:
    return {
        "popular": [POPULARITY.desc(), Track.published_at.desc()],
        "distance": [Track.distance_m.asc()],
        "pace": [Track.avg_pace_s_per_km.asc()],
        "date": [Track.started_at.desc()],
        "attempts": [ATTEMPTS.desc(), Track.published_at.desc()],
    }[q.sort] + [Track.id]


def list_tracks(db: Session, q: SearchQuery) -> tuple[int, list[dict[str, Any]]]:
    total = db.execute(_base(q, func.count())).scalar_one()
    rows = db.execute(
        _base(
            q,
            Track,
            User,
            ATTEMPTS.label("attempts"),
            RUNNERS.label("runners"),
            func.ST_X(Track.start_point).label("lon"),
            func.ST_Y(Track.start_point).label("lat"),
        )
        .order_by(*_order(q))
        .limit(q.limit)
        .offset(q.offset)
    ).all()
    items = [
        {
            "track": r.Track,
            "author": r.User,
            "attempts_count": int(r.attempts),
            "runners_count": int(r.runners),
            "start": [float(r.lon), float(r.lat)],
        }
        for r in rows
    ]
    return int(total), items


def cluster_cell_deg(zoom: float) -> float:
    """Размер ячейки кластера: примерно треть тайла на текущем зуме."""
    return 360.0 / (2 ** max(zoom, 0)) / 3


def clusters(db: Session, q: SearchQuery) -> list[dict[str, float]]:
    cell = cluster_cell_deg(q.zoom)
    grid = func.ST_SnapToGrid(Track.start_point, cell)
    center = func.ST_Centroid(func.ST_Collect(Track.start_point))
    rows = db.execute(
        _base(q, func.ST_X(center), func.ST_Y(center), func.count()).group_by(grid)
    ).all()
    return [{"lon": float(x), "lat": float(y), "count": int(n)} for x, y, n in rows]


def lines(db: Session, q: SearchQuery, max_lines: int) -> list[dict[str, Any]]:
    tolerance = 360.0 / (256 * 2 ** max(q.zoom, 0))  # ~1 пиксель
    geom = func.ST_AsGeoJSON(func.ST_Simplify(Track.display_geometry, literal(tolerance)), 6)
    rows = db.execute(_base(q, Track.id, geom).order_by(*_order(q)).limit(max_lines)).all()
    return [{"id": tid, "coordinates": json.loads(g)["coordinates"]} for tid, g in rows if g]


def km_marks(db: Session, track: Track) -> list[dict[str, float]]:
    """Отметки целых километров на видимой части (дистанция — по всему треку)."""
    if track.visible_geometry is None or track.visible_from_m is None or not track.distance_m:
        return []
    start, end = track.visible_from_m, track.visible_to_m or track.distance_m
    kms = [k for k in range(1, int(track.distance_m // 1000) + 1) if start <= k * 1000 <= end]
    if not kms or end <= start:
        return []
    fracs = [(k * 1000 - start) / (end - start) for k in kms]
    geog = func.ST_Force2D(Track.visible_geometry).cast(GEOGRAPHY)
    marks = []
    for k, f in zip(kms, fracs, strict=True):
        point = func.ST_LineInterpolatePoint(geog, literal(f)).cast(GEOMETRY)
        x, y = db.execute(
            select(func.ST_X(point), func.ST_Y(point)).where(Track.id == track.id)
        ).one()
        marks.append({"km": k, "lon": float(x), "lat": float(y)})
    return marks


def record_download(db: Session, track_id: uuid.UUID, user_id: uuid.UUID | None) -> None:
    db.add(TrackDownload(track_id=track_id, user_id=user_id))
    db.commit()


def gpx_coords(db: Session, track_id: uuid.UUID) -> list[list[float]]:
    raw = db.execute(
        select(func.ST_AsGeoJSON(func.ST_Force2D(Track.visible_geometry), 7)).where(
            Track.id == track_id
        )
    ).scalar_one_or_none()
    return json.loads(raw)["coordinates"] if raw else []
