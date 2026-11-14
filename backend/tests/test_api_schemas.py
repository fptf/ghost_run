"""Literal-типы схем ответа совпадают с enum-статусами моделей."""

import pytest

from app.api.schemas import as_literal
from app.api.tracks import ATTEMPT_STATES, STATUSES, VISIBILITIES
from app.infra.models import AttemptState, TrackStatus, Visibility


def test_literals_match_enums() -> None:
    assert set(STATUSES) == {s.value for s in TrackStatus}
    assert set(VISIBILITIES) == {v.value for v in Visibility}
    assert set(ATTEMPT_STATES) == {s.value for s in AttemptState}


def test_as_literal() -> None:
    assert as_literal(TrackStatus.draft.value, STATUSES) == "draft"
    with pytest.raises(ValueError):
        as_literal("unknown", STATUSES)
