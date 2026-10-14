from dataclasses import dataclass

from django.urls import reverse

from apps.accounts.models import Role
from apps.accounts.permissions import has_role


@dataclass(frozen=True)
class NavItem:
    label: str
    url_name: str | None = None  # None = halaman belum dibangun (tampil nonaktif)
    min_role: str | None = None  # None = semua orang, termasuk Guest


# Satu-satunya tempat mendaftarkan menu sidebar. Saat halaman selesai dibangun,
# isi url_name-nya.
NAV = [
    (
        "Program",
        [
            NavItem("Beranda", "core:home"),
            NavItem("Daftar Sekolah", "sekolah:list"),
            NavItem("Riwayat Impor", "imports:history", Role.ADMIN),
            NavItem("Surat Dukungan", "support:dashboard"),
            NavItem("Baseline Sekolah", "baseline:dashboard"),
        ],
    ),
    (
        "Intervensi",
        [
            NavItem("Kebutuhan Intervensi", "intervensi:dashboard"),
            NavItem("Direktorat SMP"),
            NavItem("BBPMP/BPMP"),
            NavItem("Dinas Pendidikan"),
        ],
    ),
    (
        "Sekolah",
        [
            NavItem("Kurasi"),
            NavItem("Rencana Tindak Lanjut"),
        ],
    ),
    (
        "Administrasi",
        [
            NavItem("Pengguna", "accounts:user_list", Role.SUPER_ADMIN),
            NavItem("Periode", "referensi:periode_list", Role.SUPER_ADMIN),
            NavItem("Wilayah", "referensi:wilayah_list", Role.SUPER_ADMIN),
        ],
    ),
]


def navigation(request):
    path = request.path
    user = getattr(request, "user", None)

    sections = []
    for title, items in NAV:
        visible = []
        for item in items:
            if item.min_role and not has_role(user, item.min_role):
                continue
            url = reverse(item.url_name) if item.url_name else None
            # Aktif bila URL cocok; untuk halaman selain "/" juga cocok pada sub-halamannya.
            active = bool(url) and (path == url if url == "/" else path.startswith(url))
            visible.append({"label": item.label, "url": url, "active": active})
        if visible:
            sections.append({"title": title, "items": visible})
    return {"nav_sections": sections}
