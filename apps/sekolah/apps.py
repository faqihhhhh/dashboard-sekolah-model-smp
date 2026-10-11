from django.apps import AppConfig


class SekolahConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sekolah"
    verbose_name = "Sekolah"

    def ready(self):
        from . import dataset  # noqa: F401  (mendaftarkan dataset ke registry)
