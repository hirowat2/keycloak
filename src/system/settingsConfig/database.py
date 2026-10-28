"""
TODO(Fazendaaa): THIS FILE NEEDS TO BE IMPROVED
"""

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

import os


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DATABASE_ENGINE = (
    os.environ["DJANGO_DATABASE_ENGINE"]
    if "DJANGO_DATABASE_ENGINE" in os.environ
    else ""
)

DATABASE_HOST = (
    os.environ["DJANGO_DATABASE_HOST"] if "DJANGO_DATABASE_HOST" in os.environ else ""
)

DJANGO_DATABASE_NAME = (
    os.environ["DJANGO_DATABASE_NAME"] if "DJANGO_DATABASE_NAME" in os.environ else ""
)

DJANGO_DATABASE_USERNAME = (
    os.environ["DJANGO_DATABASE_USERNAME"]
    if "DJANGO_DATABASE_USERNAME" in os.environ
    else ""
)

DJANGO_DATABASE_PASSWORD = (
    os.environ["DJANGO_DATABASE_PASSWORD"]
    if "DJANGO_DATABASE_PASSWORD" in os.environ
    else ""
)

DJANGO_DATABASE_PORT = (
    os.environ["DJANGO_DATABASE_PORT"] if "DJANGO_DATABASE_PORT" in os.environ else ""
)

ENGINE_MAP = {
    "postgres": "django.db.backends.postgresql",
    "postgresql": "django.db.backends.postgresql",
    "mysql": "django.db.backends.mysql",
    "sqlite": "django.db.backends.sqlite3",
}

DATABASE_DEFAULT_ENGINE = ENGINE_MAP.get(
    DATABASE_ENGINE.lower(),
    "django.db.backends.sqlite3",  # fallback
)

DATABASE_DEFAULT_NAME = (
    DJANGO_DATABASE_NAME if "" != DJANGO_DATABASE_NAME else BASE_DIR / "db.sqlite3"
)

DATABASES = {
    "default": {
        "ENGINE": DATABASE_DEFAULT_ENGINE,
        "NAME": DATABASE_DEFAULT_NAME,
        "USER": DJANGO_DATABASE_USERNAME,
        "PASSWORD": DJANGO_DATABASE_PASSWORD,
        "HOST": DATABASE_HOST,
        "PORT": DJANGO_DATABASE_PORT,
    }
}

