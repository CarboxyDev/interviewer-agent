FROM ghcr.io/astral-sh/uv:0.12.1 AS uv

FROM python:3.12-slim-bookworm

ARG TARGETARCH
ARG CHROME_VERSION=152.0.7977.64-1
ARG CHROME_SHA256_AMD64=4eae0736a812d9bc851cd2937f7af00e47dbaf8305845eed452703ff009873c7
ARG CHROME_SHA256_ARM64=6ccab79a7afe1d174c89e28cf0d5a265e6e8855ff3b45c6a2151a65d7ddae9e8

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
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        ffmpeg \
        novnc \
        pulseaudio \
        pulseaudio-utils \
        websockify \
        x11vnc \
        xvfb \
    && curl -fsSLo /tmp/google-chrome.deb \
        "https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_${CHROME_VERSION}_${TARGETARCH}.deb" \
    && if [ "$TARGETARCH" = "amd64" ]; then CHROME_SHA256="$CHROME_SHA256_AMD64"; \
       elif [ "$TARGETARCH" = "arm64" ]; then CHROME_SHA256="$CHROME_SHA256_ARM64"; \
       else echo "Unsupported architecture: $TARGETARCH" >&2; exit 1; fi \
    && echo "$CHROME_SHA256  /tmp/google-chrome.deb" | sha256sum -c - \
    && apt-get install -y --no-install-recommends /tmp/google-chrome.deb \
    && google-chrome --version \
    && rm -f /tmp/google-chrome.deb \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 interviewer \
    && mkdir -p /app /app/data /tmp/interviewer-runtime /tmp/.X11-unix \
    && chown -R interviewer:interviewer /app /tmp/interviewer-runtime \
    && chmod 700 /tmp/interviewer-runtime \
    && chmod 1777 /tmp/.X11-unix

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen --no-install-project --no-dev

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
