from sqlalchemy.orm import Session

from app.domain.tracks.metrics import MetricsConfig
from app.domain.tracks.pipeline import GeometryConfig
from app.infra.settings_repo import get_setting


def load_configs(db: Session) -> tuple[MetricsConfig, GeometryConfig]:
    def num(key: str) -> float:
        return float(get_setting(db, key))

    metrics = MetricsConfig(
        max_point_speed_mps=num("metrics.max_point_speed_mps"),
        stopped_speed_mps=num("metrics.stopped_speed_mps"),
        elevation_noise_m=num("metrics.elevation_noise_m"),
        min_pace_s_per_km=num("upload.min_pace_s_per_km"),
        category_bounds_m=tuple(int(b) for b in get_setting(db, "categories.bounds_m")),
    )
    geometry = GeometryConfig(
        resample_step_m=num("geometry.resample_step_m"),
        simplify_tolerance_m=num("geometry.simplify_tolerance_m"),
    )
    return metrics, geometry
