"""
Development settings — verbose logging, relaxed security, no HTTPS requirement.
"""
from .base import *   # noqa: F401, F403 — intentional wildcard import for settings layering

DEBUG = True

# In dev, all hosts are fine — on prod this must be locked down
ALLOWED_HOSTS = ['*']

# Print emails to console instead of sending them — avoids needing SMTP locally
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Verbose SQL logging to help debug query performance during development
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',     # logs every SQL query — remove in prod
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
