FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY mris ./mris
RUN pip install --no-cache-dir -e .

EXPOSE 8000
CMD ["uvicorn", "mris.api:app", "--host", "0.0.0.0", "--port", "8000"]
