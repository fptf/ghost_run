"""Демо-дамп со сценариями: ваши треки от компании из пяти бегунов, темп подобран под показ.

    python3 -I tools/make_demo_dump.py tracks tracks-demo

Идея: у каждого маршрута есть «автор» — копия одной из ваших пробежек с подобранным темпом.
Темп автора лежит между темпами ваших пробежек этой серии, поэтому, загружая оригиналы, вы
увидите и «Превзошли автора», и «Медленнее автора». Вокруг автора — попытки тех же бегунов:
быстрее и медленнее, повтор автора, несколько забегов одного бегуна, «Не засчитывать»,
приватный трек, трек «по ссылке», тот же путь в обратную сторону — отдельный маршрут.

Копии отличаются от оригиналов (обрезаны концы, сдвиг до 4 м, выброшено ~10% точек, другая
дата), поэтому не ловятся как дубликаты, но сопоставляются с тем же маршрутом.

Результат: <dst>/<серия>/<бегун>_<дата>_<исходник>.gpx и <dst>/manifest.json; порядок треков
в манифесте — порядок публикации (авторы маршрутов — первыми). Загрузка — tools/load_dump.py.
Только стандартная библиотека.
"""

import json
import math
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_dump import M_PER_DEG, distance_m, read, write  # noqa: E402

SEED = 20261114
RUNNERS = {
    "marina": "Марина В.",
    "oleg": "Олег Т.",
    "sergey": "Сергей Н.",
    "anna": "Анна Л.",
    "kirill": "Кирилл Д.",
}

# (серия, исходник, бегун, темп мин/км, дней назад, название, опции)
# Темп автора выбран между темпами ваших пробежек серии — см. «ожидания» в README дампа.
ROOT = "root"
SCENARIO: list[tuple[str, str, str, float, int, str, dict]] = [
    # --- 01 «Пятёрка у дома»: ваши 7:23 (14.05, с добавкой), 5:45 (22.05), 5:49 (29.05)
    ("01_5km_3-probezhki", "20250522", "oleg", 6.10, 58, "Пятёрка у дома", {ROOT: True}),
    ("01_5km_3-probezhki", "20250529", "marina", 6.40, 40, "", {}),
    ("01_5km_3-probezhki", "20250522", "sergey", 5.45, 21, "", {}),
    ("01_5km_3-probezhki", "20250522", "anna", 6.90, 30, "", {}),
    ("01_5km_3-probezhki", "20250529", "anna", 6.50, 6, "", {}),  # лучшая из двух
    ("01_5km_3-probezhki", "20250529", "oleg", 5.95, 3, "", {}),  # автор пробежал снова
    ("01_5km_3-probezhki", "20250522", "kirill", 6.00, 2, "", {"detach": True}),
    # --- 02 «Восьмёрка через сопку»: ваши 6:38 (04.06), 6:58 (11.06), 6:49 (01.07)
    ("02_8km_3-probezhki", "20260604", "marina", 6.35, 55, "Восьмёрка через сопку", {ROOT: True}),
    ("02_8km_3-probezhki", "20260604", "kirill", 7.20, 25, "", {}),
    ("02_8km_3-probezhki", "20260604", "sergey", 6.30, 4, "", {}),
    # --- 03 «Десятка по набережной»: ваши 6:02 (30.05), 5:22 (21.06)
    ("03_10km_2-probezhki", "20260621", "sergey", 5.70, 52, "Десятка по набережной", {ROOT: True}),
    ("03_10km_2-probezhki", "20260621", "anna", 6.50, 18, "", {}),
    ("03_10km_2-probezhki", "20260621", "oleg", 5.85, 1, "", {}),
    # --- 04 «Большая десятка»: ваши 6:11 (17.06), 5:56 (29.06)
    ("04_10km_2-probezhki", "20260617", "anna", 6.29, 50, "Большая десятка", {ROOT: True}),
    ("04_10km_2-probezhki", "20260629", "marina", 6.40, 27, "", {}),
    ("04_10km_2-probezhki", "20260629", "sergey", 5.60, 9, "", {}),
    ("04_10km_2-probezhki", "20260617", "kirill", 5.90, 5, "", {"visibility": "private"}),
    # --- 05 «Пятёрка со срезкой»: ваши 5:43 (26.10), 5:24 (01.11), срезка 6:07 (10.11)
    ("05_5km_3-probezhki_so-srezkoj", "20261026", "kirill", 5.55, 35, "Пятёрка вдоль моря",
     {ROOT: True}),
    ("05_5km_3-probezhki_so-srezkoj", "20261101", "oleg", 5.80, 12, "", {}),
    ("05_5km_3-probezhki_so-srezkoj", "20261026", "anna", 6.20, 7, "", {}),
    # --- 06 «Трёшка в одну сторону»: ваши 6:28 (27.10) и 6:17 (28.10, в обратную сторону)
    ("06_3km_2-probezhki_linejnyj", "20261027", "marina", 5.91, 33, "Трёшка в одну сторону",
     {ROOT: True}),
    ("06_3km_2-probezhki_linejnyj", "20261027", "kirill", 6.60, 8, "", {}),
    ("06_3km_2-probezhki_linejnyj", "20261028", "sergey", 6.55, 31, "Трёшка обратно",
     {ROOT: True}),
    # --- Одиночные маршруты (по одному вашему треку): часть быстрее вас, часть медленнее
    ("00_odinochnye", "20250503", "anna", 9.00, 48, "Круг по парку", {ROOT: True}),
    ("00_odinochnye", "20250520", "oleg", 7.00, 46, "Длинная десятка", {ROOT: True}),
    ("00_odinochnye", "20250524", "sergey", 5.60, 44, "Быстрая десятка", {ROOT: True}),
    ("00_odinochnye", "20250530", "marina", 6.25, 42, "Семёрка по сопкам", {ROOT: True}),
    ("00_odinochnye", "20250601", "kirill", 6.00, 39, "Десятка через мост", {ROOT: True}),
    ("00_odinochnye", "20250601", "anna", 6.60, 14, "", {}),
    ("00_odinochnye", "20250611", "sergey", 6.10, 37, "Шестёрка с петлёй", {ROOT: True}),
    ("00_odinochnye", "20250615", "anna", 8.00, 36, "Вечерняя семёрка",
     {ROOT: True, "visibility": "link"}),
    ("00_odinochnye", "20260704", "oleg", 8.20, 34, "Тихая десятка", {ROOT: True}),
    ("00_odinochnye", "20260926", "marina", 5.75, 32, "Осенняя десятка", {ROOT: True}),
    # 20261030 — без копии: ваша загрузка станет новым маршрутом
]
# Живой показ (папка live/): новый маршрут и две попытки к нему от второго бегуна.
# Маршрута нет в дампе, поэтому первый файл станет новым маршрутом.
LIVE_SOURCE = ("00_odinochnye", "20261030")
LIVE = [
    ("1_novyj_marshrut.gpx", 6.50, 1, "автор: загрузить первым, новый бегун"),
    ("2_ne_prevzoshel.gpx", 7.00, 0, "второй бегун: медленнее автора на ~2 мин"),
    ("3_prevzoshel.gpx", 6.00, 0, "второй бегун: быстрее автора на ~2 мин"),
]
# Начало и конец каждой копии обрезаются на случайные сотни метров: мест ваших стартов у дома
# нет на карте, а по разбросу концов его не вычислить. Скрытой зоны у бегунов дампа нет — иначе
# досчёт скрытой части (до трети времени) зависел бы от случайного среза и итог «прыгал».
# Автора режем сильнее, чем попытки: попытка должна пройти через его старт и финиш.
TRIM_ROOT_M = (600.0, 800.0)
TRIM_ATTEMPT_M = (400.0, 500.0)

# Скачивания GPX для рейтинга популярности: (исходник серии автора, бегуны, которые скачали)
DOWNLOADS = {
    "04_10km_2-probezhki": ["oleg", "kirill", "marina"],
    "01_5km_3-probezhki": ["anna", "sergey"],
}


def retime(pts, rnd: random.Random, pace_min_km: float, day: datetime):
    """Копия с заданным средним темпом, в другой день, со сдвигом координат до ~4 м."""
    km = distance_m(pts) / 1000
    scale = pace_min_km * 60 * km / (pts[-1][2] - pts[0][2]).total_seconds()
    t0 = pts[0][2]
    start = datetime.combine(day.date(), t0.timetz())
    shift_e, shift_n = rnd.uniform(-4, 4), rnd.uniform(-4, 4)
    period_e, period_n = rnd.uniform(150, 400), rnd.uniform(150, 400)
    phase_e, phase_n = rnd.uniform(0, 2 * math.pi), rnd.uniform(0, 2 * math.pi)
    out = []
    for i, (lat, lon, t, ele) in enumerate(pts):
        if 0 < i < len(pts) - 1 and rnd.random() < 0.10:
            continue
        e = shift_e + 3 * math.sin(2 * math.pi * i / period_e + phase_e)
        n = shift_n + 3 * math.sin(2 * math.pi * i / period_n + phase_n)
        out.append(
            (
                lat + n / M_PER_DEG,
                lon + e / (M_PER_DEG * math.cos(math.radians(lat))),
                start + (t - t0) * scale,
                ele,
            )
        )
    return out


def trim(pts, rnd: random.Random, span: tuple[float, float]):
    """Отрезает случайные span метров с начала и (независимо) с конца трека."""
    cum = [0.0]
    for a, b in zip(pts, pts[1:], strict=False):
        cum.append(cum[-1] + distance_m([a, b]))
    head, tail = rnd.uniform(*span), rnd.uniform(*span)
    return [p for p, c in zip(pts, cum, strict=True) if head <= c <= cum[-1] - tail]


def make_live(src_file: Path, dst: Path, rnd: random.Random, now: datetime) -> None:
    pts = read(src_file)
    lines = []
    for k, (name, pace, days_ago, note) in enumerate(LIVE):
        cut = trim(pts, rnd, TRIM_ROOT_M if k == 0 else TRIM_ATTEMPT_M)
        variant = retime(cut, rnd, pace, now - timedelta(days=days_ago))
        write(variant, "Пробежка", dst / "live" / name)
        lines.append(f"- `{name}` — темп {pace:.2f} мин/км; {note}")
    (dst / "live" / "README.md").write_text(
        "# Живой показ\n\n" + "\n".join(lines) + "\n"
    )


def main(src: Path, dst: Path) -> None:
    rnd = random.Random(SEED)
    now = datetime.now(UTC)
    files = {(f.parent.name, f.name[:8]): f for f in src.rglob("*.gpx")}
    runners = {
        slug: {
            "name": name,
            "email": f"{slug}@example.com",
            "city": "Владивосток",
        }
        for slug, name in RUNNERS.items()
    }
    titles: dict[str, str] = {}
    entries = []
    # авторы маршрутов публикуются первыми — иначе маршрутом группы станет попытка
    ordered = sorted(SCENARIO, key=lambda s: (not s[6].get(ROOT), -s[4]))
    for series, source, slug, pace, days_ago, title, opts in ordered:
        span = TRIM_ROOT_M if opts.get(ROOT) else TRIM_ATTEMPT_M
        pts = trim(read(files[(series, source)]), rnd, span)
        day = now - timedelta(days=days_ago)
        variant = retime(pts, rnd, pace, day)
        # у одиночных маршрут — один исходник, у серий — вся серия
        route_key = f"{series}/{source}" if series == "00_odinochnye" else series
        if opts.get(ROOT):
            titles.setdefault(route_key, title)
        name = title or titles.get(route_key) or "Пробежка"
        out = dst / series / f"{slug}_{variant[0][2]:%Y%m%d}_{source}.gpx"
        write(variant, name, out)
        entries.append(
            {
                "file": str(out.relative_to(dst)),
                "runner": slug,
                "series": series,
                "source": source,
                "title": name,
                "pace_min_km": pace,
                "root": bool(opts.get(ROOT)),
                "visibility": opts.get("visibility", "public"),
                "detach": bool(opts.get("detach")),
            }
        )
    make_live(files[LIVE_SOURCE], dst, rnd, now)
    manifest = {"runners": runners, "tracks": entries, "downloads": DOWNLOADS}
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"{len(entries)} треков от {len(runners)} бегунов -> {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
