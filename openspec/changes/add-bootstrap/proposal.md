## Why
Нужен рабочий каркас, на который ложатся все остальные изменения: репозиторий, окружение
разработки, БД с PostGIS, очередь, хранилище файлов и CI.

## What Changes
- Монорепозиторий: `backend/` (FastAPI), `frontend/` (React + Vite), `docs/`, `openspec/`.
- Docker Compose: api, worker (Celery), postgres+postgis, redis, minio, frontend.
- Alembic с первой миграцией (расширение PostGIS, таблица настроек `settings`).
- Health-check API, пустая страница фронта, сгенерированный API-клиент.
- CI: линтеры, типы, тесты бэкенда и фронта.

## Impact
- Affected specs: platform (новая)
- Affected code: весь каркас
