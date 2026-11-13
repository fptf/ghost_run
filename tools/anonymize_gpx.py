"""Обезличивание GPX для тестовых фикстур.

    python3 -I tools/anonymize_gpx.py <папка с исходными GPX> <папка назначения>

Что делает с треками:
- все треки вместе поворачиваются на случайный угол и переносятся в случайное место Земли.
  Взаимное расположение и расстояния сохраняются (погрешность — доли процента), а параметры
  преобразования берутся из os.urandom при каждом запуске и нигде не сохраняются: восстановить
  исходные координаты по фикстурам нельзя;
- у незамкнутых треков срезается по TRIM_M метров с начала и конца — убирает окрестности дома;
- у круговых (старт и финиш ближе LOOP_M) старт переносится на LOOP_START_SHARE длины круга:
  круг остаётся кругом, но начинается не у дома;
- выбрасываются метаданные устройства, имя и расширения; остаются координаты, время и высота.

Имя результата — run_YYYYMMDD.gpx по первым 8 символам исходного имени. Повторный запуск даёт
другие координаты — тесты не должны зависеть от абсолютного положения фикстур.
Только стандартная библиотека: скрипт запускается без окружения проекта.
"""

import math
import os
import random
import statistics
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

TRIM_M = 500.0
LOOP_M = 50.0
LOOP_START_SHARE = 0.4
GPX_NS = "http://www.topografix.com/GPX/1/1"
R_EARTH = 6371008.8

Point = dict[str, str]


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = (
        math.sin((la2 - la1) / 2) ** 2
        + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    )
    return 2 * R_EARTH * math.asin(math.sqrt(h))


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def read_points(path: Path) -> list[Point]:
    points = []
    for el in ET.parse(path).getroot().iter():
        if local(el.tag) != "trkpt":
            continue
        pt = {"lat": el.attrib["lat"], "lon": el.attrib["lon"]}
        for child in el:
            if local(child.tag) in ("time", "ele") and child.text:
                pt[local(child.tag)] = child.text.strip()
        points.append(pt)
    return points


def coords(p: Point) -> tuple[float, float]:
    return float(p["lat"]), float(p["lon"])


def cumulative(points: list[Point]) -> list[float]:
    cum = [0.0]
    for a, b in zip(points, points[1:], strict=False):
        cum.append(cum[-1] + haversine(coords(a), coords(b)))
    return cum


def trim(points: list[Point], trim_m: float) -> list[Point]:
    cum = cumulative(points)
    total = cum[-1]
    if total <= 2 * trim_m + 100:
        raise ValueError(f"трек слишком короткий для среза: {total:.0f} м")
    return [p for p, d in zip(points, cum, strict=True) if trim_m <= d <= total - trim_m]


def _time(p: Point) -> datetime:
    return datetime.fromisoformat(p["time"].replace("Z", "+00:00"))


def restart_loop(points: list[Point], share: float) -> list[Point]:
    """Круг с другой точки старта: время идёт подряд, шаг на стыке — медианный."""
    cum = cumulative(points)
    k = next(i for i, d in enumerate(cum) if d >= cum[-1] * share)
    order = points[k:] + points[:k]
    if not all("time" in p for p in points):
        return order
    steps = [(_time(b) - _time(a)).total_seconds() for a, b in zip(points, points[1:], strict=False)]
    gap = timedelta(seconds=statistics.median(steps))
    t = _time(points[0])
    out = [{**order[0], "time": t.strftime("%Y-%m-%dT%H:%M:%SZ")}]
    for a, b in zip(order, order[1:], strict=False):
        dt = _time(b) - _time(a)
        t += dt if dt.total_seconds() > 0 else gap  # стык конца и начала исходного круга
        out.append({**b, "time": t.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return out


class Transform:
    """Поворот вокруг общего центра и перенос в случайное место, в локальной плоскости (м)."""

    def __init__(self, origin: tuple[float, float], rnd: random.Random) -> None:
        self.lat0, self.lon0 = origin
        self.angle = rnd.uniform(0, 2 * math.pi)
        self.lat1 = rnd.uniform(-55, 55)
        self.lon1 = rnd.uniform(-180, 180)

    def __call__(self, lat: float, lon: float) -> tuple[float, float]:
        x = math.radians(lon - self.lon0) * R_EARTH * math.cos(math.radians(self.lat0))
        y = math.radians(lat - self.lat0) * R_EARTH
        c, s = math.cos(self.angle), math.sin(self.angle)
        x, y = x * c - y * s, x * s + y * c
        lat2 = self.lat1 + math.degrees(y / R_EARTH)
        lon2 = self.lon1 + math.degrees(x / (R_EARTH * math.cos(math.radians(self.lat1))))
        return lat2, (lon2 + 180) % 360 - 180


def write_gpx(points: list[Point], name: str, path: Path, move: Transform) -> None:
    ET.register_namespace("", GPX_NS)
    gpx = ET.Element(f"{{{GPX_NS}}}gpx", {"version": "1.1", "creator": "runners-fixtures"})
    trk = ET.SubElement(gpx, f"{{{GPX_NS}}}trk")
    ET.SubElement(trk, f"{{{GPX_NS}}}name").text = name
    seg = ET.SubElement(trk, f"{{{GPX_NS}}}trkseg")
    for p in points:
        lat, lon = move(*coords(p))
        el = ET.SubElement(seg, f"{{{GPX_NS}}}trkpt", {"lat": f"{lat:.7f}", "lon": f"{lon:.7f}"})
        if "ele" in p:
            ET.SubElement(el, f"{{{GPX_NS}}}ele").text = p["ele"]
        if "time" in p:
            ET.SubElement(el, f"{{{GPX_NS}}}time").text = p["time"]
    ET.indent(gpx, space=" ")
    ET.ElementTree(gpx).write(path, encoding="UTF-8", xml_declaration=True)


def main(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    files = sorted(src.rglob("*.gpx"))
    tracks = {f: read_points(f) for f in files}
    starts = [coords(p[0]) for p in tracks.values() if p]
    origin = (statistics.fmean(s[0] for s in starts), statistics.fmean(s[1] for s in starts))
    move = Transform(origin, random.Random(int.from_bytes(os.urandom(16))))
    for f, points in tracks.items():
        name = f"run_{f.name[:8]}"
        is_loop = haversine(coords(points[0]), coords(points[-1])) < LOOP_M
        points = restart_loop(points, LOOP_START_SHARE) if is_loop else trim(points, TRIM_M)
        write_gpx(points, name, dst / f"{name}.gpx", move)
        kind = "круг, старт перенесён" if is_loop else "срез концов"
        print(f"{f.name} -> {name}.gpx ({len(points)} точек, {kind})")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
