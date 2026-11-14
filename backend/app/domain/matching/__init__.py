"""Правила сопоставления маршрутов (раздел 5 ТЗ): чистые функции без I/O."""

from app.domain.matching.rules import (
    AttemptLine,
    Comparison,
    MatchConfig,
    MatchResult,
    Outcome,
    Route,
    compare,
    match,
    verdict,
)

__all__ = [
    "AttemptLine",
    "Comparison",
    "MatchConfig",
    "MatchResult",
    "Outcome",
    "Route",
    "compare",
    "match",
    "verdict",
]
