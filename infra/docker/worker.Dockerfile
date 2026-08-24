FROM python:3.12.4-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend-requirements.txt
COPY requirements.txt /app/ocr-requirements.txt
COPY infra/docker/worker/requirements.txt /app/worker-requirements.txt
RUN pip install --no-cache-dir \
    -r /app/backend-requirements.txt \
    -r /app/worker-requirements.txt \
    -r /app/ocr-requirements.txt

COPY backend /app/backend
COPY ai /app/ai
COPY schemas /app/schemas

CMD ["celery", "-A", "backend.app.worker.celery_app:celery_app", "worker", "--loglevel=info"]
