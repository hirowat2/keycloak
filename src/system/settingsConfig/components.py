from django_components import ComponentsSettings

COMPONENTS = ComponentsSettings(
    dirs=[
        os.path.join(BASE_DIR, "system", "components"),
    ],
)

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "compressor.finders.CompressorFinder",
]
