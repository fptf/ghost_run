"""Requirement: Continuous Integration — сценарии Failing test и OpenAPI drift."""

from pathlib import Path

import yaml

from app.scripts.export_openapi import OPENAPI_PATH, render

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"

REQUIRED_COMMANDS = [
    "ruff check",
    "black --check",
    "mypy",
    "pytest",
    "npm run lint",
    "npm run format:check",
    "npm run typecheck",
    "npm run test",
    "git diff --exit-code",
]


def _run_steps() -> list[str]:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return [step["run"] for job in data["jobs"].values() for step in job["steps"] if "run" in step]


def test_workflow_runs_all_checks() -> None:
    runs = "\n".join(_run_steps())
    missing = [cmd for cmd in REQUIRED_COMMANDS if cmd not in runs]
    assert not missing, f"в CI нет проверок: {missing}"


def test_workflow_triggers_on_pull_request() -> None:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = data.get("on") or data.get(True)  # PyYAML читает `on` как True
    assert "pull_request" in triggers


def test_no_step_ignores_failures() -> None:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in data["jobs"].values():
        assert not job.get("continue-on-error")
        for step in job["steps"]:
            assert not step.get("continue-on-error"), step
            assert "|| true" not in step.get("run", ""), step


def test_openapi_json_is_up_to_date() -> None:
    assert (
        OPENAPI_PATH.read_text(encoding="utf-8") == render()
    ), "backend/openapi.json устарел: выполните `uv run python -m app.scripts.export_openapi`"
