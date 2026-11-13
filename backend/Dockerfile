FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.8 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_HTTP_TIMEOUT=120 \
    PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python -m app.scripts.init_storage && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
