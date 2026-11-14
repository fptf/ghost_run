"""Чистая логика треков: метрики, проверки, скрытая зона, рабочие геометрии, фото."""

import io
import math
import time
from pathlib import Path

import pytest
from PIL import Image

from app.domain.tracks.geo import Projection
from app.domain.tracks.metrics import MetricsConfig, category_for
from app.domain.tracks.model import FileFormat, RejectReason, TrackRejectedError
from app.domain.tracks.parsers import detect_format, parse
from app.domain.tracks.pipeline import GeometryConfig, process
from app.infra.photos import sanitize
from tests.gpx_factory import ORIGIN, circle, offset, straight, to_gpx
from tests.helpers import FIXTURES, haversine, jpeg_with_gps

MC, GC = MetricsConfig(), GeometryConfig()


def run(data: bytes, home: tuple[float, float] | None = None, radius: float | None = None):
    fmt = detect_format(data[:4096])
    assert fmt is not None
    return process(data, fmt, home, radius, MC, GC)


# --- Supported Files --------------------------------------------------------------


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("run_*.gpx")), ids=lambda p: p.stem)
def test_real_gpx_distance_matches_points(path: Path) -> None:
    data = path.read_bytes()
    points = parse(data, FileFormat.gpx)
    naive = sum(
        haversine((a.lat, a.lon), (b.lat, b.lon)) for a, b in zip(points, points[1:], strict=False)
    )
    result = run(data)
    assert abs(result.metrics.distance_m - naive) / naive <= 0.01


def test_same_run_in_three_formats() -> None:
    results = {
        ext: run((FIXTURES / f"run_20261026.{ext}").read_bytes()).metrics
        for ext in ("gpx", "tcx", "fit")
    }
    base = results["gpx"]
    for m in results.values():
        assert m.distance_m == pytest.approx(base.distance_m, rel=0.01)
        assert m.total_time_s == pytest.approx(base.total_time_s, rel=0.01)
        assert m.elevation_gain_m == pytest.approx(base.elevation_gain_m, abs=1)


def test_format_detected_by_content_not_extension() -> None:
    assert detect_format((FIXTURES / "run_20261026.fit").read_bytes()[:64]) == FileFormat.fit
    assert detect_format((FIXTURES / "run_20261026.tcx").read_bytes()[:4096]) == FileFormat.tcx
    assert detect_format(b"%PDF-1.7 not a track") is None


def test_processing_time_for_20mb_file() -> None:
    pts = straight(42_195, pace_s_per_km=330, step_s=0.12, ele=True)
    data = to_gpx(pts, pretty=True)
    while len(data) < 19 * 1024 * 1024:  # добиваем до ~20 МБ пробелами внутри трека
        data = data.replace(b"\n</trkseg>", b"\n" + b" " * (1024 * 1024) + b"\n</trkseg>", 1)
    assert len(data) <= 20 * 1024 * 1024
    started = time.perf_counter()
    run(data)
    assert time.perf_counter() - started < 10


# --- Track Metrics ----------------------------------------------------------------


def test_category_assigned() -> None:
    assert run(to_gpx(straight(5200))).metrics.category == "5"
    bounds = (3000, 7500, 15000, 25000)
    assert [category_for(d, bounds) for d in (2999, 3000, 7499, 7500, 15000, 24999, 25000)] == [
        "1", "5", "5", "10", "21", "21", "21+",
    ]  # fmt: skip


def test_stops_excluded_from_moving_time() -> None:
    m = run(to_gpx(straight(2000, pace_s_per_km=300, stops={1000: 120}))).metrics
    assert m.total_time_s == pytest.approx(600 + 120, abs=2)
    assert m.moving_time_s == pytest.approx(600, abs=2)
    assert m.avg_pace_s_per_km == pytest.approx(360, abs=2)  # общее время / дистанция


def test_kilometre_splits() -> None:
    m = run(to_gpx(straight(10_300, pace_s_per_km=300))).metrics
    assert len(m.splits) == 11
    assert all(s.distance_m == 1000 for s in m.splits[:10])
    assert m.splits[-1].distance_m == pytest.approx(300, abs=1)
    assert all(s.time_s == pytest.approx(300, abs=1) for s in m.splits[:10])


def test_gps_spike_ignored() -> None:
    pts = straight(1000)
    spike = pts[300]
    pts[300] = type(spike)(*offset(spike.lat, spike.lon, 500, 0), spike.t)
    m = run(to_gpx(pts)).metrics
    assert m.distance_m == pytest.approx(1000, abs=10)


def test_elevation_gain() -> None:
    m = run(to_gpx(straight(2000, ele=True))).metrics
    assert m.has_elevation
    # синусоида 100±25 м с периодом 1 км: подъёмы 25 + 50 + 25 = 100 м
    assert m.elevation_gain_m == pytest.approx(100, abs=8)


def test_working_geometries() -> None:
    result = run(to_gpx(straight(3000, bearing_deg=45)))
    route = result.visibility.route
    proj = Projection.for_point(route[0][1], route[0][0])
    xy = proj.to_xy([p[1] for p in route], [p[0] for p in route])
    steps = [math.dist(a, b) for a, b in zip(xy, xy[1:], strict=False)]
    assert all(s == pytest.approx(10, abs=0.05) for s in steps[:-1])
    assert len(result.visibility.display) < len(result.visibility.visible) / 10
    assert result.visibility.display[0] == pytest.approx(route[0][:2], abs=1e-6)


# --- Implausible Tracks Rejected --------------------------------------------------


def test_no_timestamps() -> None:
    pts = straight(1000)
    for p in pts:
        p.t = None
    with pytest.raises(TrackRejectedError) as err:
        run(to_gpx(pts))
    assert err.value.reason == RejectReason.no_time
    assert str(err.value) == "в файле нет времени"


def test_too_fast() -> None:
    with pytest.raises(TrackRejectedError) as err:
        run(to_gpx(straight(5000, pace_s_per_km=130)))  # 2:10 мин/км
    assert err.value.reason == RejectReason.too_fast
    assert str(err.value) == "похоже на транспорт"


# --- Home Privacy Zones -----------------------------------------------------------


def test_start_inside_zone() -> None:
    pts = straight(3000, bearing_deg=0)
    home = offset(*ORIGIN, 0, 150)  # дом в 150 м от старта по ходу трека
    result = run(to_gpx(pts), home=home, radius=300)
    vis = result.visibility
    assert vis.range is not None and vis.range.from_m == pytest.approx(450, abs=2)
    for geometry in (vis.visible, vis.route, vis.display):
        assert min(haversine(home, (p[1], p[0])) for p in geometry) >= 300


def test_finish_inside_zone() -> None:
    pts = straight(3000, bearing_deg=0)
    home = offset(*ORIGIN, 0, 2900)
    vis = run(to_gpx(pts), home=home, radius=300).visibility
    assert vis.range is not None and vis.range.to_m == pytest.approx(2600, abs=2)


def test_middle_pass_stays_visible() -> None:
    home = offset(*ORIGIN, 100, 1500)  # трек проходит в 100 м от дома посередине
    vis = run(to_gpx(straight(3000)), home=home, radius=300).visibility
    assert vis.range is not None
    assert (vis.range.from_m, vis.range.to_m) == pytest.approx((0, 3000), abs=1)


def test_no_home_set() -> None:
    result = run(to_gpx(straight(2000)))
    assert result.visibility.range is not None
    assert result.visibility.range.from_m == 0
    assert result.visibility.range.to_m == pytest.approx(result.metrics.distance_m)


def test_track_entirely_inside_zone() -> None:
    vis = run(to_gpx(circle(ORIGIN, 150, laps=2)), home=ORIGIN, radius=300).visibility
    assert vis.range is None and vis.display == [] and vis.route == []


# --- Photos ------------------------------------------------------------------------


def test_photo_location_stripped() -> None:
    original = jpeg_with_gps()
    assert Image.open(io.BytesIO(original)).getexif().get_ifd(0x8825)
    clean, content_type, ext = sanitize(original)
    img = Image.open(io.BytesIO(clean))
    assert content_type == "image/jpeg" and ext == "jpg"
    assert not img.getexif()
    assert "exif" not in img.info
    assert max(img.size) == 2048
