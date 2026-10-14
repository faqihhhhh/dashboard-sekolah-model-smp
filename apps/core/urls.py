from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("api/agregat/sekolah/", views.home_aggregate, name="home_aggregate"),
    path("healthz", views.healthz, name="healthz"),
]
