"""
ASGI config for ConstructTrack.
Enables async support — required if we add Django Channels for real-time
site alerts or WhatsApp webhooks in the future.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'constructtrack.settings.production')
application = get_asgi_application()
