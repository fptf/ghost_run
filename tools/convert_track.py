"""Конвертация GPX в TCX и FIT для тестовых фикстур (из окружения backend).

    cd backend && uv run python ../tools/convert_track.py tests/fixtures/tracks/run_20261026.gpx

Рядом с исходником появляются .tcx и .fit с теми же точками и временем.
"""

import sys
from datetime import UTC
from pathlib import Path
from xml.sax.saxutils import escape

import gpxpy
from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.activity_message import ActivityMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.profile_type import FileType, Manufacturer, Sport


def load(path: Path) -> list[gpxpy.gpx.GPXTrackPoint]:
    with path.open(encoding="utf-8") as f:
        gpx = gpxpy.parse(f)
    return [p for t in gpx.tracks for s in t.segments for p in s.points]


def iso(p: gpxpy.gpx.GPXTrackPoint) -> str:
    assert p.time is not None
    return p.time.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def write_tcx(points: list[gpxpy.gpx.GPXTrackPoint], path: Path) -> None:
    rows = []
    for p in points:
        ele = f"<AltitudeMeters>{p.elevation:.1f}</AltitudeMeters>" if p.elevation is not None else ""
        rows.append(
            f"<Trackpoint><Time>{iso(p)}</Time><Position>"
            f"<LatitudeDegrees>{p.latitude:.7f}</LatitudeDegrees>"
            f"<LongitudeDegrees>{p.longitude:.7f}</LongitudeDegrees></Position>{ele}</Trackpoint>"
        )
    start = iso(points[0])
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">'
        f'<Activities><Activity Sport="Running"><Id>{escape(start)}</Id>'
        f'<Lap StartTime="{start}"><Track>{"".join(rows)}</Track></Lap>'
        "</Activity></Activities></TrainingCenterDatabase>\n",
        encoding="utf-8",
    )


def write_fit(points: list[gpxpy.gpx.GPXTrackPoint], path: Path) -> None:
    assert points[0].time is not None and points[-1].time is not None
    start_ms = round(points[0].time.timestamp() * 1000)
    end_ms = round(points[-1].time.timestamp() * 1000)
    builder = FitFileBuilder(auto_define=True, min_string_size=50)

    file_id = FileIdMessage()
    file_id.type = FileType.ACTIVITY
    file_id.manufacturer = Manufacturer.DEVELOPMENT.value
    file_id.product = 0
    file_id.serial_number = 1
    file_id.time_created = start_ms
    builder.add(file_id)

    for p in points:
        assert p.time is not None
        rec = RecordMessage()
        rec.timestamp = round(p.time.timestamp() * 1000)
        rec.position_lat = p.latitude
        rec.position_long = p.longitude
        if p.elevation is not None:
            rec.altitude = p.elevation
        builder.add(rec)

    lap = LapMessage()
    lap.timestamp = end_ms
    lap.start_time = start_ms
    lap.total_elapsed_time = (end_ms - start_ms) / 1000
    builder.add(lap)

    session = SessionMessage()
    session.timestamp = end_ms
    session.start_time = start_ms
    session.total_elapsed_time = (end_ms - start_ms) / 1000
    session.sport = Sport.RUNNING
    builder.add(session)

    activity = ActivityMessage()
    activity.timestamp = end_ms
    activity.num_sessions = 1
    builder.add(activity)

    builder.build().to_file(str(path))


def main(src: Path) -> None:
    points = load(src)
    write_tcx(points, src.with_suffix(".tcx"))
    write_fit(points, src.with_suffix(".fit"))
    print(f"{src.name}: {len(points)} точек -> .tcx, .fit")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
