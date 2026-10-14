from django.urls import path

from . import views

app_name = "imports"

urlpatterns = [
    path("impor/riwayat/", views.batch_history, name="history"),
    path("impor/batch/<int:pk>/", views.batch_detail, name="batch_detail"),
    path("impor/batch/<int:pk>/file/", views.batch_file, name="batch_file"),
    path("impor/batch/<int:pk>/laporan-error/", views.error_report, name="error_report"),
    path("impor/batch/<int:pk>/rollback/", views.batch_rollback, name="rollback"),
    path("impor/<slug:dataset_key>/", views.wizard, name="wizard"),
]
