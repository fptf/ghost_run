"""Сборка EWKT для PostGIS из списков координат."""

from collections.abc import Sequence


def _fmt(values: Sequence[float]) -> str:
    return " ".join(f"{v:.7f}" if i < 2 else f"{v:.2f}" for i, v in enumerate(values))


def linestring(coords: Sequence[Sequence[float]], dims: str = "") -> str | None:
    """dims: '' (XY), 'M' (XYM) или 'ZM' (XYZM)."""
    if len(coords) < 2:
        return None
    kind = f"LINESTRING {dims}".strip()
    return f"SRID=4326;{kind}({', '.join(_fmt(c) for c in coords)})"


def point(lon: float, lat: float) -> str:
    return f"SRID=4326;POINT({lon:.7f} {lat:.7f})"
