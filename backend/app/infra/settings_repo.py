"""Сервис настроек: каждое чтение идёт в БД, кеша в процессе нет.

Так изменение значения в таблице `settings` видно сразу, без перезапуска.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.models import Setting


class SettingNotFoundError(KeyError):
    pass


def get_setting(session: Session, key: str) -> Any:
    value = session.execute(select(Setting.value).where(Setting.key == key)).scalar_one_or_none()
    if value is None:
        raise SettingNotFoundError(key)
    return value


def set_setting(session: Session, key: str, value: Any) -> None:
    session.merge(Setting(key=key, value=value))


def all_settings(session: Session) -> dict[str, Any]:
    return {row.key: row.value for row in session.execute(select(Setting)).scalars()}
