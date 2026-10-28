import os
import sys

IS_RUNNING_TESTS = "test" in sys.argv

INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    # "debug_toolbar",
    "django.contrib.humanize",
    "django_extensions",
    "health_check",  # required
    "health_check.db",  # stock Django health checkers
    "auditlog",
    "pwa",
    "cachalot",
    "extra_settings",
    "compressor",
    "csp",
    "silk",
    "django_prometheus",
    "django_guid",
    "import_export",
    "modeltrans",
    "django_components",
    "django_htmx",
    "suspense",
] + ([] if IS_RUNNING_TESTS else ["debug_toolbar"]) + (
    [os.environ["PROJECT_PACKAGE_NAME"]] if "PROJECT_PACKAGE_NAME" in os.environ else []
)
