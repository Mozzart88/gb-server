FROM python:3.13-slim
ARG UID=1000
ARG GID=1002

RUN groupadd -g $GID appgroup && \
    useradd -u $UID -g $GID -m appuser

WORKDIR /app

# Install system dependencies if any are needed (e.g., for sqlite or others)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     ... && \
#     rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY data/ ./data/
# Note: In production, you might want to mount data/ as a volume instead of copying
# but for the first run or default state, copying is fine.

# Ensure data directory exists and is writable
RUN mkdir -p /app/data && chmod -R 777 /app && chown appuser:appgroup /app
USER appuser

ENV PYTHONPATH=/app
EXPOSE 3000

CMD ["python", "src/main.py"]
