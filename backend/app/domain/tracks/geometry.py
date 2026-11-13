"""Нарезка по дистанции, пересэмплинг с равным шагом и упрощение (Дуглас—Пекер)."""

from dataclasses import dataclass

from shapely.geometry import LineString


@dataclass(frozen=True)
class MPoint:
    """Точка в метрах UTM с временем от старта (M)."""

    x: float
    y: float
    m: float


def _interp(xy: list[tuple[float, float]], cum: list[float], t: list[float], at: float) -> MPoint:
    if at <= 0:
        return MPoint(xy[0][0], xy[0][1], t[0])
    if at >= cum[-1]:
        return MPoint(xy[-1][0], xy[-1][1], t[-1])
    lo, hi = 0, len(cum) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if cum[mid] <= at:
            lo = mid
        else:
            hi = mid
    seg = cum[hi] - cum[lo]
    k = (at - cum[lo]) / seg if seg > 0 else 0.0
    return MPoint(
        xy[lo][0] + k * (xy[hi][0] - xy[lo][0]),
        xy[lo][1] + k * (xy[hi][1] - xy[lo][1]),
        t[lo] + k * (t[hi] - t[lo]),
    )


def slice_by_distance(
    xy: list[tuple[float, float]], cum: list[float], t: list[float], from_m: float, to_m: float
) -> list[MPoint]:
    """Часть линии между from_m и to_m с интерполированными концами."""
    inner = [
        MPoint(p[0], p[1], tt) for p, c, tt in zip(xy, cum, t, strict=True) if from_m < c < to_m
    ]
    return [_interp(xy, cum, t, from_m), *inner, _interp(xy, cum, t, to_m)]


def resample(points: list[MPoint], step_m: float) -> list[MPoint]:
    """Точки через каждые step_m метров вдоль линии (плюс последняя)."""
    xy = [(p.x, p.y) for p in points]
    t = [p.m for p in points]
    cum = [0.0]
    for a, b in zip(points, points[1:], strict=False):
        cum.append(cum[-1] + ((b.x - a.x) ** 2 + (b.y - a.y) ** 2) ** 0.5)
    total = cum[-1]
    out = [_interp(xy, cum, t, i * step_m) for i in range(int(total // step_m) + 1)]
    if total - (len(out) - 1) * step_m > 1e-6:
        out.append(_interp(xy, cum, t, total))
    return out


def simplify(points: list[MPoint], tolerance_m: float) -> list[tuple[float, float]]:
    """Дуглас—Пекер; концы сохраняются."""
    if len(points) < 3:
        return [(p.x, p.y) for p in points]
    line = LineString([(p.x, p.y) for p in points]).simplify(tolerance_m, preserve_topology=False)
    return [(float(x), float(y)) for x, y in line.coords]
