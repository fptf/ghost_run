## 1. Backend
- [x] 1.1 Модели User и RefreshToken, миграция (GeoAlchemy2, роль, точка дома, радиус), настройка `auth.rate_limit_per_minute`
- [x] 1.2 `IdentityVerifier`: Google (`google-auth`) и dev-вход под флагом `AUTH_DEV_LOGIN`
- [x] 1.3 Эндпоинты `/auth/config`, `/auth/google`, `/auth/dev-login`, `/auth/refresh`, `/auth/logout`
- [x] 1.4 Access JWT 15 мин, refresh в httpOnly-cookie с ротацией и отзывом семейства
- [x] 1.5 `GET/PATCH /me`, `GET /users/{id}` (публичная схема без email и дома)
- [x] 1.6 Точка дома и радиус с проверкой границ из `privacy.hide_radius_m`
- [x] 1.7 `DELETE /me` и реестр очистки (S3-префикс пользователя)
- [x] 1.8 Лимит попыток входа через Redis (refresh под лимит не попадает)
- [x] 1.9 CLI назначения роли

## 2. Frontend
- [x] 2.1 `AuthProvider`, токен в памяти, авто-обновление, `RequireAuth` и `/login?next=`
- [x] 2.2 Экран входа: кнопка Google (если есть Client ID) и dev-форма (если включена)
- [x] 2.3 Шапка с «Загрузить трек», заглушка `/upload` за входом
- [x] 2.4 Профиль: статистика, ленты «Мои треки», «Мои попытки», «Ачивки» (пока пустые); публичный профиль
- [x] 2.5 Настройки: имя, город, описание, точка дома (координаты, «Моё местоположение»), радиус, удаление аккаунта
- [x] 2.6 Базовые стили по токенам макетов (акцент #C2410C, Inter), адаптив от 360 px, favicon

## 3. Tests
- [x] 3.1 auth: First Google sign-in, Returning user, Invalid Google token
- [x] 3.2 auth: Dev sign-in disabled / enabled
- [x] 3.3 auth: Expired access token, Refresh token reuse, Sign out
- [x] 3.4 auth: Too many attempts, Page reloads keep the session, Assign role
- [x] 3.5 auth: Guest starts upload (Vitest: редирект на вход и возврат на `/upload`)
- [x] 3.6 profile: Guest views profile, Edit profile
- [x] 3.7 profile: Radius out of range, Home point stays private
- [x] 3.8 profile: Delete account

## 4. Docs
- [x] 4.1 Решения 13.11.2026 в `docs/tz.md` (раздел 11), README: как подключить Google Client ID
