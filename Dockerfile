# Production image for the Flask API.  The frontend is compiled into the
# Flask static directory so the runtime does not need Node or a Vite server.
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# curl is used only by the container healthcheck.  All document parsing and
# malware scanning happen in the application/clamd services, not in a shell.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . ./
COPY --from=frontend-build /src/app/static/frontend ./app/static/frontend

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin lianyipei \
    && mkdir -p /app/instance /app/uploads \
    && chown -R lianyipei:lianyipei /app
USER lianyipei

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"

CMD ["gunicorn", "wsgi:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
