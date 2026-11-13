# Design

## Context
Каркас из add-bootstrap: FastAPI, PostGIS, Redis, S3, таблица `settings`. Вход только через Google,
согласие не берётся (решения 13.11.2026). OAuth-клиента Google пока нет — всё должно работать
и тестироваться без него.

## Goals / Non-Goals

**Goals:**
- Вход через Google и dev-вход за одним интерфейсом проверки личности.
- Безопасный жизненный цикл токенов (раздел 8 ТЗ: короткий JWT, refresh, CSRF/XSS).
- Профиль, точка дома, удаление аккаунта, роли.

**Non-Goals:**
- Email/пароль, Apple, согласие на обработку.
- Загрузка своего аватара (пока используется картинка из Google).
- Выбор точки дома на карте — появится в add-map-search вместе с выбором провайдера тайлов;
  сейчас — координаты и кнопка «Моё местоположение».
- Статистика и ленты считаются в add-track-upload / add-route-matching; сейчас — нули и пустые списки.

## Decisions
- **Google Identity Services + проверка `id_token` на бэкенде** (`google-auth`), а не серверный
  authorization-code flow: не нужен redirect URI на бэкенде и client secret, бэкенд остаётся
  stateless. Проверяются подпись, `iss`, `aud` = наш Client ID, срок действия, `email_verified`.
- **Интерфейс `IdentityVerifier`**: Google-реализация и dev-реализация. Dev-вход доступен только при
  `AUTH_DEV_LOGIN=true` (в docker compose для разработки — включён, по умолчанию — выключен).
- **Токены**: access — JWT HS256 (PyJWT), 15 минут, хранится в памяти фронта (не в localStorage —
  защита от XSS). Refresh — случайные 256 бит, в БД только SHA-256-хеш, срок 30 дней,
  httpOnly + SameSite=Strict cookie (`Secure` включается переменной в проде). Ротация при каждом
  обновлении; повторное предъявление использованного токена отзывает всё семейство (сессию).
  CSRF: cookie нужен только `/auth/refresh` и `/auth/logout`, SameSite=Strict + JSON-тело.
- **Модель**: `users` (uuid, google_sub unique, email unique, name, avatar_url, city, about, role,
  home_point geography(Point,4326) null, hide_radius_m null, created_at) и `refresh_tokens`
  (uuid, user_id FK on delete cascade, family_id, token_hash, expires_at, used_at, revoked_at).
  PostGIS-типы — через GeoAlchemy2.
- **Точка дома** отдаётся только в `GET /me`; публичная схема её не содержит (проверяется тестом).
  Границы радиуса читаются из `privacy.hide_radius_m` при каждой валидации.
- **Удаление аккаунта** — реестр функций очистки `(session, user_id) -> None`; сейчас в нём удаление
  объектов S3 с префиксом `users/{id}/`, остальное каскадом в БД. Следующие изменения добавляют свои.
- **Лимит попыток входа** (`/auth/google`, `/auth/dev-login`) — счётчик в Redis на IP и минуту, лимит из `auth.rate_limit_per_minute`
  (новая миграция). IP — `request.client.host`; доверие к `X-Forwarded-For` настроим при деплое.
- **Роли** назначаются `python -m app.scripts.set_role <email> <role>` до появления админки.
- **Фронт**: `AuthProvider` восстанавливает сессию через `/auth/refresh` при старте, добавляет
  `Authorization` к запросам и один раз повторяет запрос после 401. `RequireAuth` уводит гостя на
  `/login?next=<путь>`; после входа — переход на `next` (только относительные пути — защита от open
  redirect). Кнопка Google показывается, если бэкенд отдал Client ID в `GET /auth/config`.

## Risks / Trade-offs
- [Нет Client ID Google] → dev-вход; Google-верификатор покрыт тестами с подменой проверки подписи.
- [Dev-вход случайно включён в проде] → по умолчанию выключен; при включении — предупреждение в лог
  на старте.
- [IP за прокси одинаковый для всех] → лимит общий; настроить `--proxy-headers` при деплое.

## Open Questions
- Удаление аккаунта автора исходного трека с попытками: ФТ-9 требует сохранять группу, GDPR —
  удалять все треки. Решаем в add-route-matching (вариант: исходным становится следующий трек группы,
  как при скрытии модератором).
