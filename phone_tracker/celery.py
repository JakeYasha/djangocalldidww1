import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'phone_tracker.settings')

app = Celery('phone_tracker')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Периодические задачи
app.conf.beat_schedule = {
    'process-unprocessed-recordings': {
        'task': 'phone_numbers.tasks.process_unprocessed_recordings',
        'schedule': crontab(minute='*/5'),  # Каждые 5 минут
    },
    'schedule-recall': {
        'task': 'phone_numbers.tasks.schedule_recall',
        'schedule': crontab(minute='*/30'),  # Каждые 30 минут
    },
}
