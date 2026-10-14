from django.urls import path

from . import views

app_name = "baseline"

urlpatterns = [
    path("baseline/impor/", views.import_wizard, name="import_wizard"),
]
