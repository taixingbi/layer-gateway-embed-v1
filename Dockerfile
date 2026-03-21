FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY router_embed/ router_embed/
RUN pip install --no-cache-dir .

EXPOSE 8011
ENV ROUTER_PORT=8011
CMD ["python", "-m", "router_embed.server"]
