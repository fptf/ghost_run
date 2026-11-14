"""Синтетические треки для особых случаев (остановки, выбросы, «транспорт», без времени)."""

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pyproj import Geod

ORIGIN = (45.0, 10.0)  # условная точка для синтетических треков
T0 = datetime(2026, 10, 1, 7, 0, tzinfo=UTC)


@dataclass
class P:
    lat: float
    lon: float
    t: datetime | None
    ele: float | None = None


GEOD = Geod(ellps="WGS84")


def offset(lat: float, lon: float, east_m: float, north_m: float) -> tuple[float, float]:
    """Точная геодезическая точка в east_m/north_m метрах от (lat, lon)."""
    distance = math.hypot(east_m, north_m)
    if distance == 0:
        return lat, lon
    azimuth = math.degrees(math.atan2(east_m, north_m))
    lon2, lat2, _ = GEOD.fwd(lon, lat, azimuth, distance)
    return lat2, lon2


def straight(
    distance_m: float,
    pace_s_per_km: float = 300.0,
    step_s: float = 1.0,
    start: tuple[float, float] = ORIGIN,
    bearing_deg: float = 0.0,
    stops: dict[float, float] | None = None,
    ele: bool = False,
) -> list[P]:
    """Прямой отрезок с постоянным темпом; stops — {дистанция, м: длительность остановки, с}."""
    speed = 1000.0 / pace_s_per_km
    pending = dict(sorted((stops or {}).items()))
    pts: list[P] = []
    d, t = 0.0, 0.0
    b = math.radians(bearing_deg)
    while True:
        lat, lon = offset(*start, d * math.sin(b), d * math.cos(b))
        elevation = 100 + 25 * math.sin(d / 500 * math.pi) if ele else None
        pts.append(P(lat, lon, T0 + timedelta(seconds=t), elevation))
        for at in list(pending):
            if d >= at:
                pause = pending.pop(at)
                for k in range(1, int(pause // step_s) + 1):
                    pts.append(P(lat, lon, T0 + timedelta(seconds=t + k * step_s), elevation))
                t += pause
        if d >= distance_m:
            return pts
        d = min(distance_m, d + speed * step_s)
        t += step_s


def circle(center: tuple[float, float], radius_m: float, laps: float = 1.0, pace: float = 300.0):
    """Круг вокруг центра (для трека целиком в скрытой зоне)."""
    length = 2 * math.pi * radius_m * laps
    speed = 1000.0 / pace
    n = int(length / speed)
    return [
        P(
            *offset(*center, radius_m * math.cos(i * speed / radius_m),
                    radius_m * math.sin(i * speed / radius_m)),
            T0 + timedelta(seconds=i),
        )
        for i in range(n + 1)
    ]  # fmt: skip


def to_gpx(points: list[P], pretty: bool = False) -> bytes:
    nl = "\n    " if pretty else ""
    rows = []
    for p in points:
        ele = f"<ele>{p.ele:.1f}</ele>" if p.ele is not None else ""
        time = f"<time>{p.t.strftime('%Y-%m-%dT%H:%M:%SZ')}</time>" if p.t else ""
        rows.append(f'<trkpt lat="{p.lat:.7f}" lon="{p.lon:.7f}">{nl}{ele}{time}</trkpt>')
    body = "\n".join(rows)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="tests" xmlns="http://www.topografix.com/GPX/1/1">'
        f"<trk><trkseg>\n{body}\n</trkseg></trk></gpx>\n"
    ).encode()
