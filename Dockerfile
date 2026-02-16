FROM python:3.14-slim AS build
WORKDIR /build

# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc && \
    rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --no-cache-dir uv==0.9.22

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-install-project

COPY . .

FROM python:3.14-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

ARG APP_UID=1000
ARG APP_GID=1000
RUN addgroup --gid ${APP_GID} appgroup && \
    adduser --disabled-password --gecos '' --uid ${APP_UID} --gid ${APP_GID} --home /app \
      --shell /usr/sbin/nologin appuser && \
    mkdir -p /app/data && chown -R appuser:appgroup /app/data /app

WORKDIR /app

COPY --from=build --chown=appuser:appgroup /opt/venv /opt/venv

COPY --from=build --chown=appuser:appgroup /build .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import sys,urllib.request as u; u.urlopen('http://127.0.0.1:8000/health').read(); sys.exit(0)" || exit 1

USER appuser

CMD ["uvicorn", "services.ml.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
