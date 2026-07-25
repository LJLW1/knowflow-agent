FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    HF_HOME=/app/model-cache \
    PATH="/app/.venv/bin:${PATH}"

RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system knowflow && useradd --system --gid knowflow --create-home knowflow

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.9.28 /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev --extra embedding
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5', cache_folder='/app/model-cache')"

ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

COPY app ./app
COPY prompts ./prompts
COPY alembic ./alembic
COPY alembic.ini ./

RUN mkdir -p /app/data/runtime /app/data/chroma /app/data/uploads /app/reports/runtime \
    && chown -R knowflow:knowflow /app

USER knowflow
EXPOSE 8000
CMD ["knowflow-api"]
