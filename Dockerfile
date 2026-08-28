FROM ghcr.io/astral-sh/uv:0.12.1 AS uv

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/app/.venv/bin:$PATH \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    XDG_RUNTIME_DIR=/tmp/interviewer-runtime \
    PULSE_SERVER=unix:/tmp/interviewer-runtime/pulse/native \
    DISPLAY=:99

COPY --from=uv /uv /uvx /bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg pulseaudio pulseaudio-utils \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 interviewer \
    && mkdir -p /app /app/data /tmp/interviewer-runtime /tmp/.X11-unix \
    && chown -R interviewer:interviewer /app /tmp/interviewer-runtime \
    && chmod 700 /tmp/interviewer-runtime \
    && chmod 1777 /tmp/.X11-unix

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen --no-install-project --no-dev \
    && .venv/bin/playwright install --with-deps chromium \
    && chmod -R a+rX /ms-playwright

COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations

RUN uv sync --frozen --no-dev

COPY --chown=interviewer:interviewer docker/entrypoint.sh /usr/local/bin/interviewer-entrypoint

USER interviewer

EXPOSE 8000
VOLUME ["/app/data"]

ENTRYPOINT ["interviewer-entrypoint"]
CMD ["voice-interviewer", "serve"]
