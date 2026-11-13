"""Экспорт схемы OpenAPI: `python -m app.scripts.export_openapi [путь]`."""

import json
import sys
from pathlib import Path

from app.main import app

OPENAPI_PATH = Path(__file__).resolve().parents[2] / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else OPENAPI_PATH
    target.write_text(render(), encoding="utf-8")


if __name__ == "__main__":
    main()
