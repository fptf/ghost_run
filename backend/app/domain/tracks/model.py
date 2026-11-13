from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class Point:
    lat: float
    lon: float
    time: datetime | None
    ele: float | None = None


class FileFormat(StrEnum):
    gpx = "gpx"
    tcx = "tcx"
    fit = "fit"


class RejectReason(StrEnum):
    unsupported_format = "unsupported_format"
    too_large = "too_large"
    no_time = "no_time"
    too_fast = "too_fast"
    too_short = "too_short"
    broken_file = "broken_file"


REJECT_MESSAGES: dict[RejectReason, str] = {
    RejectReason.unsupported_format: "формат не поддерживается",
    RejectReason.too_large: "файл больше 20 МБ",
    RejectReason.no_time: "в файле нет времени",
    RejectReason.too_fast: "похоже на транспорт",
    RejectReason.too_short: "в треке слишком мало точек",
    RejectReason.broken_file: "файл повреждён или не читается",
}


class TrackRejectedError(Exception):
    def __init__(self, reason: RejectReason) -> None:
        self.reason = reason
        super().__init__(REJECT_MESSAGES[reason])
