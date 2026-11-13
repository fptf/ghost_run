import logging

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.tracks import router as tracks_router
from app.api.users import router as users_router
from app.config import get_config
from app.middleware import UPLOAD_BODY_LIMIT, BodySizeLimit


def create_app() -> FastAPI:
    app = FastAPI(title="Бегуны API", version="0.1.0")
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(tracks_router)
    app.add_middleware(BodySizeLimit, max_bytes=UPLOAD_BODY_LIMIT)
    if get_config().auth_dev_login:
        logging.getLogger(__name__).warning("AUTH_DEV_LOGIN включён — не используйте в проде")
    return app


app = create_app()
