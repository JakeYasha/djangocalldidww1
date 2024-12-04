import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-your-secret-key-here'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_celery_beat',
    'phone_numbers',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'phone_tracker.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'phone_tracker.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'phone_tracker'),
        'USER': os.getenv('POSTGRES_USER', 'phone_tracker'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'phone_tracker_pass'),
        'HOST': os.getenv('POSTGRES_HOST', 'db'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
    }
}

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Riga'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files (Recordings)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, '')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Celery Configuration
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Summary Prompt Configuration
SUMMARY_PROMPT = """You are a helper who creates short descriptions of phone menu navigation.

Task: Provide a highly detailed list of all possible and available keystroke sequences and their results, including single key presses, sequences of key presses (e.g., '1-2-3'), and language selection presses. If there are no keys to press, provide voice commands that achieve the desired result. Use the context from the filenames to determine the company name or service.

Instructions:
- Format: For each item, use one of the following formats:
  - For key presses:
    - 'Call [Company Name or Service] [phone number, if available], press [sequence of numbers] to [end result].'
  - For voice commands:
    - 'Call [Company Name or Service] [phone number, if available], say "[voice command]" to [end result].'
- Requirements:
  - Include both single keystroke options and the sequences that follow them.
  - Include all possible paths, even if they lead to the same result.
  - Do not add any additional comments or explanations.
  - Use the filenames indicated in the format '=== File: filename ===' to determine the context and company name.
  - Your answer must be IN ENGLISH.

Examples of correct answers (from other texts, please do the same):

[START EXAMPLE]
- Call Apple Support, press 1 to resolve billing issues related to charges on your account.
- Call 1-800-433-7300, press 1-2-1-1 to book a new reservation using miles for 1 passenger.
[END EXAMPLE]"""

# Recording settings
RECORDINGS_DIR = os.path.join(BASE_DIR, 'recordings')
