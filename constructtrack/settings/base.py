"""
Base settings shared across all environments.
Environment-specific files (development.py, production.py) import and extend this.
"""
from pathlib import Path
from decouple import config
from datetime import timedelta

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECRET_KEY = config('SECRET_KEY', default='insecure-default-change-in-prod')

ALLOWED_HOSTS = ['*']  # Tightened per-environment in development/production files

# ---------------------------------------------------------------------------
# Application definition
# We deliberately exclude django.contrib.auth and django.contrib.admin:
#   - auth  creates auth_user, auth_group, auth_permission, etc. — replaced by accounts.User
#   - admin creates django_admin_log — not needed; we have a custom admin API
# django.contrib.contenttypes is kept because DRF's generic relations need it.
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    # django.contrib.auth is required so that simplejwt, DRF, and password validators
    # can import from it — but we set MIGRATION_MODULES['auth'] = None below so no
    # auth_* tables are ever created. Our own accounts.User replaces auth.User.
    'django.contrib.auth',
    'django.contrib.contenttypes',   # required by DRF browsable API + generic FK support
    'rest_framework',
    'rest_framework_simplejwt',
    # token_blacklist excluded — it creates token_blacklist_* tables we don't need.
    # Logout is handled client-side by discarding the JWT.
    'corsheaders',
    'apps.accounts',
    'apps.tenants',
    'apps.sites',
    'apps.bills',
    'apps.attendance',
    'apps.progress',
    'apps.reports',
    'apps.payments',
    'apps.core',
    'apps.contracts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',           # must be before CommonMiddleware
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'constructtrack.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
            ],
        },
    },
]

WSGI_APPLICATION = 'constructtrack.wsgi.application'
ASGI_APPLICATION = 'constructtrack.asgi.application'

# ---------------------------------------------------------------------------
# Database — MySQL via mysqlclient
# ---------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'builder',
        'USER': 'root',
        'PASSWORD': 'umasiva1126@',   # stored in .env; decouple injects it
        'HOST': '127.0.0.1',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',     # full Unicode incl. emoji in site names
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# ---------------------------------------------------------------------------
# Disable migrations for built-in Django apps so they don't create default
# tables we explicitly don't want (auth_*, django_content_type, etc.)
# Setting a module to None tells Django: "skip migrations for this app".
# ---------------------------------------------------------------------------
MIGRATION_MODULES = {
    'contenttypes': None,   # skip django_content_type table creation
    'auth': None,           # skip auth_user / auth_group / auth_permission tables
}

# ---------------------------------------------------------------------------
# Custom user model — replaces Django's built-in auth.User
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = 'accounts.User'

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Colombo'   # Sri Lanka Standard Time (UTC+5:30)
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static / media files
# ---------------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/min',
        'user': '120/min',
        'auth': '5/min',    # stricter for login/register
    },
    'EXCEPTION_HANDLER': 'apps.core.utils.custom_exception_handler',
}

# ---------------------------------------------------------------------------
# JWT — short-lived access tokens; refresh tokens blacklisted on logout
# ---------------------------------------------------------------------------
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,   # blacklist app not installed; logout is client-side
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# ---------------------------------------------------------------------------
# CORS — allow all origins in base; restrict in production.py
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://127.0.0.1:6379/1')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Colombo'

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@constructtrack.lk')

# ---------------------------------------------------------------------------
# Third-party integrations
# ---------------------------------------------------------------------------
META_WHATSAPP_API_TOKEN = config('META_WHATSAPP_API_TOKEN', default='')
META_PHONE_NUMBER_ID = config('META_PHONE_NUMBER_ID', default='')
META_WABA_ID = config('META_WABA_ID', default='')

DIALOG_SMS_API_KEY = config('DIALOG_SMS_API_KEY', default='')
DIALOG_SMS_API_URL = config('DIALOG_SMS_API_URL', default='https://sms.dialog.lk/api/v2/send')

SUPABASE_URL = config('SUPABASE_URL', default='')
SUPABASE_SERVICE_KEY = config('SUPABASE_SERVICE_KEY', default='')
SUPABASE_BUCKET_NAME = config('SUPABASE_BUCKET_NAME', default='constructtrack-media')

LKR_USD_RATE = config('LKR_USD_RATE', default=310, cast=float)

# Fernet key for encrypting sensitive stored data (e.g. bank account numbers)
FERNET_KEY = config('FERNET_KEY', default='')

DEVELOPER_EMAIL = config('DEVELOPER_EMAIL', default='dev@constructtrack.lk')
