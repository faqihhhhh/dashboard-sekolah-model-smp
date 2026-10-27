from django.urls import path

from . import views

app_name = "galeri"

urlpatterns = [
    path("galeri-praktik/", views.video_list, name="list"),
    path("galeri-praktik/tambah/", views.video_manage, name="create"),
    path("galeri-praktik/<int:pk>/ubah/", views.video_manage, name="update"),
    path("galeri-praktik/<int:pk>/hapus/", views.video_delete, name="delete"),
]
