"""
Items app configuration.
Yeh file items app ki configuration settings rakhti hai.
"""

from django.apps import AppConfig


class ItemsConfig(AppConfig):
    """
    Items app ki configuration class.
    Django ko app ke baare mein batati hai.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'items'
    verbose_name = 'Lost & Found Items'  # Admin panel mein dikhne wala naam
