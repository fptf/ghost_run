import uuid

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator

from app.api.auth import REFRESH_COOKIE
from app.api.deps import ConfigDep, CurrentUser, DbDep
from app.domain.privacy import RadiusBounds, RadiusOutOfRangeError, validate_hide_radius
from app.infra.account_cleanup import run_cleanups
from app.infra.models import User
from app.infra.settings_repo import get_setting
from app.infra.users_repo import get_home, get_user, set_home

router = APIRouter(tags=["users"])


class ProfileStats(BaseModel):
    runs: int = 0
    total_distance_m: int = 0
    # Личные рекорды: код категории -> лучшее время, с (заполняется в add-track-upload).
    records: dict[str, int] = Field(default_factory=dict)


class PublicProfile(BaseModel):
    id: uuid.UUID
    name: str
    avatar_url: str | None
    city: str | None
    about: str | None
    stats: ProfileStats


class HomePoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class OwnProfile(PublicProfile):
    email: str
    role: str
    home: HomePoint | None
    hide_radius_m: int | None
    new_attempts: int = 0  # счётчик новых попыток (сценарий В), появится в add-route-matching


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    about: str | None = Field(default=None, max_length=1000)
    home: HomePoint | None = None
    hide_radius_m: int | None = None

    @model_validator(mode="after")
    def _home_and_radius_together(self) -> "ProfileUpdate":
        fields = self.model_fields_set
        if "home" in fields and self.home is not None and "hide_radius_m" not in fields:
            raise ValueError("Вместе с точкой дома укажите радиус скрытой зоны")
        return self


def _public(user: User) -> PublicProfile:
    return PublicProfile(
        id=user.id,
        name=user.name,
        avatar_url=user.avatar_url,
        city=user.city,
        about=user.about,
        stats=ProfileStats(),
    )


def _own(db: DbDep, user: User) -> OwnProfile:
    home = get_home(db, user)
    return OwnProfile(
        **_public(user).model_dump(),
        email=user.email,
        role=user.role,
        home=HomePoint(lat=home[0], lon=home[1]) if home else None,
        hide_radius_m=user.hide_radius_m,
    )


@router.get("/me")
def read_me(user: CurrentUser, db: DbDep) -> OwnProfile:
    return _own(db, user)


@router.patch("/me", responses={422: {"description": "Недопустимые значения"}})
def update_me(body: ProfileUpdate, user: CurrentUser, db: DbDep) -> OwnProfile:
    fields = body.model_fields_set
    if "name" in fields and body.name is not None:
        user.name = body.name
    if "city" in fields:
        user.city = body.city or None
    if "about" in fields:
        user.about = body.about or None
    if "hide_radius_m" in fields and body.hide_radius_m is not None:
        bounds = RadiusBounds.from_setting(get_setting(db, "privacy.hide_radius_m"))
        try:
            validate_hide_radius(body.hide_radius_m, bounds)
        except RadiusOutOfRangeError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
        user.hide_radius_m = body.hide_radius_m
    if "home" in fields:
        set_home(user, body.home.lat if body.home else None, body.home.lon if body.home else None)
        if body.home is None:
            user.hide_radius_m = None
    db.commit()
    db.refresh(user)
    return _own(db, user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(response: Response, user: CurrentUser, db: DbDep, cfg: ConfigDep) -> None:
    run_cleanups(cfg, user.id)
    db.delete(user)  # refresh-токены удаляются каскадом
    db.commit()
    response.delete_cookie(REFRESH_COOKIE, path="/")


@router.get("/users/{user_id}", responses={404: {"description": "Пользователь не найден"}})
def read_profile(user_id: uuid.UUID, db: DbDep) -> PublicProfile:
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    return _public(user)
