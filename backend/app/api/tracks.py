import hashlib
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.api.deps import ConfigDep, CurrentUser, DbDep, OptionalUser
from app.api.schemas import AchievementFields, Author, LineGeometry, RootRef, author_of, root_ref
from app.domain.matching import verdict
from app.domain.tracks.model import REJECT_MESSAGES, RejectReason
from app.domain.tracks.parsers import detect_format
from app.infra import tracks_repo
from app.infra.achievements_service import new_attempts, track_achievements
from app.infra.matching_service import (
    attempt_row,
    detach,
    has_group,
    root_of,
    soft_delete_root,
    sync_group,
    tie_threshold_s,
)
from app.infra.models import Track, TrackPhoto, TrackStatus, User, Visibility
from app.infra.photos import BadPhotoError, sanitize
from app.infra.queue import TaskQueue, get_queue
from app.infra.rate_limit import RateLimiter
from app.infra.s3 import delete_prefix, s3_client
from app.infra.search_repo import km_marks
from app.infra.settings_repo import get_setting
from app.infra.track_processing import source_key, track_prefix
from app.infra.users_repo import get_home

router = APIRouter(tags=["tracks"])

QueueDep = Annotated[TaskQueue, Depends(get_queue)]
StatusLiteral = Literal["processing", "rejected", "draft", "published"]
VisibilityLiteral = Literal["public", "link", "private"]
FULLY_HIDDEN_MESSAGE = (
    "Трек целиком в скрытой зоне у дома — его можно опубликовать только как приватный"
)


# ---------- Схемы ----------


class Split(BaseModel):
    idx: int
    distance_m: float
    time_s: float


class Photo(BaseModel):
    id: uuid.UUID
    url: str


class HiddenZone(BaseModel):
    lat: float
    lon: float
    radius_m: int


class TrackSummary(BaseModel):
    id: uuid.UUID
    status: StatusLiteral
    reject_reason: str | None
    reject_message: str | None
    visibility: VisibilityLiteral
    title: str | None
    started_at: datetime | None
    distance_m: float | None
    total_time_s: float | None
    avg_pace_s_per_km: float | None
    category: str | None
    created_at: datetime
    new_attempts: int = 0  # новые попытки других бегунов (только в «Моих треках»)
    is_attempt: bool = False  # трек засчитан как попытка в группе маршрута
    attempt_root_id: uuid.UUID | None = None  # маршрут, на который засчитан


class OwnerExtras(BaseModel):
    full_geometry: LineGeometry | None
    hidden_zone: HiddenZone | None
    fully_hidden: bool


class MatchInfo(BaseModel):
    """Совпадение с маршрутом — автору трека (плашка в превью и на просмотре)."""

    root: RootRef
    state: Literal["pending", "active", "detached"]
    result_time_s: float
    diff_s: float
    beat: bool
    equal: bool
    by_author: bool
    trimmed: bool
    segment_distance_m: float
    hidden_time_s: float


class AchievementBadge(AchievementFields):
    pass


class KmMark(BaseModel):
    km: int
    lon: float
    lat: float


class TrackDetail(TrackSummary):
    description: str | None
    moving_time_s: float | None
    elevation_gain_m: float | None
    has_elevation: bool | None
    splits: list[Split]
    author: Author
    geometry: LineGeometry | None  # только видимая часть
    photos: list[Photo]
    is_owner: bool
    owner: OwnerExtras | None
    km_marks: list[KmMark]
    match: MatchInfo | None  # только автору
    attempt_of: RootRef | None  # трек — попытка в группе этого маршрута
    group_runners: int  # бегунов в группе маршрута этого трека (с автором)
    achievements: list[AchievementBadge]  # полученные этой попыткой


class TrackUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    visibility: VisibilityLiteral | None = None
    publish: bool = False
    detach: bool = False  # «Не засчитывать» — трек не попадает в группы


class UploadError(BaseModel):
    code: str
    detail: str
    track_id: uuid.UUID | None = None
    retry_after_s: int | None = None


def _error(status_code: int, code: str, detail: str, **extra: Any) -> JSONResponse:
    body = UploadError(code=code, detail=detail, **extra).model_dump(mode="json")
    headers = {"Retry-After": str(extra["retry_after_s"])} if extra.get("retry_after_s") else None
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def _summary(track: Track) -> TrackSummary:
    reason = RejectReason(track.reject_reason) if track.reject_reason else None
    return TrackSummary(
        id=track.id,
        status=track.status,  # type: ignore[arg-type]
        reject_reason=track.reject_reason,
        reject_message=REJECT_MESSAGES[reason] if reason else None,
        visibility=track.visibility,  # type: ignore[arg-type]
        title=track.title,
        started_at=track.started_at,
        distance_m=track.distance_m,
        total_time_s=track.total_time_s,
        avg_pace_s_per_km=track.avg_pace_s_per_km,
        category=track.category,
        created_at=track.created_at,
        is_attempt=track.parent_track_id is not None,
        attempt_root_id=track.parent_track_id,
    )


def _detail(db: DbDep, track: Track, viewer: User | None) -> TrackDetail:
    user = tracks_repo.author(db, track)
    is_owner = viewer is not None and viewer.id == track.user_id
    owner = None
    if is_owner:
        home = get_home(db, user)
        owner = OwnerExtras(
            full_geometry=tracks_repo.geojson(db, track.id, "full_display_geometry"),  # type: ignore[arg-type]
            hidden_zone=(
                HiddenZone(lat=home[0], lon=home[1], radius_m=user.hide_radius_m)
                if home and user.hide_radius_m
                else None
            ),
            fully_hidden=track.fully_hidden,
        )
    return TrackDetail(
        **_summary(track).model_dump(),
        description=track.description,
        moving_time_s=track.moving_time_s,
        elevation_gain_m=track.elevation_gain_m,
        has_elevation=track.has_elevation,
        splits=[
            Split(idx=s.idx, distance_m=s.distance_m, time_s=s.time_s)
            for s in tracks_repo.splits(db, track.id)
        ],
        author=author_of(user),
        geometry=tracks_repo.geojson(db, track.id, "display_geometry"),  # type: ignore[arg-type]
        photos=[
            Photo(id=p.id, url=f"/tracks/{track.id}/photos/{p.id}")
            for p in tracks_repo.photos(db, track.id)
        ],
        is_owner=is_owner,
        owner=owner,
        km_marks=[KmMark.model_validate(m) for m in km_marks(db, track)],
        match=_match_info(db, track) if is_owner else None,
        attempt_of=_root_ref(db, track.parent_track_id) if track.parent_track_id else None,
        group_runners=(
            tracks_repo.runners_count(db, root_of(db, track).id)
            if track.status == TrackStatus.published.value
            else 0
        ),
        achievements=[AchievementBadge.of(a) for a in track_achievements(db, track.id)],
    )


def _match_info(db: DbDep, track: Track) -> MatchInfo | None:
    attempt = attempt_row(db, track.id)
    if attempt is None:
        return None
    ref = _root_ref(db, attempt.root_track_id)
    if ref is None:
        return None
    return MatchInfo(
        root=ref,
        state=attempt.state,  # type: ignore[arg-type]
        result_time_s=attempt.result_time_s,
        diff_s=attempt.diff_s,
        beat=attempt.beat,
        equal=verdict(attempt.diff_s, tie_threshold_s(db)).equal,
        by_author=attempt.by_author,
        trimmed=attempt.trimmed,
        segment_distance_m=attempt.segment_distance_m,
        hidden_time_s=attempt.hidden_time_s,
    )


def _root_ref(db: DbDep, root_id: uuid.UUID) -> RootRef | None:
    found = tracks_repo.with_author(db, root_id)
    return root_ref(*found) if found else None


def _own_track(db: DbDep, track_id: uuid.UUID, user: User) -> Track:
    track = db.get(Track, track_id)
    if track is None or track.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Трек не найден")
    return track


def _visible_track(db: DbDep, track_id: uuid.UUID, viewer: User | None) -> Track:
    track = db.get(Track, track_id)
    if track is None or not tracks_repo.can_view(track, viewer.id if viewer else None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Трек не найден")
    return track


# ---------- Загрузка ----------


@router.post(
    "/tracks",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TrackSummary,
    responses={
        409: {"model": UploadError, "description": "Этот трек уже есть"},
        413: {"model": UploadError, "description": "Файл больше лимита"},
        415: {"model": UploadError, "description": "Формат не поддерживается"},
        429: {"model": UploadError, "description": "Лимит загрузок в час"},
    },
)
def upload_track(
    file: Annotated[UploadFile, File()],
    user: CurrentUser,
    db: DbDep,
    cfg: ConfigDep,
    queue: QueueDep,
) -> Any:
    # Обычный def: FastAPI выполнит его в пуле потоков, блокирующие S3 и БД не держат event loop.
    max_bytes = int(get_setting(db, "upload.max_file_bytes"))
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        return _error(413, "too_large", REJECT_MESSAGES[RejectReason.too_large])
    fmt = detect_format(data[:4096])
    if fmt is None:
        return _error(415, "unsupported_format", REJECT_MESSAGES[RejectReason.unsupported_format])
    sha = hashlib.sha256(data).hexdigest()
    existing = tracks_repo.find_duplicate(db, user.id, sha)
    if existing is not None:
        return _error(409, "duplicate", "Этот трек уже есть", track_id=existing.id)

    limit = int(get_setting(db, "upload.rate_limit_per_hour"))
    retry_after = RateLimiter(cfg).hit_sliding("upload", str(user.id), limit, 3600)
    if retry_after is not None:
        minutes = max(1, (retry_after + 59) // 60)
        return _error(
            429,
            "rate_limited",
            f"Не больше {limit} загрузок в час. Можно продолжить через {minutes} мин",
            retry_after_s=retry_after,
        )

    track = Track(
        user_id=user.id,
        status=TrackStatus.processing.value,
        file_format=fmt.value,
        file_size=len(data),
        file_sha256=sha,
        source_name=(file.filename or "")[:255] or None,
    )
    db.add(track)
    try:
        db.flush()
    except IntegrityError:  # тот же файл пришёл параллельным запросом
        db.rollback()
        existing = tracks_repo.find_duplicate(db, user.id, sha)
        return _error(409, "duplicate", "Этот трек уже есть", track_id=existing and existing.id)
    s3_client(cfg, timeout_s=60).put_object(Bucket=cfg.s3_bucket, Key=source_key(track), Body=data)
    db.commit()
    queue.process_track(track.id)
    return _summary(track)


# ---------- Чтение ----------


@router.get("/tracks/{track_id}", responses={404: {"description": "Трек не найден"}})
def read_track(track_id: uuid.UUID, db: DbDep, viewer: OptionalUser) -> TrackDetail:
    return _detail(db, _visible_track(db, track_id, viewer), viewer)


@router.get("/me/tracks")
def my_tracks(user: CurrentUser, db: DbDep) -> list[TrackSummary]:
    fresh = new_attempts(db, user.id)
    out = []
    for t in tracks_repo.user_tracks(db, user.id, public_only=False):
        item = _summary(t)
        item.new_attempts = fresh.get(t.id, 0)
        out.append(item)
    return out


@router.get("/users/{user_id}/tracks")
def user_tracks(user_id: uuid.UUID, db: DbDep) -> list[TrackSummary]:
    return [_summary(t) for t in tracks_repo.user_tracks(db, user_id, public_only=True)]


# ---------- Публикация, редактирование, удаление ----------


@router.patch(
    "/tracks/{track_id}",
    responses={404: {"description": "Трек не найден"}, 409: {"description": "Трек не готов"}},
)
def update_track(
    track_id: uuid.UUID, body: TrackUpdate, user: CurrentUser, db: DbDep
) -> TrackDetail:
    track = _own_track(db, track_id, user)
    if track.status not in tracks_repo.PROCESSED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Трек ещё не обработан")
    fields = body.model_fields_set
    if "title" in fields:
        track.title = (body.title or "").strip() or None
    if "description" in fields:
        track.description = (body.description or "").strip() or None
    if body.visibility is not None:
        if track.fully_hidden and body.visibility != Visibility.private.value:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, FULLY_HIDDEN_MESSAGE)
        track.visibility = body.visibility
    if body.publish:
        if not track.title:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Укажите название трека")
        track.status = TrackStatus.published.value
        track.published_at = track.published_at or datetime.now(UTC)
    if body.detach:
        detach(db, track)
    db.flush()
    if track.status == TrackStatus.published.value:
        sync_group(db, track)  # привязка к маршруту или выход из группы по видимости
    db.commit()
    db.refresh(track)
    return _detail(db, track, user)


@router.delete("/tracks/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_track(track_id: uuid.UUID, user: CurrentUser, db: DbDep, cfg: ConfigDep) -> None:
    track = _own_track(db, track_id, user)
    if has_group(db, track.id):
        # ФТ-9: исходный трек с попытками только прячется — группа и таблица остаются
        soft_delete_root(track)
        db.commit()
        return
    prefix = track_prefix(track.user_id, track.id)
    db.delete(track)
    db.commit()
    delete_prefix(cfg, prefix)  # после commit: при откате БД файлы остаются целы


# ---------- Фото ----------


@router.post(
    "/tracks/{track_id}/photos",
    status_code=status.HTTP_201_CREATED,
    response_model=Photo,
    responses={
        413: {"model": UploadError},
        415: {"model": UploadError},
        422: {"model": UploadError, "description": "Не больше 5 фото"},
    },
)
def add_photo(
    track_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    user: CurrentUser,
    db: DbDep,
    cfg: ConfigDep,
) -> Any:
    track = _own_track(db, track_id, user)
    max_photos = int(get_setting(db, "upload.max_photos"))
    if len(tracks_repo.photos(db, track.id)) >= max_photos:
        return _error(422, "too_many_photos", f"не больше {max_photos} фото")
    max_bytes = int(get_setting(db, "upload.max_photo_bytes"))
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        return _error(413, "too_large", f"фото больше {max_bytes // (1024 * 1024)} МБ")
    try:
        clean, content_type, ext = sanitize(data)
    except BadPhotoError:
        return _error(415, "unsupported_format", "нужно фото JPEG, PNG или WebP")
    photo = TrackPhoto(track_id=track.id, s3_key="", content_type=content_type)
    db.add(photo)
    db.flush()
    photo.s3_key = f"{track_prefix(track.user_id, track.id)}photos/{photo.id}.{ext}"
    s3_client(cfg, timeout_s=30).put_object(
        Bucket=cfg.s3_bucket, Key=photo.s3_key, Body=clean, ContentType=content_type
    )
    db.commit()
    return Photo(id=photo.id, url=f"/tracks/{track.id}/photos/{photo.id}")


def _photo(db: DbDep, track: Track, photo_id: uuid.UUID) -> TrackPhoto:
    photo = db.get(TrackPhoto, photo_id)
    if photo is None or photo.track_id != track.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Фото не найдено")
    return photo


@router.get(
    "/tracks/{track_id}/photos/{photo_id}",
    response_class=Response,
    responses={200: {"content": {"image/*": {}}}},
)
def read_photo(
    track_id: uuid.UUID, photo_id: uuid.UUID, db: DbDep, cfg: ConfigDep, viewer: OptionalUser
) -> Response:
    photo = _photo(db, _visible_track(db, track_id, viewer), photo_id)
    body = s3_client(cfg, timeout_s=30).get_object(Bucket=cfg.s3_bucket, Key=photo.s3_key)
    return Response(
        content=body["Body"].read(),
        media_type=photo.content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.delete("/tracks/{track_id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo(
    track_id: uuid.UUID, photo_id: uuid.UUID, user: CurrentUser, db: DbDep, cfg: ConfigDep
) -> None:
    photo = _photo(db, _own_track(db, track_id, user), photo_id)
    key = photo.s3_key
    db.delete(photo)
    db.commit()
    s3_client(cfg, timeout_s=30).delete_object(Bucket=cfg.s3_bucket, Key=key)
