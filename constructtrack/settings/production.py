"""
Production settings — strict security, no debug output, HTTPS enforcement.
"""
from .base import *   # noqa: F401, F403
from decouple import config

DEBUG = False

# Must explicitly list the domains serving this app
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='constructtrack.lk,www.constructtrack.lk').split(',')

# HTTPS hardening
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Restrict CORS to known frontend origins in prod
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='https://app.constructtrack.lk,https://admin.constructtrack.lk'
).split(',')

# Production logging — write to file / structured output for log aggregator
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
