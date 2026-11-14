## 1. Backend
- [x] 1.1 Формула популярности — чистая функция с коэффициентами
- [x] 1.2 Миграция `popularity_scores`; пересчёт одним проходом, удаление устаревших строк
- [x] 1.3 Задача `recalc_popularity` в Celery beat, интервал из настроек; воркер с `-B`
- [x] 1.4 `GET /ratings?category=`
- [x] 1.5 Сортировка поиска «Популярные» по пересчитанному значению

## 2. Frontend
- [x] 2.1 Экран рейтингов с вкладками 1, 5, 10, 21, 21+ км
- [x] 2.2 «Рейтинги» в нижней навигации и шапке

## 3. Tests
- [x] 3.1 Score calculation, Weights from settings
- [x] 3.2 Category tab, Attempts and private tracks excluded
- [x] 3.3 New attempt, Schedule; Sort by stored popularity
- [x] 3.4 Vitest: вкладки рейтинга, навигация
