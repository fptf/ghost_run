## 1. Repository
- [ ] 1.1 Структура монорепозитория, README с запуском одной командой
- [ ] 1.2 Проверить, что `docs/tz.md` и `docs/project.md` на месте

## 2. Backend skeleton
- [ ] 2.1 FastAPI-приложение, конфигурация через переменные окружения
- [ ] 2.2 SQLAlchemy + Alembic, миграция с `CREATE EXTENSION postgis` и таблицей `settings`
- [ ] 2.3 Сид настроек: пороги раздела 5, границы категорий, коэффициенты популярности
- [ ] 2.4 `GET /health` проверяет БД, Redis и S3
- [ ] 2.5 Celery-воркер с тестовой задачей

## 3. Frontend skeleton
- [ ] 3.1 Vite + React + TS, роутинг, i18n (ru)
- [ ] 3.2 Генерация API-клиента из OpenAPI

## 4. Dev & CI
- [ ] 4.1 docker-compose.yml со всеми сервисами
- [ ] 4.2 GitHub Actions: ruff, mypy, pytest (PostGIS), eslint, tsc, vitest
