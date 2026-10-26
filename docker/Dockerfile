FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf \
    EMBEDDINGS_PROVIDER=huggingface

WORKDIR /app

# libgomp1: OpenMP runtime needed by xgboost/torch. curl: container health check.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-deploy.txt .
RUN pip install -r requirements-deploy.txt

# Bake the embedding model into the image so containers never download it at startup.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy only what the service needs (no .env, venv, notebooks, data or frontend).
COPY api ./api
COPY agent ./agent
COPY rag ./rag
COPY policies ./policies
COPY artifacts ./artifacts

RUN useradd --create-home app && chown -R app:app /app /opt/hf
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD curl -fsS http://localhost:8000/agent/health || exit 1

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
