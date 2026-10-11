from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm

app_name = "accounts"

urlpatterns = [
    path(
        "masuk/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
            authentication_form=LoginForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("keluar/", auth_views.LogoutView.as_view(), name="logout"),
    path("pengguna/", views.UserListView.as_view(), name="user_list"),
    path("pengguna/tambah/", views.UserCreateView.as_view(), name="user_create"),
    path("pengguna/<int:pk>/ubah/", views.UserUpdateView.as_view(), name="user_update"),
    path("pengguna/<int:pk>/kata-sandi/", views.UserPasswordView.as_view(), name="user_password"),
]
