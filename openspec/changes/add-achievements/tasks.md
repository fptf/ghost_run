## 1. Backend
- [ ] 1.1 Миграция: achievements (сид «Превзошёл»), user_achievements, attempts.activated_at, tracks.attempts_seen_at
- [ ] 1.2 sync_achievements после любых изменений группы; идемпотентно
- [ ] 1.3 `GET /tracks/{id}/result` — исход, разница, место, соседи, ачивки
- [ ] 1.4 Счётчик новых попыток: `/me.new_attempts`, по треку в «Мои треки», сброс при открытии группы автором
- [ ] 1.5 `GET /users/{id}/achievements`; ачивки на просмотре попытки
- [ ] 1.6 Отзыв при скрытии модератором и выходе из группы

## 2. Frontend
- [ ] 2.1 Экраны результата по макетам ResultWin и ResultSlower; переход после публикации попытки
- [ ] 2.2 Значок счётчика на «Профиль» в навигации; счётчики в «Мои треки»
- [ ] 2.3 Витрина ачивок в профиле, отметка на попытке; «Поделиться»

## 3. Tests
- [ ] 3.1 Outperformed: Beat the author, Own route, Equal, Repeated processing
- [ ] 3.2 Result Screen: Faster, Slower, No match
- [ ] 3.3 Counter grows and resets; Showcase; Fraud hidden; Attempt detached
- [ ] 3.4 Vitest: экраны результата, переход после публикации, значок счётчика, витрина
