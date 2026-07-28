"""Configurações Django do Gestor Elétrico."""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .database_urls import (
    validate_neon_direct_url,
    validate_neon_runtime_url,
)

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(nome, padrao=False):
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    normalizado = valor.strip().lower()
    if normalizado in {"1", "true", "yes", "sim", "on"}:
        return True
    if normalizado in {"0", "false", "no", "nao", "não", "off"}:
        return False
    raise ImproperlyConfigured(
        f"{nome} deve ser um valor booleano, como true ou false."
    )


def _env_list(nome, padrao=()):
    valor = os.getenv(nome, "")
    if not valor.strip():
        return list(padrao)
    return [item.strip() for item in valor.split(",") if item.strip()]


CHAVE_DESENVOLVIMENTO = "dev-only-change-me"
DEBUG = _env_bool("DJANGO_DEBUG", True)
REQUIRE_LOGIN = _env_bool("DJANGO_REQUIRE_LOGIN", not DEBUG)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", CHAVE_DESENVOLVIMENTO)
if not DEBUG and SECRET_KEY == CHAVE_DESENVOLVIMENTO:
    raise ImproperlyConfigured(
        "Defina DJANGO_SECRET_KEY antes de executar com DJANGO_DEBUG=False."
    )

ALLOWED_HOSTS = _env_list(
    "DJANGO_ALLOWED_HOSTS",
    ("127.0.0.1", "localhost"),
)
CSRF_TRUSTED_ORIGINS = _env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
if RENDER_EXTERNAL_HOSTNAME:
    if RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    render_origin = f"https://{RENDER_EXTERNAL_HOSTNAME}"
    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(render_origin)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "cadastros",
    "orcamentos",
    "ferramentas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if REQUIRE_LOGIN:
    authentication_index = MIDDLEWARE.index(
        "django.contrib.auth.middleware.AuthenticationMiddleware"
    )
    MIDDLEWARE.insert(
        authentication_index + 1,
        "django.contrib.auth.middleware.LoginRequiredMiddleware",
    )

ROOT_URLCONF = "eletrico.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.app_context",
            ],
        },
    },
]

WSGI_APPLICATION = "eletrico.wsgi.application"
ASGI_APPLICATION = "eletrico.asgi.application"

IS_RENDER = _env_bool("RENDER", False)
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if IS_RENDER and not DATABASE_URL:
    raise ImproperlyConfigured(
        "DATABASE_URL é obrigatória no Render; SQLite não é persistente."
    )
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=int(os.getenv("DJANGO_DB_CONN_MAX_AGE", "60")),
            conn_health_checks=True,
        )
    }
    database_engine = DATABASES["default"]["ENGINE"]
    if IS_RENDER and database_engine != "django.db.backends.postgresql":
        raise ImproperlyConfigured("DATABASE_URL no Render deve usar PostgreSQL/Neon.")
    if (
        _env_bool("DJANGO_DATABASE_SSL_REQUIRE", False)
        and database_engine == "django.db.backends.postgresql"
    ):
        DATABASES["default"].setdefault("OPTIONS", {})
        current_ssl_mode = DATABASES["default"]["OPTIONS"].get("sslmode")
        if not isinstance(current_ssl_mode, str) or current_ssl_mode not in {
            "verify-ca",
            "verify-full",
        }:
            DATABASES["default"]["OPTIONS"]["sslmode"] = "require"
    if database_engine == "django.db.backends.postgresql":
        DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = _env_bool(
            "DJANGO_DB_DISABLE_SERVER_SIDE_CURSORS",
            "-pooler" in DATABASE_URL,
        )
        if IS_RENDER:
            try:
                if _env_bool("DJANGO_DATABASE_EXPECT_POOLED", True):
                    validate_neon_runtime_url(DATABASE_URL)
                else:
                    validate_neon_direct_url(DATABASE_URL)
            except ValueError as error:
                raise ImproperlyConfigured(str(error)) from error
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "database" / "db.sqlite3",
            "OPTIONS": {
                "timeout": 20,
            },
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": ("django.contrib.auth.password_validation.MinimumLengthValidator"),
        "OPTIONS": {"min_length": 12},
    },
    {
        "NAME": ("django.contrib.auth.password_validation.CommonPasswordValidator"),
    },
    {
        "NAME": ("django.contrib.auth.password_validation.NumericPasswordValidator"),
    },
]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "login"
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

HTTPS_MODE = _env_bool("DJANGO_HTTPS_MODE", False)
if HTTPS_MODE:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "3600"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool(
        "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
        False,
    )

SECURE_CONTENT_TYPE_NOSNIFF = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
