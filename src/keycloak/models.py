import importlib
import os

from django.db import models


def is_valid_model(cls, PACKAGE_NAME):
    return (
        isinstance(cls, type)
        and (
            issubclass(cls, models.Model)
            or "model" in cls.__name__.lower()
            or any("model" in base.__name__.lower() for base in cls.__bases__)
        )
        and cls != models.Model
        and hasattr(cls, "_meta")
        and not hasattr(cls._meta, "abstract")
        and not hasattr(cls._meta, "proxy")
        and getattr(cls._meta, "app_label", None) == PACKAGE_NAME
    )


def import_models_from_subfolders():
    imported_models = []
    PACKAGE_NAME = os.environ.get("PROJECT_PACKAGE_NAME", "commercial")
    PACKAGE_DIR = os.environ.get(
        "PROJECT_PACKAGE_PATH", os.path.dirname(os.path.abspath(__file__))
    )

    if not PACKAGE_NAME or not PACKAGE_DIR:
        return imported_models

    MODELS_DIR = os.path.join(PACKAGE_DIR, "screens")

    if not os.path.exists(MODELS_DIR):
        return imported_models

    # 👇 A LISTA NEGRA: Proíbe o models.py de importar arquivos de tela/rotas cedo demais
    EXCLUDED_FILES = {
        "admin.py",
        "resources.py",
        "views.py",
        "view.py",
        "urls.py",
        "apps.py",
        "tests.py",
    }

    for root, _, files in os.walk(MODELS_DIR):
        rel_path = os.path.relpath(root, PACKAGE_DIR)
        module_path = f"{PACKAGE_NAME}.{rel_path.replace(os.sep, '.')}"

        for filename in files:
            if filename.endswith(".py") and not filename.startswith("__"):

                # Se for arquivo de tela (admin.py, etc), pula!
                if filename in EXCLUDED_FILES:
                    continue

                module_name = filename[:-3]
                try:
                    module = importlib.import_module(f"{module_path}.{module_name}")
                    for name, obj in vars(module).items():
                        if is_valid_model(obj, PACKAGE_NAME):
                            globals()[name] = obj
                            imported_models.append(name)
                except ImportError:
                    pass

    return imported_models


__all__ = import_models_from_subfolders()

# Núcleo de propostas (fora de screens/, por isso importado explicitamente).
from commercial.propostas import models as propostas_models  # noqa: E402,F401
