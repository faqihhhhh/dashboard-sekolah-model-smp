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
            NavItem("Surat Dukungan"),
            NavItem("Baseline Sekolah"),
        ],
    ),
    (
        "Intervensi",
        [
            NavItem("Direktorat SMP"),
            NavItem("BBPMP/BPMP"),
            NavItem("Dinas Pendidikan"),
        ],
    ),
    (
        "Administrasi",
        [
            NavItem("Pengguna", "accounts:user_list", Role.SUPER_ADMIN),
        ],
    ),
]


def navigation(request):
    match = getattr(request, "resolver_match", None)
    current = match.view_name if match else None
    user = getattr(request, "user", None)

    sections = []
    for title, items in NAV:
        visible = []
        for item in items:
            if item.min_role and not has_role(user, item.min_role):
                continue
            visible.append(
                {
                    "label": item.label,
                    "url": reverse(item.url_name) if item.url_name else None,
                    "active": item.url_name is not None and item.url_name == current,
                }
            )
        if visible:
            sections.append({"title": title, "items": visible})
    return {"nav_sections": sections}
