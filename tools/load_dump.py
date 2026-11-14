"""Загрузка тестового дампа в работающий стек через API (нужен AUTH_DEV_LOGIN=true).

    cd backend && uv run python ../tools/load_dump.py ../tracks-dump [--reset] [http://localhost:8000]

Для каждого бегуна из manifest.json: dev-вход, город, точка дома и радиус скрытой зоны;
затем загрузка треков в порядке манифеста, ожидание обработки и публикация. Необязательные
поля трека: visibility (по умолчанию public), detach («Не засчитывать»), root (автор маршрута).
Необязательное поле downloads — {серия: [бегуны]}: скачивания GPX маршрута для рейтинга.
Повторный запуск безопасен: уже загруженные файлы распознаются как дубликаты и пропускаются.
--reset сначала удаляет аккаунты бегунов дампа со всеми их треками — после перегенерации дампа.
"""

import json
import sys
import time
from pathlib import Path

import httpx


def login(client: httpx.Client, email: str, name: str) -> dict[str, str]:
    """Dev-вход; при лимите попыток входа (10 в минуту с IP) ждём и повторяем."""
    for _ in range(5):
        resp = client.post("/auth/dev-login", json={"email": email, "name": name})
        if resp.status_code != 429:
            resp.raise_for_status()
            return {"Authorization": f"Bearer {resp.json()['access_token']}"}
        print("  лимит попыток входа — ждём минуту…")
        time.sleep(61)
    sys.exit("Не удалось войти: лимит попыток входа")


def main(dump: Path, api: str, reset: bool) -> None:
    manifest = json.loads((dump / "manifest.json").read_text())
    client = httpx.Client(base_url=api, timeout=60)
    if reset:
        for r in manifest["runners"].values():
            client.delete("/me", headers=login(client, r["email"], r["name"])).raise_for_status()
        print(f"Удалены аккаунты бегунов дампа: {len(manifest['runners'])}")
    headers: dict[str, dict[str, str]] = {}
    for slug, r in manifest["runners"].items():
        h = login(client, r["email"], r["name"])
        profile = {"city": r["city"]}
        if "home" in r:  # скрытая зона у дома — необязательна
            profile |= {"home": r["home"], "hide_radius_m": r["hide_radius_m"]}
        client.patch("/me", headers=h, json=profile).raise_for_status()
        headers[slug] = h

    done = skipped = failed = 0
    roots: dict[str, str] = {}
    for t in manifest["tracks"]:
        h = headers[t["runner"]]
        path = dump / t["file"]
        resp = client.post("/tracks", headers=h, files={"file": (path.name, path.read_bytes())})
        if resp.status_code == 409:
            skipped += 1
            continue
        if resp.status_code == 429:
            sys.exit(f"Лимит загрузок в час: {resp.json()['detail']}. Повторите позже.")
        resp.raise_for_status()
        track_id = resp.json()["id"]
        status = "processing"
        for _ in range(60):
            status = client.get(f"/tracks/{track_id}", headers=h).json()["status"]
            if status != "processing":
                break
            time.sleep(0.5)
        if status != "draft":
            failed += 1
            print(f"  {t['file']}: {status}")
            continue
        body = {"title": t["title"], "visibility": t.get("visibility", "public"), "publish": True}
        published = client.patch(f"/tracks/{track_id}", headers=h, json=body)
        published.raise_for_status()
        if t.get("detach"):
            client.patch(
                f"/tracks/{track_id}", headers=h, json={"detach": True}
            ).raise_for_status()
        if t.get("root"):
            roots.setdefault(t["series"], track_id)
        attempt_of = (published.json().get("attempt_of") or {}).get("title")
        done += 1
        print(f"  {t['file']} -> {t['title']}" + (f" (попытка: {attempt_of})" if attempt_of else ""))

    for series, slugs in manifest.get("downloads", {}).items():
        if series in roots:
            for slug in slugs:
                client.get(f"/tracks/{roots[series]}/gpx", headers=headers[slug]).raise_for_status()
    print(f"Загружено {done}, уже были {skipped}, не обработано {failed}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--reset"]
    if len(args) not in (1, 2):
        sys.exit(__doc__)
    main(Path(args[0]), args[1] if len(args) == 2 else "http://localhost:8000", "--reset" in sys.argv)
