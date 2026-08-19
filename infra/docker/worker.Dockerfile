# Infra-owned Celery skeleton: proves the worker can reach Redis. No
# receipt-processing task is registered; that belongs to Backend-1/Backend-2.
FROM python:3.12.4-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY infra/docker/worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY infra/docker/worker/celery_app.py /app/celery_app.py

CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info"]
