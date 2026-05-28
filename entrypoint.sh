#!/bin/bash
set -e

echo "Running Django migrations..."
python manage.py migrate --noinput

echo "Starting Gunicorn server..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 2
