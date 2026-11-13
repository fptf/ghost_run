# Бегуны — стартовый пакет OpenSpec

Пакет для старта разработки AI-агентом (Claude Code) по спекам OpenSpec 2.x.

## Что внутри
- `docs/tz.md` — ТЗ
- `docs/design/` — макеты экранов (телефон и десктоп)
- `docs/project.md` — стек, архитектура, доменные термины, ограничения
- `openspec/config.yaml` — контекст и правила для OpenSpec
- `openspec/changes/` — 7 изменений MVP с предложениями, спеками и задачами

## Порядок изменений
1. add-bootstrap — каркас, Docker, PostGIS, очередь, CI
2. add-auth-profile — регистрация, вход, профиль, скрытая зона
3. add-track-upload — загрузка, разбор файлов, показатели, скрытые зоны
4. add-map-search — карта, фильтр дистанции, поиск, карточка трека
5. add-route-matching — автосопоставление, группы, проверка пробежки
6. add-achievements — «Превзошёл», экран результата, счётчик попыток
7. add-ratings — популярность и рейтинги по категориям

4 и 5 можно вести параллельно после 3. Для 5 заранее соберите 10–20 реальных GPX
(линейный, круговой, с разминкой, со срезкой, два круга, обратное направление)
в `backend/tests/fixtures/tracks/`.

## Как начать
```bash
mkdir runners && cd runners && git init
# распаковать сюда архив
npm install -g @fission-ai/openspec@latest
openspec init --tools claude      # добавит skills для Claude Code; config.yaml не перезапишет
openspec list                     # должно показать 7 изменений
```
Затем в Claude Code: «Реализуй изменение add-bootstrap» (или `/openspec-apply-change add-bootstrap`).
После завершения и проверки — архивировать изменение, его спеки переедут в `openspec/specs/`.
