"""
ASGI config for phone_tracker project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'phone_tracker.settings')

application = get_asgi_application()
