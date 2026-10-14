from django.urls import path

from . import views

app_name = "support"

urlpatterns = [
    path("surat-dukungan/", views.dashboard, name="dashboard"),
    path("surat-dukungan/dokumen/<int:pk>/", views.open_document, name="open_document"),
    path(
        "surat-dukungan/kelola/<int:school_pk>/<str:kind>/",
        views.manage_document,
        name="manage_document",
    ),
]
