## 1. Fixtures
- [x] 1.1 `tools/anonymize_gpx.py`: сдвиг долготы, срез 500 м с концов, без метаданных; обезличенные копии в `backend/tests/fixtures/tracks/`
- [x] 1.2 `tools/convert_track.py`: TCX и FIT из GPX для теста «три формата»

## 2. Domain (app/domain/tracks, без I/O)
- [x] 2.1 Парсеры GPX, TCX, FIT в единую модель точек (lat, lon, time, ele)
- [x] 2.2 Очистка выбросов, дистанция в локальной UTM-проекции
- [x] 2.3 Общее время, время движения, темп, сплиты по км, набор высоты
- [x] 2.4 Категория по границам из `settings`
- [x] 2.5 Проверки ФТ-7: нет времени, темп быстрее 2:30
- [x] 2.6 Скрытая зона: границы видимой части (начало и конец), видимая геометрия
- [x] 2.7 Рабочие геометрии: пересэмплинг с равным шагом (сопоставление), Дуглас—Пекер (карта)

## 3. Storage & processing
- [x] 3.1 Миграция: tracks (LINESTRINGZM, visible LINESTRINGM, границы, статусы, видимость), track_splits, track_photos, новые ключи `settings`
- [x] 3.2 `POST /tracks`: размер по потоку, формат по сигнатуре, SHA-256-дубликаты, лимит в час, файл в S3, задача
- [x] 3.3 Воркер `process_track`: разбор, проверки, метрики, видимая часть → draft или rejected
- [x] 3.4 `GET /tracks/{id}`: автору — всё, чужим — только видимая часть и только published public/link
- [x] 3.5 `PATCH /tracks/{id}` (публикация, название, описание, видимость), `DELETE /tracks/{id}`
- [x] 3.6 Фото: загрузка до 5, перекодирование без EXIF, удаление
- [x] 3.7 Пересчёт видимой части при изменении дома или радиуса
- [x] 3.8 `GET /me/tracks`, `GET /users/{id}/tracks`; статистика и рекорды в профиле

## 4. Frontend
- [x] 4.1 MapLibre + OpenFreeMap, компонент карты трека с затенённой зоной
- [x] 4.2 Экран загрузки по макету Processing: drag-and-drop, шаги, «можно закрыть»
- [x] 4.3 Превью по макету Preview: карта, показатели, график темпа (SVG), название, описание, фото, видимость, «Опубликовать»; место под плашку совпадения
- [x] 4.4 Экраны ошибок с причиной и «Загрузить другой файл»; «Этот трек уже есть» со ссылкой
- [x] 4.5 «Мои треки» в профиле со статусами; ленты и статистика в профилях
- [x] 4.6 Просмотр трека и отдельная форма с «Назад»; после публикации — на просмотр; значения на графике темпа

## 5. Tests
- [x] 5.1 Supported Files: Valid GPX, Same run in three formats, File too large, Unsupported format, Processing time
- [x] 5.2 Track Metrics: Category assigned, Stops excluded, Kilometre splits, GPS spike ignored, Working geometries
- [x] 5.3 Implausible: No timestamps, Too fast; Duplicate: Same file again
- [x] 5.4 Privacy zones: Start inside zone, Owner preview, No home set, Zone changed later, Track entirely inside zone
- [x] 5.5 Visibility: Publish public, Private, Link-only; Edit, Delete, Foreign track
- [x] 5.6 Photos: Sixth photo, Photo location stripped
- [x] 5.7 Profile: Guest sees only public tracks, Personal record; Delete account with tracks
- [x] 5.8 Upload Rate Limit: Limit exceeded
- [x] 5.9 Vitest: экран загрузки (шаги, ошибка с причиной), превью (публикация)
- [x] 5.10 Vitest: After publishing, Leave the form, Draft view, Pace values shown
