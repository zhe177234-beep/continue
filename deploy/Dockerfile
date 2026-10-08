FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-chi-sim && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home appuser
COPY ai-service ./ai-service
RUN mkdir /app/data && chown appuser:appuser /app/data
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "api:app", "--app-dir", "ai-service", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--limit-concurrency", "32"]
