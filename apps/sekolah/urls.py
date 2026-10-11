from django.urls import path

from . import views

app_name = "sekolah"

urlpatterns = [
    path("sekolah/", views.SekolahListView.as_view(), name="list"),
    path("sekolah/tambah/", views.SekolahCreateView.as_view(), name="create"),
    path("sekolah/terhapus/", views.SekolahTrashView.as_view(), name="trash"),
    path("sekolah/opsi-kabkota/", views.KabKotaOptionsView.as_view(), name="options_kabkota"),
    path("sekolah/<int:pk>/ubah/", views.SekolahUpdateView.as_view(), name="update"),
    path("sekolah/<int:pk>/hapus/", views.SekolahDeleteView.as_view(), name="delete"),
    path("sekolah/<int:pk>/riwayat/", views.SekolahHistoryView.as_view(), name="history"),
    path("sekolah/<int:pk>/pulihkan/", views.SekolahRestoreView.as_view(), name="restore"),
]
