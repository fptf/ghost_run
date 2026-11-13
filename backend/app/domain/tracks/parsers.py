"""GPX, TCX и FIT в единый список точек."""

import io
from datetime import UTC, datetime

import gpxpy
import gpxpy.gpx
from fitparse import FitFile, FitParseError
from lxml import etree

from app.domain.tracks.model import FileFormat, Point, RejectReason, TrackRejectedError

SEMICIRCLE = 180.0 / 2**31
TCX_NS = "{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}"


def detect_format(head: bytes) -> FileFormat | None:
    """Определяет формат по сигнатуре содержимого, а не по расширению."""
    if len(head) >= 12 and head[8:12] == b".FIT":
        return FileFormat.fit
    text = head[:4096].decode("utf-8", errors="ignore").lstrip("﻿").lower()
    if "<trainingcenterdatabase" in text:
        return FileFormat.tcx
    if "<gpx" in text:
        return FileFormat.gpx
    return None


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def parse_gpx(data: bytes) -> list[Point]:
    try:
        gpx = gpxpy.parse(data.decode("utf-8-sig", errors="replace"))
    except gpxpy.gpx.GPXException as exc:
        raise TrackRejectedError(RejectReason.broken_file) from exc
    return [
        Point(p.latitude, p.longitude, _utc(p.time), p.elevation)
        for track in gpx.tracks
        for segment in track.segments
        for p in segment.points
    ]


def parse_tcx(data: bytes) -> list[Point]:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)
    try:
        root = etree.fromstring(data, parser)
    except etree.XMLSyntaxError as exc:
        raise TrackRejectedError(RejectReason.broken_file) from exc
    points: list[Point] = []
    for tp in root.iter(f"{TCX_NS}Trackpoint"):
        lat = tp.findtext(f"{TCX_NS}Position/{TCX_NS}LatitudeDegrees")
        lon = tp.findtext(f"{TCX_NS}Position/{TCX_NS}LongitudeDegrees")
        if lat is None or lon is None:
            continue  # точки без координат (например, на паузе)
        time_text = tp.findtext(f"{TCX_NS}Time")
        ele_text = tp.findtext(f"{TCX_NS}AltitudeMeters")
        time = _utc(datetime.fromisoformat(time_text.replace("Z", "+00:00"))) if time_text else None
        points.append(Point(float(lat), float(lon), time, float(ele_text) if ele_text else None))
    return points


def parse_fit(data: bytes) -> list[Point]:
    try:
        fit = FitFile(io.BytesIO(data))
        points: list[Point] = []
        for record in fit.get_messages("record"):
            values = record.get_values()
            lat, lon = values.get("position_lat"), values.get("position_long")
            if lat is None or lon is None:
                continue
            ele = values.get("enhanced_altitude", values.get("altitude"))
            points.append(
                Point(
                    float(lat) * SEMICIRCLE,
                    float(lon) * SEMICIRCLE,
                    _utc(values.get("timestamp")),
                    float(ele) if ele is not None else None,
                )
            )
    except FitParseError as exc:
        raise TrackRejectedError(RejectReason.broken_file) from exc
    return points


def parse(data: bytes, fmt: FileFormat) -> list[Point]:
    parsers = {FileFormat.gpx: parse_gpx, FileFormat.tcx: parse_tcx, FileFormat.fit: parse_fit}
    return parsers[fmt](data)
