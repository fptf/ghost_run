"""Показатели трека (ФТ-6) и проверки правдоподобия (ФТ-7)."""

from dataclasses import dataclass, field

from app.domain.tracks.geo import Projection, cumulative, dist
from app.domain.tracks.model import Point, RejectReason, TrackRejectedError

CATEGORY_CODES = ("1", "5", "10", "21", "21+")
MIN_POINTS = 10


@dataclass(frozen=True)
class MetricsConfig:
    max_point_speed_mps: float = 12.0
    stopped_speed_mps: float = 0.5
    elevation_noise_m: float = 3.0
    min_pace_s_per_km: float = 150.0
    category_bounds_m: tuple[int, ...] = (3000, 7500, 15000, 25000)


@dataclass(frozen=True)
class Split:
    index: int  # 1, 2, ... — номер километра
    distance_m: float  # 1000 или меньше для последнего
    time_s: float


@dataclass(frozen=True)
class CleanTrack:
    """Очищенные точки и их проекция; основа для метрик и геометрий."""

    points: list[Point]
    xy: list[tuple[float, float]]
    cum_m: list[float]
    t_s: list[float]  # секунды от старта
    projection: Projection


@dataclass(frozen=True)
class Metrics:
    distance_m: float
    total_time_s: float
    moving_time_s: float
    avg_pace_s_per_km: float
    elevation_gain_m: float
    has_elevation: bool
    category: str
    splits: list[Split] = field(default_factory=list)


def category_for(distance_m: float, bounds_m: tuple[int, ...]) -> str:
    for code, bound in zip(CATEGORY_CODES, bounds_m, strict=False):
        if distance_m < bound:
            return code
    return CATEGORY_CODES[len(bounds_m)]


def clean(points: list[Point], cfg: MetricsConfig) -> CleanTrack:
    """Сортирует по времени, убирает дубликаты времени и точки-выбросы."""
    if any(p.time is None for p in points) or not points:
        raise TrackRejectedError(RejectReason.no_time)
    ordered = sorted(points, key=lambda p: p.time)  # type: ignore[arg-type, return-value]
    proj = Projection.for_point(ordered[0].lat, ordered[0].lon)
    xy_all = proj.to_xy([p.lat for p in ordered], [p.lon for p in ordered])

    kept: list[int] = [0]
    for i in range(1, len(ordered)):
        prev = kept[-1]
        t0, t1 = ordered[prev].time, ordered[i].time
        assert t0 is not None and t1 is not None
        dt = (t1 - t0).total_seconds()
        if dt <= 0:
            continue
        if dist(xy_all[prev], xy_all[i]) / dt > cfg.max_point_speed_mps:
            continue  # выброс GPS: до точки не добежать
        kept.append(i)

    if len(kept) < MIN_POINTS:
        raise TrackRejectedError(RejectReason.too_short)
    pts = [ordered[i] for i in kept]
    xy = [xy_all[i] for i in kept]
    start = pts[0].time
    assert start is not None
    t_s = [(p.time - start).total_seconds() for p in pts]  # type: ignore[operator]
    return CleanTrack(points=pts, xy=xy, cum_m=cumulative(xy), t_s=t_s, projection=proj)


def _splits(cum: list[float], t: list[float]) -> list[Split]:
    splits: list[Split] = []
    total = cum[-1]
    boundary, prev_t, j = 1000.0, 0.0, 1
    while boundary <= total:
        while cum[j] < boundary:
            j += 1
        seg = cum[j] - cum[j - 1]
        k = (boundary - cum[j - 1]) / seg if seg > 0 else 0.0
        at = t[j - 1] + k * (t[j] - t[j - 1])
        splits.append(Split(index=len(splits) + 1, distance_m=1000.0, time_s=at - prev_t))
        prev_t, boundary = at, boundary + 1000.0
    rest = total - (boundary - 1000.0)
    if rest >= 1.0:
        splits.append(Split(index=len(splits) + 1, distance_m=rest, time_s=t[-1] - prev_t))
    return splits


def _elevation_gain(eles: list[float], noise_m: float) -> float:
    window = 5
    smooth = [
        sum(eles[max(0, i - window // 2) : i + window // 2 + 1])
        / len(eles[max(0, i - window // 2) : i + window // 2 + 1])
        for i in range(len(eles))
    ]
    gain, low = 0.0, smooth[0]
    for e in smooth[1:]:
        if e < low:
            low = e
        elif e - low >= noise_m:
            gain += e - low
            low = e
    return gain


def compute_metrics(track: CleanTrack, cfg: MetricsConfig) -> Metrics:
    cum, t = track.cum_m, track.t_s
    distance = cum[-1]
    total = t[-1]
    moving = 0.0
    for i in range(1, len(t)):
        dt = t[i] - t[i - 1]
        if dt > 0 and (cum[i] - cum[i - 1]) / dt >= cfg.stopped_speed_mps:
            moving += dt
    eles = [p.ele for p in track.points]
    has_ele = all(e is not None for e in eles)
    gain = (
        _elevation_gain([e for e in eles if e is not None], cfg.elevation_noise_m)
        if has_ele
        else 0.0
    )
    pace = total / (distance / 1000) if distance > 0 else 0.0
    return Metrics(
        distance_m=distance,
        total_time_s=total,
        moving_time_s=moving,
        avg_pace_s_per_km=pace,
        elevation_gain_m=gain,
        has_elevation=has_ele,
        category=category_for(distance, cfg.category_bounds_m),
        splits=_splits(cum, t),
    )


def check_plausible(metrics: Metrics, cfg: MetricsConfig) -> None:
    if metrics.distance_m < 100 or metrics.total_time_s <= 0:
        raise TrackRejectedError(RejectReason.too_short)
    if metrics.avg_pace_s_per_km < cfg.min_pace_s_per_km:
        raise TrackRejectedError(RejectReason.too_fast)
