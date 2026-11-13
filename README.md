# Бегуны — стартовый пакет OpenSpec

Пакет для старта разработки AI-агентом (Claude Code) по спекам OpenSpec 2.x.

## Что внутри
- `docs/tz.md` — ТЗ
- `docs/design/` — макеты экранов (телефон и десктоп)
- `docs/project.md` — стек, архитектура, доменные термины, ограничения
- `openspec/config.yaml` — контекст и правила для OpenSpec
- `openspec/changes/` — 7 изменений MVP с предложениями, спеками и задачами

## Порядок изменений
1. add-bootstrap — каркас, Docker, PostGIS, очередь, CI
2. add-auth-profile — регистрация, вход, профиль, скрытая зона
3. add-track-upload — загрузка, разбор файлов, показатели, скрытые зоны
4. add-map-search — карта, фильтр дистанции, поиск, карточка трека
5. add-route-matching — автосопоставление, группы, проверка пробежки
6. add-achievements — «Превзошёл», экран результата, счётчик попыток
7. add-ratings — популярность и рейтинги по категориям

4 и 5 можно вести параллельно после 3. Для 5 заранее соберите 10–20 реальных GPX
(линейный, круговой, с разминкой, со срезкой, два круга, обратное направление)
в `backend/tests/fixtures/tracks/`.

## Отложено до запуска
Не блокирует разработку, но обязательно до выхода в прод.

- [ ] **Google OAuth.** Получить Client ID в Google Cloud Console (инструкция — в разделе
      [«Вход»](#вход)) и прописать `GOOGLE_CLIENT_ID`. Пока ключа нет, работает dev-вход.
      Вход через Google покрыт тестами с поддельным Google, но вживую не проверялся.
- [ ] **Боевые настройки входа:** `AUTH_DEV_LOGIN=false`, `COOKIE_SECURE=true`, свой длинный `JWT_SECRET`,
      доверие к `X-Forwarded-For` за прокси (иначе лимит попыток входа общий на всех).

## Запуск

Нужны Docker с compose v2. Одна команда поднимает всё: api, worker, PostGIS, Redis, S3 (SeaweedFS), frontend.

```bash
docker compose up -d --build --wait
curl localhost:8000/health   # {"status":"ok","checks":{"db":"ok","redis":"ok","s3":"ok"}}
open http://localhost:5173   # фронт; /api/* проксируется на бэкенд
```

Порты и пароли — в `.env.example` (у всех значений есть умолчания, `.env` не обязателен).
Миграции применяются и бакет создаётся при старте api.
На Apple Silicon образ PostGIS работает через эмуляцию amd64 (для первого `pytest` его
нужно скачать заранее: `docker pull --platform linux/amd64 postgis/postgis:16-3.5`).

## Вход

Вход только через Google. Пока `GOOGLE_CLIENT_ID` не задан, в разработке работает dev-вход
(`AUTH_DEV_LOGIN=true`, по умолчанию в docker compose): на странице «Вход» — форма email + имя.
Роль назначается так: `docker compose exec api python -m app.scripts.set_role <email> moderator`.

Подключить Google:
1. https://console.cloud.google.com → создать проект.
2. «APIs & Services» → «OAuth consent screen»: тип External, название приложения, email поддержки.
3. «Credentials» → «Create credentials» → «OAuth client ID» → тип «Web application».
   В «Authorized JavaScript origins» добавить `http://localhost:5173` (и боевой домен).
   Redirect URI не нужен — используется Google Identity Services.
4. Скопировать Client ID (вида `….apps.googleusercontent.com`) в `.env`: `GOOGLE_CLIENT_ID=…`,
   затем `docker compose up -d`. Client secret не нужен.
5. В проде: `AUTH_DEV_LOGIN=false`, `COOKIE_SECURE=true`, свой длинный `JWT_SECRET`.

## Разработка

```bash
# backend (Python 3.12, uv)
cd backend
uv sync
uv run ruff check . && uv run black --check . && uv run mypy
uv run pytest                                   # PostGIS, Redis, S3 поднимаются в testcontainers
uv run python -m app.scripts.export_openapi     # после изменения API

# frontend (Node >= 20.19)
cd frontend
npm ci
npm run gen:api                                 # клиент из backend/openapi.json
npm run lint && npm run format:check && npm run typecheck && npm run test
```

Тестовые треки (`backend/tests/fixtures/tracks/`) — только обезличенные копии реальных пробежек:
```bash
python3 -I tools/anonymize_gpx.py <папка с GPX> backend/tests/fixtures/tracks   # сдвиг координат, срез концов
cd backend && uv run python ../tools/convert_track.py tests/fixtures/tracks/run_20261026.gpx  # .tcx и .fit
```
Исходные треки с реальными координатами (`./tracks/`) в git не попадают.

Настройки (пороги сопоставления, категории, популярность, лимиты) лежат в таблице `settings`
и читаются без перезапуска.

## Работа через OpenSpec
```bash
openspec list                                   # изменения и прогресс
openspec validate <change> --strict
```
В Claude Code: `/openspec-apply-change <change>`; после проверки — архивировать изменение,
его спеки переедут в `openspec/specs/`.
