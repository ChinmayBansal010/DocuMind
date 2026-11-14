FROM node:22-alpine AS frontend-build
WORKDIR /web
ARG VITE_NEON_AUTH_URL=
ARG NEON_AUTH_BASE_URL=
ENV VITE_NEON_AUTH_URL=${VITE_NEON_AUTH_URL}
ENV NEON_AUTH_BASE_URL=${NEON_AUTH_BASE_URL}
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr libreoffice-writer && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=frontend-build /web/dist /app/frontend/dist
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["sh", "-c", "python -c 'from app.core.config import settings; settings.validate_azure_configuration()' && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
