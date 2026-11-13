"""Значения настроек по умолчанию из ТЗ (разделы 5.1–5.3, ФТ-4, ФТ-5, ФТ-7, ФТ-28, раздел 8).

Источник истины во время работы — таблица `settings`; этот словарь используется
только для начального сида.
"""

from typing import Any, Final

DEFAULT_SETTINGS: Final[dict[str, Any]] = {
    # 5.1 Проверка совпадения маршрута
    "matching.start_finish_radius_m": 50,
    "matching.corridor_width_m": 30,
    "matching.corridor_coverage": 0.9,
    "matching.length_tolerance": 0.03,
    "matching.loop_threshold_m": 50,
    # ФТ-15 отбор кандидатов
    "matching.candidate_start_radius_m": 50,
    # 5.2 Сравнение результата
    "comparison.tie_threshold_s": 1,
    # 5.3 Категории дистанций: границы 1 км | 5 км | 10 км | 21 км | 21+
    "categories.bounds_m": [3000, 7500, 15000, 25000],
    # ФТ-28 Популярность, раздел 6 — пересчёт раз в час
    "popularity.weights": {"runners": 5, "downloads": 2, "likes": 1},
    "popularity.recalc_interval_s": 3600,
    # ФТ-5, ФТ-7, раздел 8
    "upload.max_file_bytes": 20 * 1024 * 1024,
    "upload.min_pace_s_per_km": 150,
    "upload.rate_limit_per_hour": 20,
    # ФТ-4
    "privacy.hide_radius_m": {"min": 200, "max": 500},
    # add-auth-profile: лимит запросов к /auth/* на IP в минуту
    "auth.rate_limit_per_minute": 10,
    # add-track-upload: очистка GPS, остановки, высота, рабочие геометрии, фото
    "metrics.max_point_speed_mps": 12,
    "metrics.stopped_speed_mps": 0.5,
    "metrics.elevation_noise_m": 3,
    "geometry.resample_step_m": 10,
    "geometry.simplify_tolerance_m": 5,
    "upload.max_photos": 5,
    "upload.max_photo_bytes": 10 * 1024 * 1024,
    # add-map-search: кластеры до этого зума включительно, предел линий на экране
    "map.cluster_max_zoom": 11,
    "map.max_lines": 300,
    "search.new_days": 7,  # «новые» — опубликованные за столько дней
    # add-route-matching: доля точек маршрута, пройденных «по ходу»
    "matching.direction_min_share": 0.9,
}
