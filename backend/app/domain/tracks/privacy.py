"""Скрытая зона у дома: видна часть трека между выходом из круга в начале и входом в конце."""

from dataclasses import dataclass

from app.domain.tracks.geo import dist

BOUNDARY_MARGIN_M = 1.0  # граница видимой части ставится на 1 м снаружи круга


@dataclass(frozen=True)
class VisibleRange:
    from_m: float
    to_m: float


def _crossing(
    a: tuple[float, float], b: tuple[float, float], home: tuple[float, float], r: float
) -> float:
    """Доля отрезка a→b, на которой расстояние до дома равно r (a внутри, b снаружи)."""
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        p = (a[0] + (b[0] - a[0]) * mid, a[1] + (b[1] - a[1]) * mid)
        if dist(p, home) < r:
            lo = mid
        else:
            hi = mid
    return hi


def visible_range(
    xy: list[tuple[float, float]],
    cum_m: list[float],
    home: tuple[float, float] | None,
    radius_m: float | None,
) -> VisibleRange | None:
    """Границы видимой части по дистанции. None — трек целиком внутри зоны."""
    if home is None or not radius_m:
        return VisibleRange(0.0, cum_m[-1])
    r = radius_m + BOUNDARY_MARGIN_M
    inside = [dist(p, home) < r for p in xy]
    if all(inside):
        return None

    start_m = 0.0
    if inside[0]:
        i = inside.index(False)
        k = _crossing(xy[i - 1], xy[i], home, r)
        start_m = cum_m[i - 1] + k * (cum_m[i] - cum_m[i - 1])

    end_m = cum_m[-1]
    if inside[-1]:
        j = len(inside) - 1 - inside[::-1].index(False)  # последняя точка снаружи
        k = _crossing(xy[j + 1], xy[j], home, r)  # от внутренней точки к внешней
        end_m = cum_m[j + 1] - k * (cum_m[j + 1] - cum_m[j])

    if end_m <= start_m:
        return None
    return VisibleRange(start_m, end_m)
