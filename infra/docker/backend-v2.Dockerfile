FROM python:3.12-slim-bookworm AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

FROM base AS runtime
COPY backend /app/backend
COPY schemas /app/schemas
COPY ai /app/ai
COPY scripts/export_openapi_v2.py /app/scripts/export_openapi_v2.py
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS worker-deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-ocr-runtime.txt /app/requirements-ocr-runtime.txt
COPY backend/requirements-ai.txt /app/backend/requirements-ai.txt
RUN pip install --no-cache-dir -r backend/requirements-ai.txt && pip check

FROM worker-deps AS worker
COPY --from=runtime /app /app
ENV OMP_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false
CMD ["python", "-m", "celery", "-A", "backend.app.v2.worker:celery_app", "worker", "--loglevel=info", "--concurrency=1"]
