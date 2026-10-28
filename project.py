import os
from pathlib import Path

from pseudoproject.setup.setup import Setup

packagePath = Path(__file__).resolve().parent
packageName = "commercial"
mediaPath = os.path.abspath("media")
staticPath = os.path.abspath("static")

Setup(packageName, packagePath, mediaPath, staticPath)
