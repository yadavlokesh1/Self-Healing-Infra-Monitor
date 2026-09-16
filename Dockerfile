FROM python:3.12-slim AS base

WORKDIR /app

# Install deps first (layer caching)
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user
RUN useradd -m appuser
COPY app/ .
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

# Docker-level healthcheck (independent of K8s probes — useful for plain `docker run`)
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:5000/health', timeout=2)" || exit 1

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]
