import json
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbDep, OptionalUser
from app.api.tracks import Author, LineGeometry, RootRef, _root_ref
from app.domain.matching import compare
from app.infra import tracks_repo
from app.infra.achievements_service import track_achievements
from app.infra.matching_service import attempt_row, evaluate, group_rows, load_config, root_of
from app.infra.models import Track, TrackStatus
from app.infra.settings_repo import get_setting

router = APIRouter(tags=["groups"])


class GroupRow(BaseModel):
    place: int
    runner: Author
    track_id: uuid.UUID
    time_s: float
    pace_s_per_km: float
    date: datetime | None
    beat: bool
    is_author: bool
    is_root: bool
    runs: int  # попыток этого бегуна в группе
    is_viewer: bool


class GroupResponse(BaseModel):
    root: RootRef
    root_distance_m: float
    runners: int
    rows: list[GroupRow]


def _group_track(db: DbDep, track_id: uuid.UUID, viewer_id: uuid.UUID | None) -> Track:
    track = db.get(Track, track_id)
    if track is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Трек не найден")
    root = root_of(db, track)
    # Группа видна, если виден трек или (для удалённого автором исходного) любая его попытка.
    if not (tracks_repo.can_view(track, viewer_id) or root.deleted_at is not None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Трек не найден")
    return root


@router.get("/tracks/{track_id}/group", responses={404: {"description": "Трек не найден"}})
def read_group(track_id: uuid.UUID, db: DbDep, viewer: OptionalUser) -> GroupResponse:
    root = _group_track(db, track_id, viewer.id if viewer else None)
    if viewer is not None and viewer.id == root.user_id:
        # автор открыл группу своего маршрута — новые попытки просмотрены
        root.attempts_seen_at = datetime.now(UTC)
        db.commit()
    ref = _root_ref(db, root.id)
    assert ref is not None
    distance = root.distance_m or 1.0
    rows = [
        GroupRow(
            place=r["place"],
            runner=Author(id=r["user"].id, name=r["user"].name, avatar_url=r["user"].avatar_url),
            track_id=r["track_id"],
            time_s=r["time_s"],
            pace_s_per_km=r["time_s"] / (distance / 1000),  # 5.2: по дистанции маршрута
            date=r["date"],
            beat=r["beat"],
            is_author=r["is_author"],
            is_root=r["is_root"],
            runs=r["runs"],
            is_viewer=viewer is not None and r["user"].id == viewer.id,
        )
        for r in group_rows(db, root)
    ]
    return GroupResponse(root=ref, root_distance_m=distance, runners=len(rows), rows=rows)


class CheckRequest(BaseModel):
    track_id: uuid.UUID


class CheckRule(BaseModel):
    code: Literal["start", "finish", "corridor", "direction", "length"]
    ok: bool
    value: float
    required: float


class Deviation(BaseModel):
    lon: float
    lat: float
    km: float


class CheckResponse(BaseModel):
    matched: bool
    route: RootRef
    track_id: uuid.UUID
    track_title: str | None
    track_started_at: datetime | None
    rules: list[CheckRule]
    deviation: Deviation | None
    result_time_s: float | None
    diff_s: float | None
    route_line: LineGeometry | None
    corridor: dict[str, Any] | None  # GeoJSON-полигон коридора
    track_line: LineGeometry | None


@router.post(
    "/tracks/{track_id}/check",
    responses={404: {"description": "Нет маршрута или трека"}, 409: {"description": "Не готов"}},
)
def check_run(
    track_id: uuid.UUID, body: CheckRequest, user: CurrentUser, db: DbDep
) -> CheckResponse:
    root = db.get(Track, track_id)
    if root is None or not tracks_repo.can_view(root, user.id) or root.route_geometry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Маршрут не найден")
    mine = db.get(Track, body.track_id)
    if mine is None or mine.user_id != user.id or mine.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Трек не найден")
    if mine.status not in (TrackStatus.draft.value, TrackStatus.published.value):
        raise HTTPException(status.HTTP_409_CONFLICT, "Трек ещё не обработан")
    cfg = load_config(db)
    result = evaluate(db, root, mine, cfg)
    if result is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Нет геометрии для проверки")
    rules = [
        CheckRule(code="start", ok=result.start_ok, value=result.start_gap_m,
                  required=cfg.start_finish_radius_m),
        CheckRule(code="finish", ok=result.finish_ok, value=result.finish_gap_m,
                  required=cfg.start_finish_radius_m),
        CheckRule(code="corridor", ok=result.coverage_ok, value=result.coverage,
                  required=cfg.corridor_coverage),
        CheckRule(code="direction", ok=result.direction_ok, value=result.direction_share,
                  required=cfg.direction_min_share),
        CheckRule(code="length", ok=result.length_ok, value=result.length_ratio,
                  required=cfg.length_tolerance),
    ]  # fmt: skip
    cmp = compare(result.result_time_s, root.total_time_s or 0, cfg.tie_threshold_s)
    corridor_raw = db.execute(
        select(
            func.ST_AsGeoJSON(
                func.ST_Simplify(
                    func.ST_Buffer(
                        func.ST_Force2D(Track.route_geometry).cast(_geog()), cfg.corridor_width_m
                    ).cast(_geom()),
                    0.00003,
                ),
                6,
            )
        ).where(Track.id == root.id)
    ).scalar_one_or_none()
    ref = _root_ref(db, root.id)
    assert ref is not None
    dev = result.deviation
    return CheckResponse(
        matched=result.matched,
        route=ref,
        track_id=mine.id,
        track_title=mine.title,
        track_started_at=mine.started_at,
        rules=rules,
        deviation=Deviation(lon=dev.lon, lat=dev.lat, km=dev.km) if dev else None,
        result_time_s=result.result_time_s if result.matched else None,
        diff_s=cmp.diff_s if result.matched else None,
        route_line=tracks_repo.geojson(db, root.id, "display_geometry"),  # type: ignore[arg-type]
        corridor=json.loads(corridor_raw) if corridor_raw else None,
        track_line=tracks_repo.geojson(db, mine.id, "full_display_geometry"),  # type: ignore[arg-type]
    )


def _geog() -> Any:
    from geoalchemy2 import Geography

    return Geography(srid=4326)


def _geom() -> Any:
    from geoalchemy2 import Geometry

    return Geometry(srid=4326)


class ResultAchievement(BaseModel):
    code: str
    title: str
    icon: str


class ResultResponse(BaseModel):
    outcome: Literal["beat", "slower", "equal"]
    route: RootRef
    result_time_s: float
    root_time_s: float
    diff_s: float
    place: int
    runners: int
    best_time_s: float
    gap_to_best_s: float  # 0, если результат лучший в группе
    by_author: bool
    rows: list[GroupRow]
    achievements: list[ResultAchievement]


@router.get("/tracks/{track_id}/result", responses={404: {"description": "Нет результата"}})
def read_result(track_id: uuid.UUID, user: CurrentUser, db: DbDep) -> ResultResponse:
    track = db.get(Track, track_id)
    if track is None or track.user_id != user.id or track.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Трек не найден")
    attempt = attempt_row(db, track.id)
    if attempt is None or attempt.state != "active" or track.parent_track_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Трек не засчитан как попытка")
    root = db.get(Track, track.parent_track_id)
    assert root is not None
    group = read_group(root.id, db, user)
    ref = _root_ref(db, root.id)
    assert ref is not None
    mine = next((r for r in group.rows if r.is_viewer), None)
    tie = float(get_setting(db, "comparison.tie_threshold_s"))
    outcome: Literal["beat", "slower", "equal"] = (
        "equal" if abs(attempt.diff_s) < tie else "beat" if attempt.diff_s < 0 else "slower"
    )
    best = group.rows[0].time_s if group.rows else attempt.result_time_s
    return ResultResponse(
        outcome=outcome,
        route=ref,
        result_time_s=attempt.result_time_s,
        root_time_s=root.total_time_s or 0,
        diff_s=attempt.diff_s,
        place=mine.place if mine else 0,
        runners=group.runners,
        best_time_s=best,
        gap_to_best_s=max(0.0, attempt.result_time_s - best),
        by_author=attempt.by_author,
        rows=group.rows,
        achievements=[
            ResultAchievement(code=a.code, title=a.title, icon=a.icon)
            for a in track_achievements(db, track.id)
        ],
    )
