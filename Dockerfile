FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY app/ app/
RUN pip install --no-cache-dir . \
    && useradd --create-home --system app \
    && chown -R app:app /app

USER app
EXPOSE 8011
ENV ROUTER_PORT=8011
CMD ["python", "-m", "app.main"]
