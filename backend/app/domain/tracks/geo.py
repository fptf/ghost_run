"""Проекция в локальную UTM-зону: все метрические расчёты идут в метрах."""

import math
from dataclasses import dataclass

from pyproj import Proj, Transformer


@dataclass(frozen=True)
class Projection:
    """UTM-зона трека с поправкой на масштабный коэффициент в его районе.

    UTM искажает длины до ±0,1% у краёв зоны; координаты делятся на коэффициент k в первой
    точке, поэтому расстояния в пределах трека (десятки км) получаются истинными.
    """

    forward: Transformer
    inverse: Transformer
    scale: float

    @classmethod
    def for_point(cls, lat: float, lon: float) -> "Projection":
        zone = int((lon + 180) // 6) % 60 + 1
        epsg = (32600 if lat >= 0 else 32700) + zone
        k = float(Proj(epsg).get_factors(lon, lat).meridional_scale)
        return cls(
            forward=Transformer.from_crs(4326, epsg, always_xy=True),
            inverse=Transformer.from_crs(epsg, 4326, always_xy=True),
            scale=k,
        )

    def to_xy(self, lats: list[float], lons: list[float]) -> list[tuple[float, float]]:
        xs, ys = self.forward.transform(lons, lats)
        k = self.scale
        return [(float(x) / k, float(y) / k) for x, y in zip(xs, ys, strict=True)]

    def to_lonlat(self, xy: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if not xy:
            return []
        k = self.scale
        lons, lats = self.inverse.transform([p[0] * k for p in xy], [p[1] * k for p in xy])
        return list(zip(map(float, lons), map(float, lats), strict=True))


def dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def cumulative(xy: list[tuple[float, float]]) -> list[float]:
    out = [0.0]
    for a, b in zip(xy, xy[1:], strict=False):
        out.append(out[-1] + dist(a, b))
    return out
