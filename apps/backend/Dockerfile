# syntax=docker/dockerfile:1
# 타깃
#   dev  : 개발용. dev 의존성 포함, docker-compose.yml이 소스를 마운트하고 --reload로 실행
#   prod : 운영용. 런타임 의존성만, 소스를 이미지에 포함
# 같은 이미지로 API / 워커 / 스케줄러를 실행한다 (command만 다름)

FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
# 가상환경은 /app 밖(/opt/venv)에 둔다. docker compose가 apps/backend 디렉터리 전체를 /app에
# 마운트해도 이미지의 가상환경이 가려지지 않는다.

COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /usr/local/bin/uv

WORKDIR /app

# ----------------------------------------------
FROM base AS dev

# 의존성 레이어 (pyproject.toml / uv.lock이 바뀔 때만 다시 설치)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

COPY src ./src
COPY tests ./tests
COPY migrations ./migrations
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "src"]

# ----------------------------------------------
FROM base AS prod

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY migrations ./migrations
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
