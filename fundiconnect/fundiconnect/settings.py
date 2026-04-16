# fundiconnect/settings.py

from pathlib import Path
import os
import json


def load_env_file(env_path):
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_env_file(BASE_DIR / '.env')


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-@d(6&x%m(69z#j77&7^r=z1d)k3613@%f!_s%g^!d1k6&!#v9b')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() in ['1', 'true', 'yes']

ALLOWED_HOSTS = [host.strip() for host in os.environ.get('ALLOWED_HOSTS', '*').split(',') if host.strip()]
SITE_URL = os.environ.get('SITE_URL', 'http://127.0.0.1:8000')

# Application definition
INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'rest_framework',
    'users.apps.UsersConfig',
    'jobs.apps.JobsConfig',
    'payments.apps.PaymentsConfig',
    'widget_tweaks',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
    'two_factor',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'users.middleware.VerificationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'two_factor.middleware.threadlocals.ThreadLocals',

]

ROOT_URLCONF = 'fundiconnect.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'users.context_processors.two_factor_status',
            ],
        },
    },
]

WSGI_APPLICATION = 'fundiconnect.wsgi.application'
ASGI_APPLICATION = 'fundiconnect.asgi.application'


# Database configuration - use DATABASE_URL if available, otherwise SQLite
if os.environ.get('DATABASE_URL'):
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.config(default=os.environ.get('DATABASE_URL'), conn_max_age=600)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Africa/Nairobi'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

STATICFILES_STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Media files (user-uploaded files)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'users.CustomUser'

LOGIN_URL = 'users:login'
LOGIN_REDIRECT_URL = 'users:profile'

OTP_TOTP_ISSUER = "FundiConnect"  # This will appear in authenticator apps

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

# Safaricom Daraja API settings
DARAJA_CONSUMER_KEY = os.environ.get('DARAJA_CONSUMER_KEY', '')
DARAJA_CONSUMER_SECRET = os.environ.get('DARAJA_CONSUMER_SECRET', '')
DARAJA_SHORTCODE = os.environ.get('DARAJA_SHORTCODE', '')

# Email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp-relay.brevo.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ['1', 'true', 'yes']
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'no-reply@fundiconnect.com')
EMAIL_SENDER_NAME = os.environ.get('EMAIL_SENDER_NAME', 'FundiConnect')
BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3-flash-preview')
FUNDICONNECT_ASSISTANT_GEMINI_MODEL = os.environ.get('FUNDICONNECT_ASSISTANT_GEMINI_MODEL', GEMINI_MODEL)

# Assistant defaults: system instruction and suggestion limits. Can be overridden via environment.
FUNDICONNECT_ASSISTANT_SYSTEM_INSTRUCTION = os.environ.get(
    'FUNDICONNECT_ASSISTANT_SYSTEM_INSTRUCTION',
    (
        "You are the FundiConnect AI Assistant for a Kenyan artisan marketplace. "
        "Use the supplied context (facts, snapshots, retrieval_text, and platform items) as ground truth. "
        "Always answer the user directly and succinctly first, then provide one concrete next step. "
        "Be role-aware, page-aware, privacy-preserving, and action-oriented. Never expose other users' private data. "
        "Return a strict JSON object with keys: text (string), suggestions (array of {label,url,icon,reason}), "
        "highlights (array of strings), and platform_items (array). "
        "Prefer 3-5 high-signal suggestions with a clear `reason` for each. If the reply ends with a next-step question (e.g., 'Would you like me to...?', 'Do you want to...?', or any trailing '?'), convert that into actionable suggestions. "
        "When drafting text (job posts, bids, messages), return ready-to-use drafts. Keep responses concise and avoid repeating role summaries unless explicitly requested."
    ),
)

# How many suggestions to emit at most (default 5). Can be set via env var.
FUNDICONNECT_ASSISTANT_SUGGESTION_MAX = int(os.environ.get('FUNDICONNECT_ASSISTANT_SUGGESTION_MAX', '5'))

# Default timeout (seconds) to use for Gemini REST and SDK calls when available.
FUNDICONNECT_ASSISTANT_GEMINI_TIMEOUT = int(os.environ.get('FUNDICONNECT_ASSISTANT_GEMINI_TIMEOUT', '60'))

# Optional: structured function definitions for assistant function-calling.
# Provide a JSON string in the env var FUNDICONNECT_ASSISTANT_FUNCTIONS or configure here.
try:
    _fn_raw = os.environ.get('FUNDICONNECT_ASSISTANT_FUNCTIONS') or getattr(settings if 'settings' in globals() else None, 'FUNDICONNECT_ASSISTANT_FUNCTIONS', None)
except Exception:
    _fn_raw = None

if _fn_raw:
    try:
        FUNDICONNECT_ASSISTANT_FUNCTIONS = json.loads(_fn_raw)
    except Exception:
        FUNDICONNECT_ASSISTANT_FUNCTIONS = []
else:
    FUNDICONNECT_ASSISTANT_FUNCTIONS = [
        {
            "name": "get_user_snapshot",
            "description": "Return a summary snapshot of the signed-in user (no arguments).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_platform_snapshot",
            "description": "Return high-level platform metrics and categories (no arguments).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "create_support_ticket",
            "description": "Create a lightweight support ticket in the platform. Returns ticket metadata.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short title for the ticket"},
                    "body": {"type": "string", "description": "Longer body or description"}
                },
                "required": ["title"]
            }
        }
    ]
