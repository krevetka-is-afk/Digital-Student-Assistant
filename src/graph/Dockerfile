FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.127.1 \
    uvicorn==0.38.0 \
    pydantic \
    "neo4j>=5.28.2" \
    "httpx>=0.28.1"

COPY . .

EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
