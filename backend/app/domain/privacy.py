"""Правила скрытой зоны у дома (ФТ-4)."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RadiusBounds:
    min_m: int
    max_m: int

    @classmethod
    def from_setting(cls, value: Any) -> "RadiusBounds":
        return cls(min_m=int(value["min"]), max_m=int(value["max"]))


class RadiusOutOfRangeError(ValueError):
    def __init__(self, bounds: RadiusBounds) -> None:
        self.bounds = bounds
        super().__init__(f"Радиус скрытой зоны должен быть от {bounds.min_m} до {bounds.max_m} м")


def validate_hide_radius(radius_m: int, bounds: RadiusBounds) -> None:
    if not bounds.min_m <= radius_m <= bounds.max_m:
        raise RadiusOutOfRangeError(bounds)
