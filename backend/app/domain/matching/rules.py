"""Сопоставление попытки с маршрутом по правилам раздела 5.1 и сравнение результата (5.2).

Маршрут — видимая часть исходного трека (с шагом ~10 м). Все расчёты — в метрах, в UTM-зоне
старта маршрута. Каждое правило считается даже при провале других: экран «Проверить мою
пробежку» показывает все правила с фактическими значениями.
"""

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import shapely
from shapely.geometry import LineString

from app.domain.tracks.geo import Projection, cumulative, dist

LonLat = tuple[float, float]
XY = tuple[float, float]


@dataclass(frozen=True)
class MatchConfig:
    start_finish_radius_m: float = 50.0
    corridor_width_m: float = 30.0
    corridor_coverage: float = 0.9
    length_tolerance: float = 0.03
    loop_threshold_m: float = 50.0
    direction_min_share: float = 0.9
    tie_threshold_s: float = 1.0


@dataclass(frozen=True)
class Route:
    """Маршрут исходного трека."""

    points: list[LonLat]  # видимая часть, шаг ~10 м
    full_distance_m: float  # полная дистанция автора (со скрытыми частями)
    visible_from_m: float  # где начинается видимая часть на полном треке
    visible_to_m: float  # где она заканчивается
    total_time_s: float  # результат автора — общее время


@dataclass(frozen=True)
class AttemptLine:
    """Полный трек попытки: (lon, lat, секунды от старта)."""

    points: list[tuple[float, float, float]]


@dataclass(frozen=True)
class Deviation:
    lon: float
    lat: float
    km: float  # километр маршрута (по полному треку автора)


@dataclass(frozen=True)
class MatchResult:
    matched: bool
    is_loop: bool
    trimmed: bool  # из попытки вырезан участок (разминка, заминка)
    start_gap_m: float
    finish_gap_m: float
    start_ok: bool
    finish_ok: bool
    coverage: float
    coverage_ok: bool
    direction_share: float
    direction_ok: bool
    length_ratio: float
    length_ok: bool
    segment_distance_m: float
    segment_time_s: float
    hidden_time_s: float
    result_time_s: float
    deviation: Deviation | None


Outcome = Literal["beat", "slower", "equal"]


@dataclass(frozen=True)
class Comparison:
    diff_s: float  # отрицательная — быстрее автора
    equal: bool
    faster: bool

    @property
    def outcome(self) -> Outcome:
        return "equal" if self.equal else "beat" if self.faster else "slower"


def verdict(diff_s: float, tie_threshold_s: float) -> Comparison:
    """5.2: разница меньше порога — равный результат; быстрее на порог и больше — «превзошёл»."""
    equal = abs(diff_s) < tie_threshold_s
    return Comparison(diff_s=diff_s, equal=equal, faster=not equal and diff_s < 0)


def compare(result_time_s: float, root_time_s: float, tie_threshold_s: float) -> Comparison:
    """Сравнение результата попытки с результатом автора маршрута (5.2)."""
    return verdict(result_time_s - root_time_s, tie_threshold_s)


def _passages(dists: np.ndarray, radius: float) -> list[int]:
    """Индексы ближайших точек в каждом «проходе» — подряд идущих точках ближе radius."""
    inside = dists < radius
    result: list[int] = []
    i, n = 0, len(dists)
    while i < n:
        if not inside[i]:
            i += 1
            continue
        j = i
        while j < n and inside[j]:
            j += 1
        result.append(i + int(np.argmin(dists[i:j])))
        i = j
    return result


def _segment(
    att: np.ndarray, cum: list[float], start: XY, finish: XY, radius: float, target_m: float
) -> tuple[int, int, float, float] | None:
    """Пара «проход старта → более поздний проход финиша» с длиной участка ближе всего к маршруту.

    Ближайшая по длине пара, а не первая: у почти круговых маршрутов (старт и финиш в десятках
    метров) финиш «находится» сразу после старта, и участок вышел бы крошечным.
    """
    d_start = np.hypot(att[:, 0] - start[0], att[:, 1] - start[1])
    d_finish = np.hypot(att[:, 0] - finish[0], att[:, 1] - finish[1])
    finishes = _passages(d_finish, radius)
    best: tuple[float, int, int] | None = None
    for s in _passages(d_start, radius):
        for f in finishes:
            if f <= s:
                continue
            miss = abs((cum[f] - cum[s]) - target_m)
            if best is None or miss < best[0]:
                best = (miss, s, f)
    if best is None:
        return None
    _, s, f = best
    return s, f, float(d_start[s]), float(d_finish[f])


def _resample(xy: list[XY], step: float) -> np.ndarray:
    """Точки через каждые step метров вдоль линии (для выравнивания нужна равномерная плотность)."""
    pts = np.asarray(xy)
    seg = np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1]))
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    if cum[-1] == 0:
        return pts[:1]
    at = np.arange(0.0, cum[-1], step)
    return np.column_stack([np.interp(at, cum, pts[:, 0]), np.interp(at, cum, pts[:, 1])])


def _direction_share(r_xy: list[XY], seg_xy: list[XY], width: float) -> float:
    """Доля покрытых точек маршрута, которые остаются покрытыми при соблюдении порядка.

    Монотонное выравнивание (динамическое программирование): каждой точке маршрута ставится
    точка участка не раньше, чем предыдущей, так, чтобы как можно больше точек маршрута были
    в коридоре. При обратном ходе порядок «съедает» почти всё покрытие; маршруты с повторными
    проходами (восьмёрки, круги) порядок соблюдают.
    """
    route = np.asarray(r_xy)
    seg = _resample(seg_xy, 10.0)
    misses_prev = np.zeros(len(seg))
    covered_any = 0
    for x, y in route:
        inside = np.hypot(seg[:, 0] - x, seg[:, 1] - y) <= width
        covered_any += bool(inside.any())
        # лучший результат для префикса маршрута, если текущая точка встаёт не раньше j
        misses_prev = np.minimum.accumulate(misses_prev) + (~inside)
    ordered_covered = len(route) - float(misses_prev.min())
    return ordered_covered / covered_any if covered_any else 0.0


@dataclass(frozen=True)
class _Segment:
    """Участок попытки, который сравнивается с маршрутом: индексы точек и зазоры у концов."""

    i_s: int
    i_f: int
    start_gap_m: float
    finish_gap_m: float
    ordered: bool  # старт пройден раньше финиша


def _is_loop(route: Route, r_start: XY, r_finish: XY, cfg: MatchConfig) -> bool:
    # Круговой — только целиком видимый маршрут. У круга от дома видна середина, её концы
    # на границе скрытой зоны тоже рядом, но попытка начинается у своего дома, а не там, —
    # такой маршрут сопоставляется как обычный участок с досчётом скрытых концов.
    visible_len = route.visible_to_m - route.visible_from_m
    has_hidden_ends = visible_len < route.full_distance_m - 1.0
    return dist(r_start, r_finish) < cfg.loop_threshold_m and not has_hidden_ends


def _find_segment(
    a_xy: list[XY], r_start: XY, r_finish: XY, is_loop: bool, visible_len: float, cfg: MatchConfig
) -> _Segment:
    last = len(a_xy) - 1
    if is_loop:
        # 5.1: круговой маршрут не обрезается — сравнивается вся попытка.
        return _Segment(0, last, dist(a_xy[0], r_start), dist(a_xy[-1], r_finish), True)
    att = np.asarray(a_xy)
    found = _segment(
        att, cumulative(a_xy), r_start, r_finish, cfg.start_finish_radius_m, visible_len
    )
    if found is None:
        # Нет пары «старт → финиш» по порядку: остальные правила считаем по всей попытке.
        start_gap = float(np.min(np.hypot(att[:, 0] - r_start[0], att[:, 1] - r_start[1])))
        finish_gap = float(np.min(np.hypot(att[:, 0] - r_finish[0], att[:, 1] - r_finish[1])))
        return _Segment(0, last, start_gap, finish_gap, False)
    i_s, i_f, start_gap, finish_gap = found
    return _Segment(i_s, i_f, start_gap, finish_gap, True)


def _corridor(
    route: Route, r_xy: list[XY], r_cum: list[float], seg_xy: list[XY], width: float
) -> tuple[float, Deviation | None]:
    """Коридор: доля точек маршрута ближе width к линии участка и первая точка вне его."""
    pts = shapely.points(np.asarray(r_xy))
    gaps = shapely.distance(pts, LineString(seg_xy))
    covered = gaps <= width
    coverage = float(np.mean(covered))
    if covered.all():
        return coverage, None
    k = int(np.argmin(covered))  # первая точка маршрута вне коридора
    lon, lat = route.points[k]
    return coverage, Deviation(lon=lon, lat=lat, km=(route.visible_from_m + r_cum[k]) / 1000)


def _length_ratio(seg_xy: list[XY], route_len: float) -> float:
    # Длины сравниваются по линиям с одинаковым шагом 10 м: дрожание GPS удлиняет сырой трек
    # по-разному на разных пробежках, а правило — про совпадение маршрута, а не шума.
    seg_smooth = _resample(seg_xy, 10.0)
    seg_smooth_len = (
        float(np.sum(np.hypot(*np.diff(seg_smooth, axis=0).T))) if len(seg_smooth) > 1 else 0.0
    )
    return seg_smooth_len / route_len if route_len > 0 else math.inf


def match(route: Route, attempt: AttemptLine, cfg: MatchConfig) -> MatchResult:
    lon0, lat0 = route.points[0]
    proj = Projection.for_point(lat0, lon0)
    r_xy = proj.to_xy([p[1] for p in route.points], [p[0] for p in route.points])
    a_xy = proj.to_xy([p[1] for p in attempt.points], [p[0] for p in attempt.points])
    a_t = [p[2] for p in attempt.points]
    r_start, r_finish = r_xy[0], r_xy[-1]
    r_cum = cumulative(r_xy)
    visible_len = route.visible_to_m - route.visible_from_m
    is_loop = _is_loop(route, r_start, r_finish, cfg)
    seg = _find_segment(a_xy, r_start, r_finish, is_loop, visible_len, cfg)
    i_s, i_f = seg.i_s, seg.i_f

    seg_xy = a_xy[i_s : i_f + 1] if i_f > i_s else a_xy
    seg_len = cumulative(seg_xy)[-1]
    seg_time = a_t[i_f] - a_t[i_s] if i_f > i_s else a_t[-1] - a_t[0]
    att_len = cumulative(a_xy)[-1]
    coverage, deviation = _corridor(route, r_xy, r_cum, seg_xy, cfg.corridor_width_m)
    direction_share = _direction_share(r_xy, seg_xy, cfg.corridor_width_m)
    length_ratio = _length_ratio(seg_xy, r_cum[-1])
    hidden_len = max(0.0, route.full_distance_m - visible_len)
    pace = seg_time / seg_len if seg_len > 0 else 0.0
    hidden_time = hidden_len * pace

    radius = cfg.start_finish_radius_m
    start_ok = seg.start_gap_m <= radius
    finish_ok = seg.finish_gap_m <= radius
    coverage_ok = coverage >= cfg.corridor_coverage
    direction_ok = direction_share >= cfg.direction_min_share
    length_ok = abs(length_ratio - 1) <= cfg.length_tolerance
    matched = (
        start_ok
        and finish_ok
        and coverage_ok
        and direction_ok
        and length_ok
        and (is_loop or seg.ordered)
    )
    return MatchResult(
        matched=matched,
        is_loop=is_loop,
        trimmed=seg_len < att_len * 0.99,
        start_gap_m=seg.start_gap_m,
        finish_gap_m=seg.finish_gap_m,
        start_ok=start_ok,
        finish_ok=finish_ok,
        coverage=coverage,
        coverage_ok=coverage_ok,
        direction_share=direction_share,
        direction_ok=direction_ok,
        length_ratio=length_ratio,
        length_ok=length_ok,
        segment_distance_m=seg_len,
        segment_time_s=seg_time,
        hidden_time_s=hidden_time,
        result_time_s=seg_time + hidden_time,
        deviation=deviation,
    )
