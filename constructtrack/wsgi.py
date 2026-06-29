"""
WSGI config for ConstructTrack.
Exposes the WSGI callable as a module-level variable named ``application``.
Used by gunicorn in production: gunicorn constructtrack.wsgi:application
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'constructtrack.settings.production')
application = get_wsgi_application()
