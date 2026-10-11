"""
WSGI config for campusLostAndFound project.
Yeh file production server ke liye WSGI configuration hai.
"""

import os

from django.core.wsgi import get_wsgi_application

# Django settings module set kar rahe hain
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'campusLostAndFound.settings')

# WSGI application object
application = get_wsgi_application()
