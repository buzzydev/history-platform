FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 APP_ENV=production

# OCR engine (Uzbek Latin + Cyrillic + Russian + English) and a Unicode font for PDF exports
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus tesseract-ocr-uzb tesseract-ocr-uzb-cyrl \
        fonts-dejavu-core libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# ONE gunicorn worker with threads: the built-in backup scheduler thread must run exactly once.
CMD ["sh", "-c", "gunicorn wsgi:app --workers 1 --threads 8 --timeout 180 --bind 0.0.0.0:${PORT:-8080} --access-logfile - --error-logfile - --capture-output --log-level info"]
