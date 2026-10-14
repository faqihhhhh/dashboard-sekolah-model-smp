from django.urls import path

from . import views

app_name = "intervensi"

urlpatterns = [path("intervensi/kebutuhan/", views.dashboard, name="dashboard")]
