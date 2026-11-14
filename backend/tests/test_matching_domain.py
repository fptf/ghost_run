"""Правила 5.1/5.2 на реальных (обезличенных) пробежках и производных от них случаях."""

import math

import pytest

from app.domain.matching import AttemptLine, MatchConfig, Route, compare, match
from app.domain.tracks.metrics import MetricsConfig
from app.domain.tracks.model import FileFormat
from app.domain.tracks.pipeline import GeometryConfig, ProcessedTrack, process
from tests.gpx_factory import straight, to_gpx
from tests.helpers import fx, path_before

CFG = MatchConfig()


def route(p: ProcessedTrack) -> Route:
    assert p.visibility.range is not None
    return Route(
        points=[(x, y) for x, y, _ in p.visibility.route],
        full_distance_m=p.metrics.distance_m,
        visible_from_m=p.visibility.range.from_m,
        visible_to_m=p.visibility.range.to_m,
        total_time_s=p.metrics.total_time_s,
    )


def line(p: ProcessedTrack) -> list[tuple[float, float, float]]:
    return [(x, y, m) for x, y, _, m in p.full]


def run(points: list[tuple[float, float, float]]) -> AttemptLine:
    return AttemptLine(points=points)


def scaled(points, k: float):  # type: ignore[no-untyped-def]
    """Тот же путь, темп в k раз медленнее."""
    return [(x, y, t * k) for x, y, t in points]


# --- Real series match (Automatic Matching) ---------------------------------------------------

SAME_ROUTE = [
    ("20250522", "20250529"),
    ("20250529", "20250522"),
    ("20260604", "20260701"),
    ("20260617", "20260629"),
    ("20260629", "20260617"),
    ("20261026", "20261101"),
    ("20261101", "20261026"),
]
DIFFERENT = [
    ("20250522", "20260604"),  # разные маршруты у одного дома
    ("20261026", "20250522"),
    ("20260617", "20260530"),  # две «десятки» по разным местам
    ("20250514", "20250522"),  # удлинённый вариант: +7% длины — по ТЗ другой маршрут
]


@pytest.mark.parametrize(("root", "attempt"), SAME_ROUTE)
def test_real_series_match(root: str, attempt: str) -> None:
    r = match(route(fx(root)), run(line(fx(attempt))), CFG)
    assert r.matched, r


@pytest.mark.parametrize(("root", "attempt"), DIFFERENT)
def test_real_different_routes_do_not_match(root: str, attempt: str) -> None:
    assert not match(route(fx(root)), run(line(fx(attempt))), CFG).matched


# --- Route Match Rules -----------------------------------------------------------------------


def test_real_shortcut_fails() -> None:
    """10.11 — та же «пятёрка», но со срезкой: на маршрут 26.10 не засчитывается."""
    r = match(route(fx("20261026")), run(line(fx("20261110"))), CFG)
    assert not r.matched
    assert not r.length_ok


def test_shortcut_81_percent_reports_corridor_and_deviation() -> None:
    root = fx("20261026")
    pts = line(fx("20261101"))
    n = len(pts)
    a, b = int(n * 0.40), int(n * 0.59)  # выкидываем кусок и «срезаем» по прямой
    cut = pts[:a] + pts[b:]
    r = match(route(root), run(cut), CFG)
    assert not r.matched
    assert not r.coverage_ok
    assert 0.7 < r.coverage < 0.9
    assert r.deviation is not None
    assert 1.0 < r.deviation.km < root.metrics.distance_m / 1000


def test_real_reverse_direction() -> None:
    """27.10 и 28.10 — один отрезок, пробежанный в разные стороны."""
    r = match(route(fx("20261027")), run(line(fx("20261028"))), CFG)
    assert not r.matched
    assert not r.direction_ok


def test_reversed_copy_fails_direction() -> None:
    pts = line(fx("20261101"))
    total = pts[-1][2]
    reversed_pts = [(x, y, total - t) for x, y, t in reversed(pts)]
    r = match(route(fx("20261026")), run(reversed_pts), CFG)
    assert not r.matched
    assert not r.direction_ok


# --- Warm-up Trimming ------------------------------------------------------------------------


def test_warm_up_and_cool_down_trimmed() -> None:
    root = fx("20261026")
    pts = line(fx("20261101"))
    warm = path_before((pts[0][0], pts[0][1]), 700)
    shift = warm[-1][2] + 1
    body = [(x, y, t + shift) for x, y, t in pts]
    cool_from = body[-1]
    cool = path_before((cool_from[0], cool_from[1]), 400)
    cool = [(x, y, cool_from[2] + 1 + (cool[-1][2] - t)) for x, y, t in reversed(cool)]
    r = match(route(root), run(warm[:-1] + body + cool[1:]), CFG)
    assert r.matched and r.trimmed
    # сравнивается только участок маршрута — время почти совпадает с пробежкой без разминки
    plain = match(route(root), run(pts), CFG)
    assert r.result_time_s == pytest.approx(plain.result_time_s, abs=20)


def test_warm_up_crossing_category() -> None:
    """Маршрут 7,4 км (категория 5) пробежан с разминкой до 8 км (категория 10)."""
    rt = process(to_gpx(straight(7400)), FileFormat.gpx, None, None, MetricsConfig(),
                 GeometryConfig())  # fmt: skip
    pts = line(rt)
    warm = path_before((pts[0][0], pts[0][1]), 600)
    attempt = warm[:-1] + [(x, y, t + warm[-1][2] + 1) for x, y, t in pts]
    r = match(route(rt), run(attempt), CFG)
    assert r.matched and r.trimmed


# --- Loop Routes -----------------------------------------------------------------------------


def test_loop_one_lap_matches() -> None:
    root = fx("20260926")  # круговой: старт и финиш в 8 м
    r = match(route(root), run(scaled(line(root), 0.97)), CFG)
    assert r.is_loop and r.matched and not r.trimmed
    assert r.result_time_s == pytest.approx(root.metrics.total_time_s * 0.97, rel=0.001)


def test_two_laps_rejected() -> None:
    root = fx("20260926")
    lap = line(root)
    second = [(x, y, t + lap[-1][2] + 1) for x, y, t in lap]
    r = match(route(root), run(lap + second), CFG)
    assert r.is_loop and not r.matched
    assert not r.length_ok and r.length_ratio == pytest.approx(2.0, rel=0.02)


def test_loop_from_home_with_hidden_zone_matches_neighbour() -> None:
    """Круг от дома: видна середина, её концы рядом. Сосед стартует от своего дома — засчитано."""
    plain = fx("20260926")
    lon0, lat0 = plain.full[0][0], plain.full[0][1]
    root = fx("20260926", home=(lat0, lon0), radius=400)
    rt = route(root)
    assert rt.visible_from_m > 0  # концы маршрута скрыты
    r = match(rt, run(scaled(line(plain), 0.97)), CFG)
    assert not r.is_loop
    assert r.matched, r
    assert r.result_time_s == pytest.approx(plain.metrics.total_time_s * 0.97, rel=0.02)


# --- Privacy Zone Compensation ---------------------------------------------------------------


def test_author_hid_start() -> None:
    plain_root = fx("20261026")
    lon0, lat0 = plain_root.full[0][0], plain_root.full[0][1]
    hidden_root = fx("20261026", home=(lat0, lon0), radius=300)
    rt = route(hidden_root)
    assert rt.visible_from_m > 290
    attempt = line(fx("20261101"))
    r = match(rt, run(attempt), CFG)
    assert r.matched
    hidden_len = rt.full_distance_m - (rt.visible_to_m - rt.visible_from_m)
    pace = r.segment_time_s / r.segment_distance_m
    assert r.hidden_time_s == pytest.approx(hidden_len * pace, rel=0.01)
    assert r.result_time_s == pytest.approx(r.segment_time_s + r.hidden_time_s)
    # результат сравним с честной полной пробежкой без скрытой зоны
    full = match(route(plain_root), run(attempt), CFG)
    assert r.result_time_s == pytest.approx(full.result_time_s, rel=0.03)


# --- Result Comparison -----------------------------------------------------------------------


def test_equal_result_within_one_second() -> None:
    c = compare(1500.6, 1500.0, 1.0)
    assert c.equal and not c.faster
    c = compare(1482.0, 1500.0, 1.0)
    assert c.faster and c.diff_s == pytest.approx(-18)
    c = compare(1499.2, 1500.0, 1.0)
    assert c.equal and not c.faster  # быстрее на 0,8 с — всё ещё «равно»


def test_thresholds_come_from_config() -> None:
    root, att = route(fx("20261026")), run(line(fx("20261101")))
    strict = MatchConfig(corridor_width_m=1.0)
    assert match(root, att, CFG).matched
    assert not match(root, att, strict).matched


def test_all_rules_reported_even_on_failure() -> None:
    r = match(route(fx("20261027")), run(line(fx("20261028"))), CFG)
    assert all(
        isinstance(v, float) and not math.isnan(v)
        for v in (r.start_gap_m, r.finish_gap_m, r.coverage, r.direction_share, r.length_ratio)
    )
