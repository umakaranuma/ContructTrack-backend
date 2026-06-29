"""
Celery application configuration.
Background tasks: report generation, WhatsApp notifications, email digests.
"""
import os
from celery import Celery

# Default to development settings; production overrides via env var
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'constructtrack.settings.development')

app = Celery('constructtrack')

# Pull all CELERY_* settings from Django settings rather than a separate celery.conf
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in each installed app's tasks.py
app.autodiscover_tasks()
