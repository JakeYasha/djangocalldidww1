#!/bin/bash

echo "Starting PulseAudio..."
pulseaudio --start

if [ "$1" = "python" ] && [ "$2" = "simple_caller.py" ]; then
    exec "$@"
else
    echo "Waiting for database..."
    while ! nc -z db 5432; do
        sleep 0.1
    done
    echo "Database started"

    # Run database migrations
    echo "Running database migrations..."
    python manage.py migrate

    # Create default superuser if not exists
    echo "Creating default superuser..."
    python manage.py shell << END
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
END

    # Collect static files
    echo "Collecting static files..."
    python manage.py collectstatic --noinput

    exec "$@"
fi
