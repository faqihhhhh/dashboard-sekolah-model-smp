from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("", include("apps.referensi.urls")),
    path("", include("apps.sekolah.urls")),
    path("", include("apps.imports.urls")),
    path("", include("apps.baseline.urls")),
    path("", include("apps.support.urls")),
    path("", include("apps.intervensi.urls")),
    path("", include("apps.core.urls")),
]

handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"
