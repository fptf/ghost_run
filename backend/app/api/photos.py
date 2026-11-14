"""Фото к трекам: загрузка (без метаданных), чтение и удаление."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status

from app.api.deps import ConfigDep, CurrentUser, DbDep, OptionalUser
from app.api.schemas import Photo, UploadError, error_response, photo_url
from app.api.tracks import own_track, visible_track
from app.infra import tracks_repo
from app.infra.models import Track, TrackPhoto
from app.infra.photos import BadPhotoError, sanitize
from app.infra.s3 import s3_client
from app.infra.settings_repo import get_setting
from app.infra.track_processing import track_prefix

router = APIRouter(tags=["tracks"])


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
    track = own_track(db, track_id, user)
    max_photos = int(get_setting(db, "upload.max_photos"))
    if len(tracks_repo.photos(db, track.id)) >= max_photos:
        return error_response(422, "too_many_photos", f"не больше {max_photos} фото")
    max_bytes = int(get_setting(db, "upload.max_photo_bytes"))
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        return error_response(413, "too_large", f"фото больше {max_bytes // (1024 * 1024)} МБ")
    try:
        clean, content_type, ext = sanitize(data)
    except BadPhotoError:
        return error_response(415, "unsupported_format", "нужно фото JPEG, PNG или WebP")
    photo = TrackPhoto(track_id=track.id, s3_key="", content_type=content_type)
    db.add(photo)
    db.flush()
    photo.s3_key = f"{track_prefix(track.user_id, track.id)}photos/{photo.id}.{ext}"
    s3_client(cfg, timeout_s=30).put_object(
        Bucket=cfg.s3_bucket, Key=photo.s3_key, Body=clean, ContentType=content_type
    )
    db.commit()
    return Photo(id=photo.id, url=photo_url(track.id, photo.id))


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
    photo = _photo(db, visible_track(db, track_id, viewer), photo_id)
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
    photo = _photo(db, own_track(db, track_id, user), photo_id)
    key = photo.s3_key
    db.delete(photo)
    db.commit()
    s3_client(cfg, timeout_s=30).delete_object(Bucket=cfg.s3_bucket, Key=key)
