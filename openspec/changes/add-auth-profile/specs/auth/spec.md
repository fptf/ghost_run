## ADDED Requirements
### Requirement: Email Registration
Система SHALL регистрировать пользователя по email и паролю только с согласием на обработку персональных данных.

#### Scenario: Successful registration
- **WHEN** гость вводит новый email, пароль от 8 символов и отмечает согласие
- **THEN** создаётся аккаунт с ролью runner и выдаются access- и refresh-токены

#### Scenario: Consent missing
- **WHEN** гость не отметил согласие
- **THEN** регистрация отклоняется с понятной причиной

### Requirement: OAuth Sign-in
Система SHALL позволять вход через Google и Apple.

#### Scenario: First OAuth sign-in
- **WHEN** пользователь впервые входит через Google
- **THEN** создаётся аккаунт, связанный с его Google-идентификатором

### Requirement: Return After Sign-in
Система SHALL возвращать гостя на действие, ради которого он пошёл входить.

#### Scenario: Guest starts upload
- **WHEN** гость нажимает «Загрузить трек» и проходит вход
- **THEN** он попадает на экран загрузки, а не на главную

### Requirement: Token Lifecycle
Access-токен MUST жить не дольше 15 минут; обновление идёт через refresh-токен с ротацией.

#### Scenario: Expired access token
- **WHEN** клиент обращается с истёкшим access-токеном и действующим refresh-токеном
- **THEN** клиент получает новую пару токенов, старый refresh-токен становится недействительным
