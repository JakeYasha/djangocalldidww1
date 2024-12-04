#!/bin/bash

# Start PulseAudio
echo "Starting PulseAudio..."
mkdir -p /run/user/1000/pulse
pulseaudio --start --log-level=4 --verbose --exit-idle-time=-1 --disallow-exit &
sleep 2

# Create necessary directories
mkdir -p /home/appuser/app/recordings
mkdir -p /home/appuser/app/media

# Wait for database
echo "Waiting for database..."
while ! nc -z db 5432; do
  sleep 0.1
done

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

# Execute the passed command
exec "$@"
