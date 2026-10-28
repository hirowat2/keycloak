"""https://django-split-settings.readthedocs.io/en/latest/"""

import os

from split_settings.tools import include
from sqlparse.engine import grouping

from .setadmin import JAZZMIN_SETTINGS, JAZZMIN_UI_TWEAKS

grouping.MAX_GROUPING_TOKENS = 50_000
# App do sistema (src/commercial). O caminho sai deste arquivo: vale no Docker (/usr/src/src) e fora dele.
os.environ["PROJECT_PACKAGE_NAME"] = "commercial"
os.environ["PROJECT_PACKAGE_PATH"] = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "commercial")

include(
    "settingsConfig/apps.py",
    "settingsConfig/auditlog.py",
    "settingsConfig/base.py",
    "settingsConfig/csp.py",
    "settingsConfig/components.py",
    "settingsConfig/compress.py",
    "settingsConfig/database.py",
    "settingsConfig/debugToolbar.py",
    "settingsConfig/guid.py",
    "settingsConfig/importExport.py",
    "settingsConfig/sso.py",
    "settingsConfig/logging.py",
    "settingsConfig/middleware.py",
    "settingsConfig/pwa.py",
    "settingsConfig/permissionsPolicy.py",
    "settingsConfig/silk.py",
)

JAZZMIN_SETTINGS = JAZZMIN_SETTINGS
JAZZMIN_UI_TWEAKS = JAZZMIN_UI_TWEAKS
