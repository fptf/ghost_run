## 1. Backend
- [x] 1.1 Миграция: `parent_track_id`, `track_downloads`, pg_trgm и индексы, настройки `map.cluster_max_zoom`, `map.max_lines`
- [x] 1.2 `GET /tracks/search`: bbox, зум, категория или диапазон км, время, темп, даты, «есть попытки», текст, сортировки, пагинация
- [x] 1.3 Кластеры при мелком зуме, линии видимой части при крупном
- [x] 1.4 `GET /tracks/{id}/gpx` без скрытых зон и времени; учёт скачиваний
- [x] 1.5 Отметки километров в ответе трека
- [x] 1.6 Зафиксировать OSM-тайлы и MapLibre в `docs/project.md`
- [x] 1.7 Фильтр «новые» (`search.new_days`), признак `is_new` в выдаче

## 2. Frontend
- [x] 2.1 Навигация: нижняя панель на телефоне, меню на десктопе; ленивые страницы с картой
- [x] 2.2 Главная: карта (линии, кластеры, выбранный трек со стартом и финишем), состояние в адресе, Владивосток по умолчанию
- [x] 2.3 Фильтр дистанции 1/5/10/21/21+/своя; время, темп, дата, «есть попытки»; поиск; сортировка
- [x] 2.4 Список: панель слева на десктопе, выдвижной снизу на телефоне
- [x] 2.5 Карточка: в панели на десктопе, экран на телефоне; отметки км, «Скачать GPX», «Показать на карте», место под группу
- [x] 2.6 Настройки профиля: «Назад», после сохранения — в профиль с подтверждением

- [x] 2.7 Быстрые переключатели «Новые» и «Есть попытки», «Сбросить», явное скрытие списка (телефон и десктоп)
- [x] 2.8 Вопрос «Показать треки рядом с вами?» при первом заходе; исходная область для сброса

## 3. Tests
- [x] 3.1 Map Display: Close zoom, City-wide zoom, Attempts hidden, Not public tracks hidden, Initial area
- [x] 3.2 Distance Filter: Category 5 km, Custom range; Other Filters: Pace range, Date range
- [x] 3.3 Sorting: Sort by pace; Text Search: Search by author
- [x] 3.4 Live Results: Pan map, Shareable state
- [x] 3.5 Track Card: Download GPX, Kilometre marks, Show on map
- [x] 3.6 Profile: Save settings, Leave settings
- [x] 3.7 New tracks, Reset, Hide list, Accept nearby, Decline nearby
