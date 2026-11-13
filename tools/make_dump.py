"""Тестовый дамп из реальных треков: изменённые копии от вымышленных бегунов.

    python3 -I tools/make_dump.py tracks tracks-dump

Вход — папка с GPX, разложенными по сериям (подпапка = серия маршрута). Для каждого трека
делается 1–2 копии от разных бегунов; копии чуть отличаются, чтобы не совпадать с оригиналом
один в один и не ловиться как дубликат, когда оригинал загружают сами:
- темп: время всей пробежки масштабируется в 0,93–1,07 раза;
- дата: пробежка переносится на случайный день за последние 45 дней (часть — «новые»);
- координаты: смещение до 4 м целиком плюс плавное «дыхание» до ~3 м вдоль маршрута
  (независимый шум на каждую точку раздул бы дистанцию зигзагом), выброшено ~10% точек.
Маршрут остаётся тем же — копии и оригиналы должны сопоставляться (add-route-matching).

Каждому бегуну задаётся точка дома у самого частого места старта исходных треков (с разбросом
до 30 м) и радиус 350–450 м, чтобы на карте не было видно, где начинаются реальные пробежки.

Результат: <dst>/<серия>/<бегун>_<дата>.gpx и <dst>/manifest.json для tools/load_dump.py.
Только стандартная библиотека.
"""

import json
import math
import random
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from pathlib import Path

SEED = 20261113
RUNNERS = [
    ("Марина В.", "marina"),
    ("Олег Т.", "oleg"),
    ("Сергей Н.", "sergey"),
    ("Анна Л.", "anna"),
    ("Кирилл Д.", "kirill"),
    ("Полина Р.", "polina"),
]
SERIES_TITLES = {
    "00_odinochnye": None,  # у одиночных — своё название по дистанции
    "01_5km_3-probezhki": "Пятёрка у дома",
    "02_8km_3-probezhki": "Восьмёрка через сопку",
    "03_10km_2-probezhki": "Десятка по набережной",
    "04_10km_2-probezhki": "Большая десятка",
    "05_5km_3-probezhki_so-srezkoj": "Пятёрка со срезкой",
    "06_3km_2-probezhki_linejnyj": "Трёшка в одну сторону",
}
GPX_NS = "http://www.topografix.com/GPX/1/1"
M_PER_DEG = 111_320.0


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def read(path: Path) -> list[tuple[float, float, datetime, float | None]]:
    pts = []
    for el in ET.parse(path).getroot().iter():
        if local(el.tag) != "trkpt":
            continue
        t = ele = None
        for c in el:
            if local(c.tag) == "time" and c.text:
                t = datetime.fromisoformat(c.text.strip().replace("Z", "+00:00"))
            if local(c.tag) == "ele" and c.text:
                ele = float(c.text)
        if t is not None:
            pts.append((float(el.attrib["lat"]), float(el.attrib["lon"]), t, ele))
    return pts


def distance_m(pts: list[tuple[float, float, datetime, float | None]]) -> float:
    total = 0.0
    for (la1, lo1, *_), (la2, lo2, *_) in zip(pts, pts[1:], strict=False):
        dy = (la2 - la1) * M_PER_DEG
        dx = (lo2 - lo1) * M_PER_DEG * math.cos(math.radians(la1))
        total += math.hypot(dx, dy)
    return total


def vary(pts, rnd: random.Random, now: datetime):
    pace = rnd.uniform(0.93, 1.07)
    day = (now - timedelta(days=rnd.randint(0, 45))).date()
    t0 = pts[0][2]
    start = datetime.combine(day, t0.timetz())
    shift_e, shift_n = rnd.uniform(-4, 4), rnd.uniform(-4, 4)
    # Плавное смещение: две синусоиды с периодом в сотни точек и случайной фазой.
    period_e, period_n = rnd.uniform(150, 400), rnd.uniform(150, 400)
    phase_e, phase_n = rnd.uniform(0, 2 * math.pi), rnd.uniform(0, 2 * math.pi)
    out = []
    for i, (lat, lon, t, ele) in enumerate(pts):
        if 0 < i < len(pts) - 1 and rnd.random() < 0.10:
            continue
        e = shift_e + 3 * math.sin(2 * math.pi * i / period_e + phase_e)
        n = shift_n + 3 * math.sin(2 * math.pi * i / period_n + phase_n)
        new_lat = lat + n / M_PER_DEG
        new_lon = lon + e / (M_PER_DEG * math.cos(math.radians(lat)))
        new_t = start + (t - t0) * pace
        out.append((new_lat, new_lon, new_t, ele))
    return out


def write(pts, name: str, path: Path) -> None:
    ET.register_namespace("", GPX_NS)
    gpx = ET.Element(f"{{{GPX_NS}}}gpx", {"version": "1.1", "creator": "runners-dump"})
    trk = ET.SubElement(gpx, f"{{{GPX_NS}}}trk")
    ET.SubElement(trk, f"{{{GPX_NS}}}name").text = name
    seg = ET.SubElement(trk, f"{{{GPX_NS}}}trkseg")
    for lat, lon, t, ele in pts:
        el = ET.SubElement(seg, f"{{{GPX_NS}}}trkpt", {"lat": f"{lat:.7f}", "lon": f"{lon:.7f}"})
        if ele is not None:
            ET.SubElement(el, f"{{{GPX_NS}}}ele").text = f"{ele:.1f}"
        ET.SubElement(el, f"{{{GPX_NS}}}time").text = t.astimezone(UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(gpx).write(path, encoding="UTF-8", xml_declaration=True)


def flat_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    dy = (b[0] - a[0]) * M_PER_DEG
    dx = (b[1] - a[1]) * M_PER_DEG * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def common_start(starts: list[tuple[float, float]], radius: float = 200) -> tuple[float, float]:
    """Центр самого «плотного» места старта: у кого больше всего соседей в radius метров."""
    best = max(starts, key=lambda s: sum(flat_m(s, o) < radius for o in starts))
    near = [o for o in starts if flat_m(best, o) < radius]
    return (sum(o[0] for o in near) / len(near), sum(o[1] for o in near) / len(near))


def title_for(series: str, km: float) -> str:
    base = SERIES_TITLES.get(series)
    if base:
        return base
    return f"Маршрут на {km:.0f} км" if km >= 2 else "Короткий маршрут"


def main(src: Path, dst: Path) -> None:
    rnd = random.Random(SEED)
    now = datetime.now(UTC)
    files = sorted(src.rglob("*.gpx"))
    starts = [(p[0][0], p[0][1]) for p in (read(f) for f in files) if p]
    home = common_start(starts)
    runners: dict[str, dict] = {}
    entries = []
    turn = 0
    for f in files:
        series = f.parent.name
        pts = read(f)
        if len(pts) < 10:
            continue
        km = distance_m(pts) / 1000
        copies = 2 if series != "00_odinochnye" and f == sorted(f.parent.glob("*.gpx"))[0] else 1
        for _ in range(copies):
            name, slug = RUNNERS[turn % len(RUNNERS)]
            turn += 1
            variant = vary(pts, rnd, now)
            date = variant[0][2].strftime("%Y%m%d")
            out = dst / series / f"{slug}_{date}_{f.name[:8]}.gpx"
            write(variant, title_for(series, km), out)
            runners.setdefault(
                slug,
                {
                    "name": name,
                    "email": f"{slug}@example.com",
                    "city": "Владивосток",
                    "home": {
                        "lat": round(home[0] + rnd.uniform(-30, 30) / M_PER_DEG, 6),
                        "lon": round(
                            home[1]
                            + rnd.uniform(-30, 30) / (M_PER_DEG * math.cos(math.radians(home[0]))),
                            6,
                        ),
                    },
                    "hide_radius_m": rnd.choice([350, 400, 450]),
                },
            )
            entries.append(
                {
                    "file": str(out.relative_to(dst)),
                    "runner": slug,
                    "series": series,
                    "title": title_for(series, km),
                    "source": f.name[:8],
                }
            )
    manifest = {"runners": runners, "tracks": entries}
    (dst / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"{len(entries)} треков от {len(runners)} бегунов -> {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
