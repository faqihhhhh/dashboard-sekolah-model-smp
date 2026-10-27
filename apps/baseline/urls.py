from django.urls import path

from . import views

app_name = "baseline"

urlpatterns = [
    path("baseline/", views.dashboard, name="dashboard"),
    path("baseline/hasil/", views.dashboard, name="results"),
    path("baseline/panduan/", views.indicator_guide, name="guide"),
    path("baseline/hasil/<int:pk>/", views.detail, name="detail"),
    path("baseline/impor/", views.import_wizard, name="import_wizard"),
]
