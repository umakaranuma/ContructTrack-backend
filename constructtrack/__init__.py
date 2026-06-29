# This file marks constructtrack as a Python package.
# Celery app is imported here so it initialises with Django.
from .celery import app as celery_app

__all__ = ('celery_app',)
