# syntax=docker/dockerfile:1

# ---- Tahap 1: membangun CSS Tailwind (CLI mandiri, tanpa Node.js) ----
FROM debian:bookworm-slim AS css
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY scripts/get_tailwind.sh scripts/get_tailwind.sh
RUN bash scripts/get_tailwind.sh
COPY static/css/input.css static/css/input.css
COPY templates templates
COPY apps apps
RUN ./bin/tailwindcss -i static/css/input.css -o static/css/app.css --minify

# ---- Tahap 2: memasang dependensi Python (hanya yang dibutuhkan produksi) ----
FROM python:3.12-slim AS builder
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PIP_NO_CACHE_DIR=1
RUN pip install uv
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# ---- Tahap 3: image akhir ----
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    WEB_CONCURRENCY=3
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app . .
COPY --from=css --chown=app:app /src/static/css/app.css static/css/app.css
RUN chmod +x docker/entrypoint.sh \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R app:app /app/media /app/staticfiles
USER app

# collectstatic hanya membaca konfigurasi; nilai di bawah khusus tahap build (tidak dipakai saat berjalan).
RUN SECRET_KEY=build-only DEBUG=False DATABASE_URL=sqlite:////tmp/build.sqlite3 \
    python manage.py collectstatic --noinput

EXPOSE 8000
ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--worker-tmp-dir", "/dev/shm", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
