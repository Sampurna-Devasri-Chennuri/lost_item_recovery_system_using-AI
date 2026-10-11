"""
ASGI config for campusLostAndFound project.
Yeh file async server ke liye ASGI configuration hai.
"""

import os

from django.core.asgi import get_asgi_application

# Django settings module set kar rahe hain
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'campusLostAndFound.settings')

# ASGI application object
application = get_asgi_application()
