FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl ffmpeg gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for Tailwind build with retries
RUN for i in 1 2 3; do \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/* && break || \
    ([ $i -lt 3 ] && echo "Retry $i failed, trying again..." && sleep 5); \
done

COPY requirements.txt .
RUN for i in 1 2 3; do \
    pip install --no-cache-dir -r requirements.txt && break || \
    ([ $i -lt 3 ] && echo "pip install attempt $i failed, retrying..." && sleep 5); \
done

COPY . .

# Build Tailwind CSS
RUN cd theme/static_src && \
    for i in 1 2 3; do \
    npm ci && break || \
    ([ $i -lt 3 ] && echo "npm ci attempt $i failed, retrying..." && sleep 5); \
done && \
    npm run build

# Collect static files
RUN DJANGO_SETTINGS_MODULE=config.settings.production \
    SECRET_KEY=build-placeholder \
    DATABASE_URL=sqlite:///tmp/build.db \
    python manage.py collectstatic --noinput

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

CMD /app/entrypoint.sh
