FROM python:3.12-slim

WORKDIR /app

# Runtime needs: the mris package (incl. corpus rules/seed) + the premium UI.
COPY pyproject.toml ./
COPY mris ./mris
COPY frontend ./frontend
COPY api ./api

RUN pip install --no-cache-dir -e .

# Render (and any host) injects the listen port via $PORT; default 8000 for local runs.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn mris.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
