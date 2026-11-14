import uuid

from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.infra.identity import Identity
from app.infra.models import Role, User


def get_or_create_user(session: Session, identity: Identity) -> User:
    user = session.execute(
        select(User).where(User.google_sub == identity.subject)
    ).scalar_one_or_none()
    if user is None:
        user = User(
            google_sub=identity.subject,
            email=identity.email,
            name=identity.name,
            avatar_url=identity.avatar_url,
            role=Role.runner.value,
        )
        session.add(user)
        session.flush()
    return user


def get_user(session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id)


def get_home(session: Session, user: User) -> tuple[float, float] | None:
    """Возвращает (lat, lon) точки дома."""
    if user.home_point is None:
        return None
    geom = cast(User.home_point, Geometry)
    row = session.execute(select(func.ST_Y(geom), func.ST_X(geom)).where(User.id == user.id)).one()
    return float(row[0]), float(row[1])


def set_home(user: User, lat: float | None, lon: float | None) -> None:
    if lat is None or lon is None:
        user.home_point = None
    else:
        user.home_point = func.ST_GeogFromText(f"SRID=4326;POINT({lon:.7f} {lat:.7f})")


def set_role_by_email(session: Session, email: str, role: Role) -> User:
    user = session.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()
    if user is None:
        raise LookupError(email)
    user.role = role.value
    return user
