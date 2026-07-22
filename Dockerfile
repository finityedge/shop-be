# Matches the Python version used by the existing Azure build pipeline (3.12).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# postgresql-client provides pg_isready, used by the entrypoint to wait for the db.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first so code edits do not invalidate the pip layer.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh \
    && chmod +x /usr/local/bin/entrypoint.sh

# Non-root runtime user. staticfiles/ is created and owned here so the
# collectstatic run inside the entrypoint can write to it.
RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /app/staticfiles \
    && chown -R appuser:appuser /app

# A build-time collectstatic bakes assets into the image, so the container is
# already servable even if the entrypoint's run is skipped. Settings are read at
# import time, so a throwaway SECRET_KEY/DATABASE_URL keeps this from needing
# real credentials at build time.
USER appuser
RUN SECRET_KEY=build-only \
    DATABASE_URL=postgres://build:build@localhost:5432/build \
    python manage.py collectstatic --noinput

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["gunicorn", "core.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "60", \
     "--forwarded-allow-ips", "*", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
