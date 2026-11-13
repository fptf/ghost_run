## ADDED Requirements
### Requirement: Google Sign-in
Система SHALL регистрировать и впускать пользователя только через Google: бэкенд проверяет `id_token` Google и связывает аккаунт с идентификатором Google (`sub`).

#### Scenario: First Google sign-in
- **WHEN** пользователь впервые входит с действительным `id_token` Google
- **THEN** создаётся аккаунт с ролью runner, именем, email и аватаром из Google
- **AND** выдаются access-токен и refresh-токен в httpOnly-cookie

#### Scenario: Returning user
- **WHEN** пользователь с уже существующим аккаунтом снова входит через Google
- **THEN** он попадает в тот же аккаунт, новый аккаунт не создаётся

#### Scenario: Invalid Google token
- **WHEN** клиент присылает недействительный или чужой (`aud` не совпадает) `id_token`
- **THEN** вход отклоняется с кодом 401

### Requirement: Dev Sign-in
Система SHALL поддерживать вход без Google только при включённом флаге окружения `AUTH_DEV_LOGIN`; в проде флаг выключен.

#### Scenario: Dev sign-in disabled
- **WHEN** флаг `AUTH_DEV_LOGIN` выключен и клиент вызывает dev-вход
- **THEN** ответ 404

#### Scenario: Dev sign-in enabled
- **WHEN** флаг включён и клиент вызывает dev-вход с email и именем
- **THEN** создаётся или находится аккаунт и выдаются токены, как при входе через Google

### Requirement: Return After Sign-in
Система SHALL возвращать гостя на действие, ради которого он пошёл входить.

#### Scenario: Guest starts upload
- **WHEN** гость нажимает «Загрузить трек» и проходит вход
- **THEN** он попадает на экран загрузки, а не на главную

### Requirement: Token Lifecycle
Access-токен MUST жить не дольше 15 минут; обновление идёт через refresh-токен с ротацией.

#### Scenario: Expired access token
- **WHEN** клиент обращается с истёкшим access-токеном и действующим refresh-токеном
- **THEN** защищённый запрос отклоняется с 401, обновление выдаёт новую пару токенов
- **AND** старый refresh-токен становится недействительным

#### Scenario: Refresh token reuse
- **WHEN** уже использованный refresh-токен предъявлен повторно
- **THEN** обновление отклоняется и все refresh-токены этой сессии отзываются

#### Scenario: Sign out
- **WHEN** пользователь выходит
- **THEN** его refresh-токен отзывается, cookie очищается

### Requirement: Auth Rate Limit
Запросы к `/auth/*` MUST ограничиваться по IP; лимит читается из настройки `auth.rate_limit_per_minute` (по умолчанию 10).

#### Scenario: Too many attempts
- **WHEN** с одного IP за минуту приходит больше запросов, чем разрешено
- **THEN** лишние запросы получают 429

### Requirement: Roles
Пользователь SHALL иметь одну роль: runner, moderator или admin; новые пользователи — runner.

#### Scenario: Assign role
- **WHEN** администратор системы запускает CLI назначения роли для email
- **THEN** роль пользователя меняется, и она видна в его собственном профиле
