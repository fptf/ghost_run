## ADDED Requirements
### Requirement: Local Environment
Проект SHALL запускаться локально одной командой со всеми зависимостями.

#### Scenario: Cold start
- **WHEN** разработчик выполняет `docker compose up` в чистом клоне
- **THEN** поднимаются api, worker, postgres+postgis, redis, minio и frontend
- **AND** `GET /health` возвращает 200 со статусом каждой зависимости

### Requirement: Runtime Settings
Система SHALL хранить настраиваемые параметры в БД и читать их без перезапуска.

#### Scenario: Threshold changed
- **WHEN** администратор меняет значение настройки `matching.corridor_coverage`
- **THEN** следующее сопоставление использует новое значение без деплоя

### Requirement: Continuous Integration
Каждый PR MUST проходить линтеры, проверку типов и тесты бэкенда и фронта.

#### Scenario: Failing test
- **WHEN** в PR падает хотя бы один тест
- **THEN** CI помечает PR как непрошедший
