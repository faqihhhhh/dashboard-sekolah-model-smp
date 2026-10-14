from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("surat-dukungan/", views.surat_dukungan, name="surat_dukungan"),
    path("healthz", views.healthz, name="healthz"),
]
