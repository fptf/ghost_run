"""Requirement: Runtime Settings — сценарии Threshold changed и Defaults seeded."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.settings_defaults import DEFAULT_SETTINGS
from app.infra.settings_repo import all_settings, get_setting, set_setting

# Значения выписаны из ТЗ вручную, а не импортированы, чтобы тест ловил расхождения.
EXPECTED_FROM_TZ = {
    "matching.start_finish_radius_m": 50,  # 5.1 п.1
    "matching.corridor_width_m": 30,  # 5.1 п.2
    "matching.corridor_coverage": 0.9,  # 5.1 п.2
    "matching.length_tolerance": 0.03,  # 5.1 п.4
    "matching.loop_threshold_m": 50,  # 5.1 круговой маршрут
    "matching.candidate_start_radius_m": 50,  # ФТ-15
    "comparison.tie_threshold_s": 1,  # 5.2
    "categories.bounds_m": [3000, 7500, 15000, 25000],  # 5.3
    "popularity.weights": {"runners": 5, "downloads": 2, "likes": 1},  # ФТ-28
    "popularity.recalc_interval_s": 3600,  # раздел 6
    "upload.max_file_bytes": 20 * 1024 * 1024,  # ФТ-5
    "upload.min_pace_s_per_km": 150,  # ФТ-7: 2:30 мин/км
    "upload.rate_limit_per_hour": 20,  # раздел 8
    "privacy.hide_radius_m": {"min": 200, "max": 500},  # ФТ-4
}


def test_defaults_seeded(db: Session) -> None:
    assert all_settings(db) == EXPECTED_FROM_TZ


def test_domain_defaults_match_tz() -> None:
    assert DEFAULT_SETTINGS == EXPECTED_FROM_TZ


def test_postgis_enabled(db: Session) -> None:
    assert db.execute(text("SELECT postgis_version()")).scalar()


def test_threshold_changed_visible_without_restart(db: Session) -> None:
    key = "matching.corridor_coverage"
    original = get_setting(db, key)
    assert original == 0.9
    try:
        # Меняем значение «снаружи» — прямым SQL, как это сделал бы администратор.
        db.execute(text("UPDATE settings SET value = '0.85'::jsonb WHERE key = :k"), {"k": key})
        db.commit()
        assert get_setting(db, key) == 0.85
    finally:
        set_setting(db, key, original)
    assert get_setting(db, key) == 0.9
