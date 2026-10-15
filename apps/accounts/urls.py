from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path(
        "masuk/",
        views.ThrottledLoginView.as_view(),
        name="login",
    ),
    path("keluar/", auth_views.LogoutView.as_view(), name="logout"),
    path("kata-sandi/", views.UserPasswordChangeView.as_view(), name="password_change"),
    path("pengguna/", views.UserListView.as_view(), name="user_list"),
    path("pengguna/tambah/", views.UserCreateView.as_view(), name="user_create"),
    path("pengguna/<int:pk>/ubah/", views.UserUpdateView.as_view(), name="user_update"),
    path("pengguna/<int:pk>/kata-sandi/", views.UserPasswordView.as_view(), name="user_password"),
]
