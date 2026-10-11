from django.urls import path

from . import views

app_name = "referensi"

urlpatterns = [
    path("referensi/periode/", views.PeriodeListView.as_view(), name="periode_list"),
    path("referensi/periode/tambah/", views.PeriodeCreateView.as_view(), name="periode_create"),
    path(
        "referensi/periode/<int:pk>/ubah/", views.PeriodeUpdateView.as_view(), name="periode_update"
    ),
    path("referensi/wilayah/", views.WilayahListView.as_view(), name="wilayah_list"),
]
