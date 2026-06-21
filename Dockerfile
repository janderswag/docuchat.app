# M2-9 — lean runtime image for the FastAPI pipeline service (D-20, D-41).
# Serving path only: retrieve (LanceDB + Ollama embed over loopback) -> answer
# (Ollama chat) -> verify. NO ingestion deps (docling/pymupdf) and NO Torch/reranker
# (D-36 OFF + lazy-imported), so the image stays small. Base pinned by digest.
#
# Loopback invariant: uvicorn binds 0.0.0.0 INSIDE the container's isolated network
# namespace ONLY; the host publishes this port to 127.0.0.1:8000 (docker-compose.yml),
# so the service is never reachable off the host loopback. Host Ollama is reached via
# host.docker.internal (its bind stays 127.0.0.1; OLLAMA_HOST stays unset).
FROM python:3.12-slim-bookworm@sha256:76d4b7b6305788c6b4c6a19d6a22a3921bf802e9af4d5e1e5bd771208dba74bf

WORKDIR /app

# Install only the pinned serving deps (NOT requirements.txt — that pulls docling/Torch).
COPY pipeline/requirements-serve.txt ./requirements-serve.txt
RUN pip install --no-cache-dir -r requirements-serve.txt

# Copy the Python sources only. The LanceDB store, document bodies, .env, venv and
# caches are NEVER copied (mounted at runtime / excluded by .dockerignore, D-28/#7).
COPY pipeline/*.py ./

EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
