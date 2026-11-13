"""Популярность маршрута (ФТ-28): чистая функция с коэффициентами из настроек."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Weights:
    runners: float = 5
    downloads: float = 2
    likes: float = 1

    @classmethod
    def from_setting(cls, value: Any) -> "Weights":
        return cls(
            runners=float(value.get("runners", 5)),
            downloads=float(value.get("downloads", 2)),
            likes=float(value.get("likes", 1)),
        )


def popularity(runners: int, downloads: int, likes: int, weights: Weights) -> float:
    """5 × уникальные бегуны группы + 2 × скачивания GPX + 1 × лайки."""
    return weights.runners * runners + weights.downloads * downloads + weights.likes * likes
