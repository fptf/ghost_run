"""Общие тестовые хелперы: вход, загрузка и публикация треков, фикстуры пробежек, геометрия."""

import io
import itertools
import math
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image

from app.domain.tracks.metrics import MetricsConfig
from app.domain.tracks.model import FileFormat
from app.domain.tracks.pipeline import GeometryConfig, ProcessedTrack, process
from tests.gpx_factory import ORIGIN, T0, P, offset, straight, to_gpx

FIXTURES = Path(__file__).parent / "fixtures" / "tracks"
Headers = dict[str, str]
Points = list[tuple[float, float, float]]  # lon, lat, секунды от старта

ROOT, SAME = "20261026", "20261101"  # одна «пятёрка», 01.11 быстрее на ~1,5 мин


# --- Геометрия и файлы -----------------------------------------------------------------------


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6371008.8
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = (
        math.sin((la2 - la1) / 2) ** 2
        + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(h))


def jpeg_with_gps() -> bytes:
    img = Image.new("RGB", (3000, 2000), (200, 80, 20))
    exif = Image.Exif()
    exif[0x8825] = {1: "N", 2: (55.0, 45.0, 0.0), 3: "E", 4: (37.0, 37.0, 0.0)}  # GPSInfo
    exif[0x010F] = "PhoneMaker"
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


_RUN_SEQ = itertools.count(uuid.uuid4().int % 20_000)


def unique_run(distance: float = 3000, **kw: Any) -> bytes:
    """Каждый вызов — новый файл (сдвиг старта), чтобы не срабатывала защита от дубликатов."""
    shift = next(_RUN_SEQ) % 20_000  # по счётчику: случайный сдвиг изредка совпадал
    return to_gpx(straight(distance, start=offset(*ORIGIN, shift, 0), **kw))


# --- Реальные пробежки -----------------------------------------------------------------------

_cache: dict[str, ProcessedTrack] = {}


def fx(
    date: str, home: tuple[float, float] | None = None, radius: float | None = None
) -> ProcessedTrack:
    """Обработанная фикстура run_<date>.gpx (с кешем)."""
    key = f"{date}:{home}:{radius}"
    if key not in _cache:
        data = (FIXTURES / f"run_{date}.gpx").read_bytes()
        _cache[key] = process(data, FileFormat.gpx, home, radius, MetricsConfig(), GeometryConfig())
    return _cache[key]


def path_before(start_lonlat: tuple[float, float], meters: float, pace: float = 330) -> Points:
    """Разминка: прямой отрезок, заканчивающийся в точке старта (без времени)."""
    lon, lat = start_lonlat
    pts = straight(meters, pace_s_per_km=pace, start=offset(lat, lon, -meters, 0), bearing_deg=90)
    t0 = pts[0].t
    return [(p.lon, p.lat, (p.t - t0).total_seconds()) for p in pts]  # type: ignore[operator]


def fixture_points(date: str) -> Points:
    return [(x, y, m) for x, y, _, m in fx(date).full]


_PLACES = itertools.count()


def place() -> tuple[float, float]:
    """Сдвиг (Δlat, Δlon) в своё место для каждого теста.

    Клетки сетки 0,5° × 1° не пересекаются: маршрут одного теста не засчитает попытку другого
    (случайный сдвиг изредка сводил два теста в одно место).
    """
    k = next(_PLACES)
    return -2 + (k // 100) * 0.5, -50 + (k % 100) * 1.0


def gpx(points: Points, where: tuple[float, float], scale: float = 1.0, days_ago: float = 0,
        jitter_m: float = 0.0) -> bytes:  # fmt: skip
    """GPX из точек, перенесённых в своё место, с темпом ×scale и датой days_ago дней назад."""
    dlat, dlon = where
    start = T0 - timedelta(days=days_ago)
    out = []
    for i, (lon, lat, t) in enumerate(points):
        lat2, lon2 = lat + dlat, lon + dlon
        if jitter_m:
            lat2, lon2 = offset(lat2, lon2, jitter_m * ((i % 3) - 1), 0)
        out.append(P(lat2, lon2, start + timedelta(seconds=t * scale)))
    return to_gpx(out)


# --- API -------------------------------------------------------------------------------------


def dev_login(client: TestClient, email: str | None = None, name: str = "Бегун") -> Headers:
    """Входит через dev-вход и возвращает заголовок авторизации."""
    email = email or f"{uuid.uuid4().hex[:10]}@example.com"
    resp = client.post("/auth/dev-login", json={"email": email, "name": name})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def upload(client: TestClient, headers: Headers, data: bytes, name: str = "run.gpx") -> Any:
    return client.post("/tracks", headers=headers, files={"file": (name, data)})


def uploaded(client: TestClient, headers: Headers, data: bytes, name: str = "run.gpx") -> Any:
    resp = upload(client, headers, data, name)
    assert resp.status_code == 202, resp.text
    return client.get(f"/tracks/{resp.json()['id']}", headers=headers).json()


def publish(client: TestClient, headers: Headers, track_id: str, visibility: str) -> None:
    resp = client.patch(
        f"/tracks/{track_id}", headers=headers, json={"visibility": visibility, "publish": True}
    )
    assert resp.status_code == 200, resp.text


def published(client: TestClient, h: Headers, data: bytes, visibility: str = "public") -> Any:
    track = uploaded(client, h, data)
    assert track["status"] == "draft", track
    publish(client, h, track["id"], visibility)
    return client.get(f"/tracks/{track['id']}", headers=h).json()


def set_home(client: TestClient, headers: Headers, home: tuple[float, float], radius: int) -> None:
    resp = client.patch(
        "/me",
        headers=headers,
        json={"home": {"lat": home[0], "lon": home[1]}, "hide_radius_m": radius},
    )
    assert resp.status_code == 200, resp.text
