"""
Django settings for the CSE MCQ Portal.
All deployment-specific values come from environment variables (see
``.env.example``). For local development a ``.env`` file in the project root is
loaded automatically; real environment variables always take precedence.
"""
import os
import sys
from pathlib import Path
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be an integer, got {value!r}") from exc

def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]

DEBUG = env_bool("DJANGO_DEBUG", False)
_PLACEHOLDER_KEYS = ("change-me", "django-insecure", "your-secret", "replace-me")
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "").strip()
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-never-use-in-production-" + "x" * 20
    else:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is not set. Generate one with:\n"
            "  python -c \"from django.core.management.utils import "
            "get_random_secret_key as g; print(g())\""
        )
elif not DEBUG and (
    SECRET_KEY.lower().startswith(_PLACEHOLDER_KEYS) or len(SECRET_KEY) < 32
):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY looks like a placeholder or is too short (< 32 chars). "
        "Generate a real one before running with DJANGO_DEBUG=False."
    )

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

for _host in (
    os.environ.get("RENDER_EXTERNAL_HOSTNAME"),
    os.environ.get("RAILWAY_PUBLIC_DOMAIN"),
):
    if _host:
        if _host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_host)
        _origin = f"https://{_host}"
        if _origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_origin)

if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS is empty. Set it to your domain, e.g. "
        "DJANGO_ALLOWED_HOSTS=quiz.example.com"
    )

USE_HTTPS = env_bool("DJANGO_USE_HTTPS", not DEBUG)
if USE_HTTPS:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int("DJANGO_HSTS_SECONDS", 60 * 60 * 24 * 30)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_HSTS_INCLUDE_SUBDOMAINS", False)
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_HSTS_PRELOAD", False)

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

TRUSTED_PROXY_COUNT = env_int("TRUSTED_PROXY_COUNT", 0)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "accounts",
    "mcq_app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "mcq_quiz.middleware.ContentSecurityPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "mcq_quiz.urls"
WSGI_APPLICATION = "mcq_quiz.wsgi.application"
ASGI_APPLICATION = "mcq_quiz.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "mcq_app:home"
LOGOUT_REDIRECT_URL = "mcq_app:home"

LOGIN_MAX_FAILURES = env_int("LOGIN_MAX_FAILURES", 5)
LOGIN_LOCKOUT_SECONDS = env_int("LOGIN_LOCKOUT_SECONDS", 15 * 60)
PASSWORD_RESET_MAX_REQUESTS = env_int("PASSWORD_RESET_MAX_REQUESTS", 5) 

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if (DEBUG or TESTING)
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = env_int("EMAIL_PORT", 587)
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_TIMEOUT = 15
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "CSE MCQ Portal <no-reply@localhost>")

from django.contrib.messages import constants as message_constants 
MESSAGE_TAGS = {
    message_constants.DEBUG: "info",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "error",
}

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest").strip()
GEMINI_TIMEOUT_SECONDS = env_int("GEMINI_TIMEOUT_SECONDS", 60)

QUIZ_QUESTION_COUNT = env_int("QUIZ_QUESTION_COUNT", 15)
QUIZ_TIME_LIMIT_SECONDS = env_int("QUIZ_TIME_LIMIT_SECONDS", 15 * 60)

QUIZ_GENERATE_LIMIT = env_int("QUIZ_GENERATE_LIMIT", 10)
QUIZ_GENERATE_WINDOW_SECONDS = env_int("QUIZ_GENERATE_WINDOW_SECONDS", 60 * 60)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}