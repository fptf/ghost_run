## 1. Backend
- [ ] 1.1 Миграция: `parent_track_id`, `track_downloads`, pg_trgm и индексы, настройки `map.cluster_max_zoom`, `map.max_lines`
- [ ] 1.2 `GET /tracks/search`: bbox, зум, категория или диапазон км, время, темп, даты, «есть попытки», текст, сортировки, пагинация
- [ ] 1.3 Кластеры при мелком зуме, линии видимой части при крупном
- [ ] 1.4 `GET /tracks/{id}/gpx` без скрытых зон и времени; учёт скачиваний
- [ ] 1.5 Отметки километров в ответе трека
- [ ] 1.6 Зафиксировать OSM-тайлы и MapLibre в `docs/project.md`

## 2. Frontend
- [ ] 2.1 Навигация: нижняя панель на телефоне, меню на десктопе; ленивые страницы с картой
- [ ] 2.2 Главная: карта (линии, кластеры, выбранный трек со стартом и финишем), состояние в адресе, Владивосток по умолчанию
- [ ] 2.3 Фильтр дистанции 1/5/10/21/21+/своя; время, темп, дата, «есть попытки»; поиск; сортировка
- [ ] 2.4 Список: панель слева на десктопе, выдвижной снизу на телефоне
- [ ] 2.5 Карточка: в панели на десктопе, экран на телефоне; отметки км, «Скачать GPX», «Показать на карте», место под группу
- [ ] 2.6 Настройки профиля: «Назад», после сохранения — в профиль с подтверждением

## 3. Tests
- [ ] 3.1 Map Display: Close zoom, City-wide zoom, Attempts hidden, Not public tracks hidden, Initial area
- [ ] 3.2 Distance Filter: Category 5 km, Custom range; Other Filters: Pace range, Date range
- [ ] 3.3 Sorting: Sort by pace; Text Search: Search by author
- [ ] 3.4 Live Results: Pan map, Shareable state
- [ ] 3.5 Track Card: Download GPX, Kilometre marks, Show on map
- [ ] 3.6 Profile: Save settings, Leave settings
