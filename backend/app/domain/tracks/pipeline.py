"""Полная обработка файла: от байтов до показателей и геометрий."""

from dataclasses import dataclass

from app.domain.tracks.geometry import MPoint, resample, simplify, slice_by_distance
from app.domain.tracks.metrics import (
    CleanTrack,
    Metrics,
    MetricsConfig,
    check_plausible,
    clean,
    compute_metrics,
)
from app.domain.tracks.model import FileFormat, Point
from app.domain.tracks.parsers import parse
from app.domain.tracks.visible_range import VisibleRange, visible_range

LonLatM = tuple[float, float, float]


@dataclass(frozen=True)
class GeometryConfig:
    resample_step_m: float = 10.0
    simplify_tolerance_m: float = 5.0


@dataclass(frozen=True)
class VisiblePart:
    """Видимая часть и производные геометрии в lon/lat."""

    range: VisibleRange | None  # None — трек целиком в скрытой зоне
    visible: list[LonLatM]  # полное разрешение, M — секунды от старта
    route: list[LonLatM]  # равный шаг, для сопоставления
    display: list[tuple[float, float]]  # упрощённая, для карты


@dataclass(frozen=True)
class ProcessedTrack:
    clean: CleanTrack
    metrics: Metrics
    full: list[tuple[float, float, float, float]]  # lon, lat, ele, M
    full_display: list[tuple[float, float]]  # весь трек, упрощённый — только автору
    visible_part: VisiblePart


def _to_lonlat_m(track: CleanTrack, pts: list[MPoint]) -> list[LonLatM]:
    ll = track.projection.to_lonlat([(p.x, p.y) for p in pts])
    return [(lon, lat, p.m) for (lon, lat), p in zip(ll, pts, strict=True)]


def compute_visible_part(
    track: CleanTrack,
    home: tuple[float, float] | None,
    radius_m: float | None,
    geo_cfg: GeometryConfig,
    seed: str | None = None,
) -> VisiblePart:
    """home — (lat, lon) точки дома; seed — см. visible_range."""
    home_xy = track.projection.to_xy([home[0]], [home[1]])[0] if home else None
    vr = visible_range(track.xy, track.cum_m, home_xy, radius_m, seed)
    if vr is None:
        return VisiblePart(range=None, visible=[], route=[], display=[])
    part = slice_by_distance(track.xy, track.cum_m, track.t_s, vr.from_m, vr.to_m)
    display = track.projection.to_lonlat(simplify(part, geo_cfg.simplify_tolerance_m))
    return VisiblePart(
        range=vr,
        visible=_to_lonlat_m(track, part),
        route=_to_lonlat_m(track, resample(part, geo_cfg.resample_step_m)),
        display=display,
    )


def process(
    data: bytes,
    fmt: FileFormat,
    home: tuple[float, float] | None,
    radius_m: float | None,
    metrics_cfg: MetricsConfig,
    geo_cfg: GeometryConfig,
    seed: str | None = None,
) -> ProcessedTrack:
    points: list[Point] = parse(data, fmt)
    track = clean(points, metrics_cfg)
    metrics = compute_metrics(track, metrics_cfg)
    check_plausible(metrics, metrics_cfg)
    full_parts = [MPoint(x, y, t) for (x, y), t in zip(track.xy, track.t_s, strict=True)]
    full = [
        (lon, lat, p.ele if p.ele is not None else 0.0, t)
        for (lon, lat, t), p in zip(_to_lonlat_m(track, full_parts), track.points, strict=True)
    ]
    return ProcessedTrack(
        clean=track,
        metrics=metrics,
        full=full,
        full_display=track.projection.to_lonlat(simplify(full_parts, geo_cfg.simplify_tolerance_m)),
        visible_part=compute_visible_part(track, home, radius_m, geo_cfg, seed),
    )
