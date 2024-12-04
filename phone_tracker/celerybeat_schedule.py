from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    'check-new-recordings': {
        'task': 'phone_numbers.tasks.check_recordings',
        'schedule': crontab(minute='*/2'),  # Каждые 2 минуты
    },
    'schedule-recall': {
        'task': 'phone_numbers.tasks.schedule_recall',
        'schedule': crontab(hour='*/24'),  # Каждые 24 часа
    },
}
