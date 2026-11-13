## ADDED Requirements
### Requirement: Local Environment
Проект SHALL запускаться локально одной командой со всеми зависимостями.

#### Scenario: Cold start
- **WHEN** разработчик выполняет `docker compose up` в чистом клоне
- **THEN** поднимаются api, worker, postgres+postgis, redis, minio и frontend
- **AND** `GET /health` возвращает 200 с телом `{"status": "ok", "checks": {"db": "ok", "redis": "ok", "s3": "ok"}}`

#### Scenario: Dependency down
- **WHEN** БД, Redis или S3 недоступны
- **THEN** `GET /health` возвращает 503 со `status: "error"`
- **AND** в `checks` упавшая зависимость помечена как `"error"`, остальные — как `"ok"`

### Requirement: Runtime Settings
Система SHALL хранить настраиваемые параметры в таблице `settings` (key, value jsonb) и читать их без перезапуска.

#### Scenario: Threshold changed
- **WHEN** значение настройки `matching.corridor_coverage` в таблице `settings` изменено
- **THEN** следующее чтение через сервис настроек возвращает новое значение без перезапуска процесса

#### Scenario: Defaults seeded
- **WHEN** к пустой БД применены миграции
- **THEN** таблица `settings` содержит значения из ТЗ:
  `matching.start_finish_radius_m` = 50, `matching.corridor_width_m` = 30,
  `matching.corridor_coverage` = 0.9, `matching.length_tolerance` = 0.03,
  `matching.loop_threshold_m` = 50, `matching.candidate_start_radius_m` = 50,
  `comparison.tie_threshold_s` = 1, `categories.bounds_m` = [3000, 7500, 15000, 25000],
  `popularity.weights` = {runners: 5, downloads: 2, likes: 1}, `popularity.recalc_interval_s` = 3600,
  `upload.max_file_bytes` = 20971520, `upload.min_pace_s_per_km` = 150,
  `upload.rate_limit_per_hour` = 20, `privacy.hide_radius_m` = {min: 200, max: 500}

### Requirement: Background Worker
Фоновые задачи SHALL выполняться Celery-воркером через очередь Redis.

#### Scenario: Ping task
- **WHEN** API ставит в очередь задачу `ping`
- **THEN** воркер выполняет её и возвращает результат `"pong"`

### Requirement: Continuous Integration
Каждый PR MUST проходить линтеры, проверку типов и тесты бэкенда и фронта.

#### Scenario: Failing test
- **WHEN** в CI падает хотя бы один линтер, проверка типов или тест
- **THEN** job CI завершается с ошибкой
- **AND** workflow запускает ruff, black, mypy, pytest, eslint, prettier, tsc и vitest

#### Scenario: OpenAPI drift
- **WHEN** схема OpenAPI бэкенда изменилась, а `openapi.json` или сгенерированный клиент фронта не обновлены
- **THEN** CI завершается с ошибкой
