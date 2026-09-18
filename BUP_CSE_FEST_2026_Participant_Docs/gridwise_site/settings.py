"""
Django settings for GridWise — Smart Campus Energy Optimization.

Reuses the existing pydantic Settings object from config.config for application
secrets (LLM keys, host/port). Django settings here are kept minimal because
this project only exposes an HTTP API; it does not use the ORM.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Pull configuration (LLM keys, HOST, PORT, etc.) from the existing pydantic settings.
try:
    from config.config import settings as _pyd_settings
except Exception:
    _pyd_settings = None


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-gridwise-bup-cse-fest-2026-development-only-do-not-use-in-prod",
)

# Allow any host during the hackathon judging period.
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "api",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

REST_FRAMEWORK = {
    # Function-based views are used; keep DRF permissive for the hackathon demo.
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "UNAUTHENTICATED_USER": None,
}

ROOT_URLCONF = "gridwise_site.urls"
WSGI_APPLICATION = "gridwise_site.wsgi.application"
ASGI_APPLICATION = "gridwise_site.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

# An unused sqlite DB so Django can run `migrate` cleanly without an ORM hit.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True

# Bind on the same host/port the previous FastAPI app used, for drop-in parity.
if _pyd_settings is not None:
    HOST = _pyd_settings.HOST
    PORT = int(_pyd_settings.PORT)
else:
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", "8000"))
