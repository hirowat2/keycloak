import importlib
import os

# Descobre o caminho dinamicamente
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_NAME = os.path.basename(PACKAGE_DIR)  # "commercial"
SCREENS_DIR = os.path.join(PACKAGE_DIR, "screens")

# Varre as pastas procurando por arquivos admin.py e importa eles com segurança
if os.path.exists(SCREENS_DIR):
    for root, _, files in os.walk(SCREENS_DIR):
        if "admin.py" in files:
            rel_path = os.path.relpath(root, PACKAGE_DIR)
            module_path = f"{PACKAGE_NAME}.{rel_path.replace(os.sep, '.')}.admin"
            try:
                importlib.import_module(module_path)
                print(f"✅ Loaded admin: {module_path}")
            except Exception as e:
                print(f"⚠️ Failed to load admin {module_path}: {e}")

importlib.import_module(f"{PACKAGE_NAME}.propostas.admin")
