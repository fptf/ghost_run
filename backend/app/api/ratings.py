import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import DbDep
from app.api.schemas import Author, author_of
from app.infra.ratings_service import rating

router = APIRouter(tags=["ratings"])


class RatingItem(BaseModel):
    place: int
    track_id: uuid.UUID
    title: str | None
    distance_m: float | None
    total_time_s: float | None
    avg_pace_s_per_km: float | None
    author: Author
    runners: int
    downloads: int
    value: float
    computed_at: datetime


@router.get("/ratings")
def read_rating(
    db: DbDep,
    category: Literal["1", "5", "10", "21", "21+"],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[RatingItem]:
    return [
        RatingItem(
            place=i,
            track_id=track.id,
            title=track.title,
            distance_m=track.distance_m,
            total_time_s=track.total_time_s,
            avg_pace_s_per_km=track.avg_pace_s_per_km,
            author=author_of(user),
            runners=score.runners,
            downloads=score.downloads,
            value=score.value,
            computed_at=score.computed_at,
        )
        for i, (score, track, user) in enumerate(rating(db, category, limit), start=1)
    ]
