# syntax=docker/dockerfile:1
FROM python:3.13-slim AS builder

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY uv.lock pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev &&\
    uv run python generate_protobuf.py &&\
    mkdir -p /app/cache


# ==================== 最终镜像 ====================
FROM python:3.13-slim

COPY --from=builder /app /app

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=0 \
    PYTHONUNBUFFERED=1

# 使用 uv 启动（推荐）
ENTRYPOINT ["python"]
CMD ["main.py"]