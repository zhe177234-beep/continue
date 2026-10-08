FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home appuser
COPY ai-service ./ai-service
COPY web ./web
RUN mkdir /app/data && chown appuser:appuser /app/data
USER appuser
EXPOSE 8000
CMD ["python", "ai-service/app.py"]
