## 1. Repository
- [x] 1.1 Структура монорепозитория, README с запуском одной командой, `.env.example`
- [x] 1.2 Проверить, что `docs/tz.md` и `docs/project.md` на месте

## 2. Backend skeleton
- [x] 2.1 FastAPI-приложение, конфигурация через переменные окружения (uv, pyproject.toml)
- [x] 2.2 SQLAlchemy + Alembic, миграция с `CREATE EXTENSION postgis` и таблицей `settings`
- [x] 2.3 Сид настроек: пороги раздела 5, границы категорий, коэффициенты популярности, лимиты загрузки, радиус скрытия
- [x] 2.4 Сервис настроек: чтение из БД без кеша в процессе
- [x] 2.5 `GET /health` проверяет БД, Redis и S3; 200 или 503
- [x] 2.6 Celery-воркер с задачей `ping`
- [x] 2.7 Конфиги ruff, black, mypy (strict для `app/domain`)

## 3. Backend tests
- [x] 3.1 Тест «Cold start»: `/health` = 200 и все `checks` = ok (testcontainers)
- [x] 3.2 Тест «Dependency down»: 503 и упавшая зависимость для БД, Redis, S3
- [x] 3.3 Тест «Threshold changed»: изменение `matching.corridor_coverage` видно при следующем чтении
- [x] 3.4 Тест «Defaults seeded»: после миграций все ключи со значениями из ТЗ
- [x] 3.5 Тест «Ping task»: воркер возвращает `pong`

## 4. Frontend skeleton
- [x] 4.1 Vite + React + TS (strict), роутинг, i18n (ru)
- [x] 4.2 Экспорт `backend/openapi.json` и генерация клиента (`openapi-typescript` + `openapi-fetch`)
- [x] 4.3 eslint + prettier, smoke-тест на Vitest

## 5. Dev & CI
- [x] 5.1 docker-compose.yml со всеми сервисами и инициализацией бакета S3
- [x] 5.2 GitHub Actions: ruff, black, mypy, pytest, eslint, prettier, tsc, vitest, проверка дрейфа OpenAPI
- [x] 5.3 Тест «Failing test»: workflow содержит все проверки (разбор YAML)
- [x] 5.4 Тест «OpenAPI drift»: экспорт схемы совпадает с `backend/openapi.json`
- [x] 5.5 Проверка: `docker compose up` в чистом состоянии, `GET /health` = 200
