import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from urllib.parse import quote
from xml.sax.saxutils import escape, quoteattr

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel

from app.api.deps import DbDep, OptionalUser
from app.api.schemas import Author, author_of
from app.infra import search_repo
from app.infra.models import Track
from app.infra.settings_repo import get_setting
from app.infra.tracks_repo import can_view

router = APIRouter(tags=["search"])

CategoryLiteral = Literal["1", "5", "10", "21", "21+"]


class SearchItem(BaseModel):
    id: uuid.UUID
    title: str | None
    distance_m: float | None
    total_time_s: float | None
    avg_pace_s_per_km: float | None
    category: str | None
    started_at: datetime | None
    author: Author
    runners_count: int
    attempts_count: int
    is_new: bool
    start: list[float]


class Cluster(BaseModel):
    lon: float
    lat: float
    count: int


class Line(BaseModel):
    id: uuid.UUID
    coordinates: list[list[float]]


class SearchResponse(BaseModel):
    total: int
    items: list[SearchItem]
    mode: Literal["clusters", "lines"]
    clusters: list[Cluster]
    lines: list[Line]


_NUM = r"-?\d{1,3}(\.\d+)?"


def _parse_bbox(raw: str) -> tuple[float, float, float, float]:
    """Отдалённая карта отдаёт долготы за ±180 (мир повторяется) — прижимаем к допустимым."""
    west, south, east, north = (float(v) for v in raw.split(","))
    west, east = max(-180.0, west), min(180.0, east)
    south, north = max(-90.0, south), min(90.0, north)
    if west >= east or south >= north:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Некорректная область карты")
    return west, south, east, north


@router.get("/tracks/search", responses={422: {"description": "Нужна область карты или текст"}})
def search_tracks(
    db: DbDep,
    bbox: Annotated[
        str | None,
        Query(description="west,south,east,north", pattern=rf"^{_NUM}(,{_NUM}){{3}}$"),
    ] = None,
    zoom: Annotated[float, Query(ge=0, le=22)] = 12,
    category: CategoryLiteral | None = None,
    dist_min_km: Annotated[float | None, Query(ge=0)] = None,
    dist_max_km: Annotated[float | None, Query(ge=0)] = None,
    time_min_s: Annotated[float | None, Query(ge=0)] = None,
    time_max_s: Annotated[float | None, Query(ge=0)] = None,
    pace_min_s: Annotated[float | None, Query(ge=0)] = None,
    pace_max_s: Annotated[float | None, Query(ge=0)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    has_attempts: bool | None = None,
    is_new: bool | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort: search_repo.Sort = "popular",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SearchResponse:
    text = (q or "").strip() or None
    if bbox is None and text is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Нужна область карты или текст")
    box = _parse_bbox(bbox) if bbox else None
    new_since = datetime.now(UTC) - timedelta(days=int(get_setting(db, "search.new_days")))
    query = search_repo.SearchQuery(
        bbox=box,
        zoom=zoom,
        category=category,
        dist_min_m=dist_min_km * 1000 if dist_min_km is not None else None,
        dist_max_m=dist_max_km * 1000 if dist_max_km is not None else None,
        time_min_s=time_min_s,
        time_max_s=time_max_s,
        pace_min_s=pace_min_s,
        pace_max_s=pace_max_s,
        date_from=date_from,
        date_to=date_to,
        has_attempts=has_attempts,
        new_since=new_since if is_new else None,
        q=text,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    total, rows = search_repo.list_tracks(db, query)
    items = [
        SearchItem(
            id=r["track"].id,
            title=r["track"].title,
            distance_m=r["track"].distance_m,
            total_time_s=r["track"].total_time_s,
            avg_pace_s_per_km=r["track"].avg_pace_s_per_km,
            category=r["track"].category,
            started_at=r["track"].started_at,
            author=author_of(r["author"]),
            runners_count=r["runners_count"],
            attempts_count=r["attempts_count"],
            is_new=bool(r["track"].published_at and r["track"].published_at >= new_since),
            start=r["start"],
        )
        for r in rows
    ]
    if zoom <= int(get_setting(db, "map.cluster_max_zoom")):
        return SearchResponse(
            total=total,
            items=items,
            mode="clusters",
            clusters=[Cluster.model_validate(c) for c in search_repo.clusters(db, query)],
            lines=[],
        )
    max_lines = int(get_setting(db, "map.max_lines"))
    return SearchResponse(
        total=total,
        items=items,
        mode="lines",
        clusters=[],
        lines=[Line(**ln) for ln in search_repo.lines(db, query, max_lines)],
    )


def _gpx(title: str, coords: list[list[float]]) -> str:
    points = "\n".join(f'<trkpt lat="{lat:.7f}" lon="{lon:.7f}"/>' for lon, lat in coords)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="runners" xmlns="http://www.topografix.com/GPX/1/1">\n'
        f"<trk><name>{escape(title)}</name><trkseg>\n{points}\n</trkseg></trk>\n</gpx>\n"
    )


@router.get(
    "/tracks/{track_id}/gpx",
    response_class=Response,
    responses={200: {"content": {"application/gpx+xml": {}}}, 404: {"description": "Нет трека"}},
)
def download_gpx(track_id: uuid.UUID, db: DbDep, viewer: OptionalUser) -> Response:
    track = db.get(Track, track_id)
    if track is None or not can_view(track, viewer.id if viewer else None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Трек не найден")
    coords = search_repo.gpx_coords(db, track.id)
    if not coords:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "У трека нет видимой части")
    title = track.title or "Маршрут"
    search_repo.record_download(db, track.id, viewer.id if viewer else None)
    db.commit()
    ascii_name = f"route-{str(track.id)[:8]}.gpx"
    disposition = (
        f"attachment; filename={quoteattr(ascii_name)}; filename*=UTF-8''{quote(title)}.gpx"
    )
    return Response(
        content=_gpx(title, coords),
        media_type="application/gpx+xml",
        headers={"Content-Disposition": disposition},
    )
