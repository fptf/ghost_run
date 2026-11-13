## Why
Нужен рабочий каркас, на который ложатся все остальные изменения: репозиторий, окружение
разработки, БД с PostGIS, очередь, хранилище файлов и CI (раздел 9 ТЗ; основа для ФТ-1–33).

## What Changes
- Монорепозиторий: `backend/` (FastAPI), `frontend/` (React + Vite), `docs/`, `openspec/`.
- Docker Compose: api, worker (Celery), postgres+postgis, redis, s3 (SeaweedFS), frontend.
- Alembic с первой миграцией (расширение PostGIS, таблица настроек `settings` с сидом
  порогов из разделов 5.1–5.3, ФТ-5, ФТ-7, ФТ-28 и раздела 8).
- Health-check API (200/503), пустая страница фронта, сгенерированный API-клиент.
- CI: линтеры, типы, тесты бэкенда и фронта, проверка дрейфа OpenAPI.

## Impact
- Affected specs: platform (новая)
- Affected code: весь каркас
