# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PDM_CHECK_UPDATE=false \
    PDM_USE_VENV=true

RUN pip install --no-cache-dir --root-user-action=ignore pdm

WORKDIR /app

COPY pyproject.toml pdm.lock README.md ./
COPY src ./src
COPY tests ./tests
COPY config ./config

RUN pdm install --frozen

# Default: run the app; override in compose for tests.
CMD ["pdm", "run", "python", "-m", "veridoc"]
