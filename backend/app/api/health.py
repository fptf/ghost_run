from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from app.config import Config, get_config
from app.infra.health import run_checks

router = APIRouter(tags=["system"])

CheckStatus = Literal["ok", "error"]


class HealthChecks(BaseModel):
    db: CheckStatus
    redis: CheckStatus
    s3: CheckStatus


class HealthResponse(BaseModel):
    status: CheckStatus
    checks: HealthChecks


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Зависимость недоступна"}},
)
def health(response: Response, cfg: Annotated[Config, Depends(get_config)]) -> HealthResponse:
    checks = run_checks(cfg)
    ok = all(v == "ok" for v in checks.values())
    if not ok:
        response.status_code = 503
    return HealthResponse(
        status="ok" if ok else "error", checks=HealthChecks.model_validate(checks)
    )
