## 1. Backend
- [ ] 1.1 Модели User и RefreshToken, миграция (GeoAlchemy2, роль, точка дома, радиус), настройка `auth.rate_limit_per_minute`
- [ ] 1.2 `IdentityVerifier`: Google (`google-auth`) и dev-вход под флагом `AUTH_DEV_LOGIN`
- [ ] 1.3 Эндпоинты `/auth/config`, `/auth/google`, `/auth/dev-login`, `/auth/refresh`, `/auth/logout`
- [ ] 1.4 Access JWT 15 мин, refresh в httpOnly-cookie с ротацией и отзывом семейства
- [ ] 1.5 `GET/PATCH /me`, `GET /users/{id}` (публичная схема без email и дома)
- [ ] 1.6 Точка дома и радиус с проверкой границ из `privacy.hide_radius_m`
- [ ] 1.7 `DELETE /me` и реестр очистки (S3-префикс пользователя)
- [ ] 1.8 Лимит запросов на `/auth/*` через Redis
- [ ] 1.9 CLI назначения роли

## 2. Frontend
- [ ] 2.1 `AuthProvider`, токен в памяти, авто-обновление, `RequireAuth` и `/login?next=`
- [ ] 2.2 Экран входа: кнопка Google (если есть Client ID) и dev-форма (если включена)
- [ ] 2.3 Шапка с «Загрузить трек», заглушка `/upload` за входом
- [ ] 2.4 Профиль: статистика, ленты «Мои треки», «Мои попытки», «Ачивки» (пока пустые); публичный профиль
- [ ] 2.5 Настройки: имя, город, описание, точка дома (координаты, «Моё местоположение»), радиус, удаление аккаунта

## 3. Tests
- [ ] 3.1 auth: First Google sign-in, Returning user, Invalid Google token
- [ ] 3.2 auth: Dev sign-in disabled / enabled
- [ ] 3.3 auth: Expired access token, Refresh token reuse, Sign out
- [ ] 3.4 auth: Too many attempts, Assign role
- [ ] 3.5 auth: Guest starts upload (Vitest: редирект на вход и возврат на `/upload`)
- [ ] 3.6 profile: Guest views profile, Edit profile
- [ ] 3.7 profile: Radius out of range, Home point stays private
- [ ] 3.8 profile: Delete account

## 4. Docs
- [ ] 4.1 Решения 13.11.2026 в `docs/tz.md` (раздел 11), README: как подключить Google Client ID
