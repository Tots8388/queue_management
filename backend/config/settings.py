"""
Django settings for the Digital Queue & Patient-Flow Management System.

Behaviour is specified in ../../spec.md. Configuration is entirely
environment-driven: no secret, credential or host-specific value is written in
this file. Variable names are documented in ../../.env.example.
"""

import logging
import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent

# Load the repo-root .env if present. Real environment variables always win, so
# the LAN deployment can set values in the machine's environment instead.
load_dotenv(REPO_ROOT / ".env", override=False)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    value = os.environ.get(name, "")
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or (default or [])


DJANGO_ENV = os.environ.get("DJANGO_ENV", "development").strip().lower()
IS_PRODUCTION = DJANGO_ENV == "production"
# Test runs must never be blocked by missing deployment configuration.
RUNNING_TESTS = "test" in sys.argv or os.environ.get("PYTEST_VERSION") is not None

DEBUG = not IS_PRODUCTION

# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise RuntimeError(
            "DJANGO_SECRET_KEY is required when DJANGO_ENV=production. "
            "Set it in the machine's environment or .env — never in the repo."
        )
    # Development only: an unmistakably non-production placeholder.
    SECRET_KEY = "django-insecure-development-only-do-not-use-in-production"

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    if IS_PRODUCTION:
        raise RuntimeError(
            "DJANGO_ALLOWED_HOSTS is required when DJANGO_ENV=production. "
            "Set it to the clinic server's LAN hostname/IP."
        )
    # Development default; the LAN deployment sets the server's real address.
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", ".local"]

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    # Daphne must precede staticfiles so runserver serves ASGI (WebSockets).
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    # Lets a refresh token be revoked at logout. Clinic terminals are shared,
    # so "signed out" has to mean the token is dead, not merely forgotten.
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "channels",
    # Local
    "queueapp",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# WSGI is kept for management commands; ASGI is what actually serves the app.
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# PostgreSQL is the specified database. SQLite is a local-prototype fallback
# only (see docs/development.md) and can never be reached in production.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
elif IS_PRODUCTION:
    raise RuntimeError(
        "DATABASE_URL is required when DJANGO_ENV=production. The SQLite "
        "fallback is for local prototype work only — see docs/development.md."
    )
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
    if not RUNNING_TESTS:
        logger.warning(
            "DATABASE_URL is unset — using the local SQLite prototype fallback "
            "at %s. This is not acceptable for the pilot or any real-data use.",
            DATABASES["default"]["NAME"],
        )

# Staff accounts carry a clinical role, so the user model is ours from the
# start. Patients never have accounts — they are identified only by a token.
AUTH_USER_MODEL = "queueapp.StaffUser"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
# Default-deny: every endpoint requires authentication unless it explicitly
# opts out (the public display and patient status views do, in later phases).
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SIMPLE_JWT = {
    # Falls back to SECRET_KEY so auth works out of the box; set JWT_SIGNING_KEY
    # separately to rotate auth keys without invalidating sessions.
    "SIGNING_KEY": os.environ.get("JWT_SIGNING_KEY") or SECRET_KEY,
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env_int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", 60)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env_int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", 1)
    ),
    "AUTH_HEADER_TYPES": ("Bearer",),
    # A refreshed session issues a new refresh token and retires the old one,
    # so a token copied off a shared terminal has a short useful life.
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# ---------------------------------------------------------------------------
# Channels (real-time)
# ---------------------------------------------------------------------------
REDIS_URL = os.environ.get("REDIS_URL", "").strip()
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    # Single-process only. Adequate for development and a single-worker LAN
    # deployment; set REDIS_URL once more than one worker process runs.
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
if not CORS_ALLOWED_ORIGINS and not IS_PRODUCTION:
    # Two separate frontends, so two origins. The patient app (token entry,
    # patient status, waiting-room board) and the staff app (sign-in and the
    # four dashboards) are different applications on different ports, and both
    # call this API from the browser — an allowlist with only one of them on it
    # fails whichever app is missing, at its first authenticated request.
    _patient_port = env_int("PATIENT_PORT", 3000)
    _staff_port = env_int("STAFF_PORT", 3001)
    CORS_ALLOWED_ORIGINS = [
        origin
        for port in (_patient_port, _staff_port)
        for origin in (f"http://localhost:{port}", f"http://127.0.0.1:{port}")
    ]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# ---------------------------------------------------------------------------
# Visit tokens
# ---------------------------------------------------------------------------
# Tokens are random, not sequential: a counter published on a public board
# tells the room how many people have been seen and in what order they
# arrived, which is information about patients that nobody needs and the board
# has no business disclosing. A random token identifies a visit and says
# nothing else.
#
# The shape is one letter and three digits — K492 — chosen to be said out loud
# and read across a waiting room. Nothing may assume the token's shape.
TOKEN = {
    # O, I, L and S are left out: spoken or read at a distance they are the
    # digits 0, 1, 1 and 5, and a token that can be misheard is a patient sent
    # to the wrong queue.
    "ALPHABET": os.environ.get("TOKEN_ALPHABET", "ABCDEFGHJKMNPQRTUVWXYZ"),
    "DIGITS": env_int("TOKEN_DIGITS", 3),
    # How long an issued token stays reserved before it may be handed to
    # someone else. Patients now leave the board only when pharmacy is done,
    # so a visit can outlive the day it started; a week gives that room while
    # still keeping the pool small enough that tokens stay short.
    "PERIOD_DAYS": env_int("TOKEN_PERIOD_DAYS", 7),
}

# ---------------------------------------------------------------------------
# Stale visits
# ---------------------------------------------------------------------------
# A visit now ends when pharmacy is finished with the patient, not when the day
# does. That is what makes the tracking board honest, and it is also what
# leaves a visit open when somebody goes home without telling anyone: nothing
# in the clinical flow will ever close it.
#
# So reception closes it, by hand, once nothing has happened to the visit for
# this many hours. Deliberately not a scheduled job — a visit still open is a
# patient the clinic has lost track of, and somebody noticing that is worth
# more than a cron entry quietly tidying it away. The threshold is enforced on
# the server, so the capability is "close what has clearly been abandoned" and
# never "remove a patient from the queue".
STALE_VISIT_HOURS = env_int("STALE_VISIT_HOURS", 24)

# ---------------------------------------------------------------------------
# Wait-range calculation (spec: cautious range, never a countdown)
# ---------------------------------------------------------------------------
WAIT_RANGE = {
    "SAMPLE_SIZE": env_int("WAIT_RANGE_SAMPLE_SIZE", 20),
    "MIN_SAMPLES": env_int("WAIT_RANGE_MIN_SAMPLES", 5),
    "BUFFER_PERCENT": env_int("WAIT_RANGE_BUFFER_PERCENT", 30),
}

# ---------------------------------------------------------------------------
# Notifications (optional SMS channel — the only outbound-internet component)
# ---------------------------------------------------------------------------
SMS_ENABLED = env_bool("SMS_ENABLED", False)
SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "africastalking").strip().lower()
# Short on purpose: a gateway having a slow morning must never be the reason a
# member of staff is left waiting at a terminal.
SMS_TIMEOUT_SECONDS = env_int("SMS_TIMEOUT_SECONDS", 8)
# Send inline rather than on a background thread. Off in normal operation; on
# under test so dispatch is deterministic.
SMS_SYNCHRONOUS = env_bool("SMS_SYNCHRONOUS", False) or RUNNING_TESTS

# ---------------------------------------------------------------------------
# Internationalisation / static files
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ---------------------------------------------------------------------------
# Security (hardened in production; the LAN deployment may run plain HTTP)
# ---------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
if IS_PRODUCTION:
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
    CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
