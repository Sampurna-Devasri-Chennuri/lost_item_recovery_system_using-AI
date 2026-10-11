#!/usr/bin/env python
"""
Django's command-line utility for administrative tasks.
Yeh file Django project ke management commands run karne ke liye hai.
"""
import os
import sys


def main():
    """
    Main function jo Django management commands ko run karti hai.
    Yeh function django-admin ya manage.py se commands execute karti hai.
    """
    # Django settings module environment variable set karna
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'campusLostAndFound.settings')
    
    try:
        # Django command line utility import karna
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        # Agar Django install nahi hai to error message
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    
    # Command line arguments se command execute karna
    execute_from_command_line(sys.argv)


# Script directly run hone par main function call karna
if __name__ == '__main__':
    main()
