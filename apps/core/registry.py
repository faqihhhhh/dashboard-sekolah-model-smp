"""Dataset Registry: satu deklarasi per dataset, dipakai oleh banyak fitur.

Model Django tetap menjadi sumber kebenaran untuk tipe, label, dan pilihan nilai tiap field.
Registry hanya menambahkan metadata yang tidak ada di model: kolom mana yang tampil di tabel,
mana yang boleh dilihat Guest, field untuk formulir, pencarian, filter, dan kunci pencocokan
(dipakai mesin impor di Fase 2). Menambah atau menghapus field = ubah model, migrasi, lalu
perbarui daftar di sini.
"""

from dataclasses import dataclass, field

from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.urls import reverse

from apps.accounts.models import Role
from apps.accounts.permissions import has_role

REGISTRY: dict[str, "DatasetSpec"] = {}


@dataclass(frozen=True)
class DatasetSpec:
    key: str
    label: str  # nama tampilan, mis. "Sekolah"
    model: type[models.Model]
    url_namespace: str  # namespace URL, mis. "sekolah"
    list_fields: tuple[str, ...]  # kolom tabel, berurutan
    form_fields: tuple[str, ...]  # field pada formulir tambah/ubah
    public_fields: tuple[str, ...]  # kolom yang boleh dilihat Guest (selebihnya terbatas)
    search_fields: tuple[str, ...] = ()
    filter_fields: tuple[str, ...] = ()
    natural_key: tuple[str, ...] = ()  # kunci pencocokan untuk impor
    time_field: str | None = None  # field tanggal/periode -> otomatis dapat chart perkembangan
    default_aliases: dict[str, dict[str, str]] = field(default_factory=dict, compare=False)

    def __post_init__(self):
        names = {f.name for f in self.model._meta.get_fields()}
        groups = {
            "list_fields": self.list_fields,
            "form_fields": self.form_fields,
            "public_fields": self.public_fields,
            "search_fields": self.search_fields,
            "filter_fields": self.filter_fields,
            "natural_key": self.natural_key,
        }

        for group, fields in groups.items():
            unknown = [f for f in fields if f not in names]
            if unknown:
                raise ImproperlyConfigured(f"{self.key}.{group}: field tidak ada: {unknown}")
        unknown_aliases = [f for f in self.default_aliases if f not in names]
        if unknown_aliases:
            raise ImproperlyConfigured(
                f"{self.key}.default_aliases: field tidak ada: {unknown_aliases}"
            )
        if self.time_field and self.time_field not in names:
            raise ImproperlyConfigured(f"{self.key}.time_field tidak ada: {self.time_field}")
        outside = [f for f in self.public_fields if f not in self.list_fields]
        if outside:
            raise ImproperlyConfigured(
                f"{self.key}.public_fields harus ada di list_fields: {outside}"
            )

    # --- akses per peran ---

    def visible_fields(self, user) -> tuple[str, ...]:
        """Viewer ke atas melihat semua kolom; Guest hanya kolom publik."""
        if has_role(user, Role.VIEWER):
            return self.list_fields
        return tuple(f for f in self.list_fields if f in self.public_fields)

    def filterable_fields(self, user) -> tuple[str, ...]:
        allowed = self.visible_fields(user)
        return tuple(f for f in self.filter_fields if f in allowed)

    def searchable_fields(self, user) -> tuple[str, ...]:
        allowed = self.visible_fields(user)
        return tuple(f for f in self.search_fields if f in allowed)

    # --- tampilan ---

    def field_label(self, name: str) -> str:
        label = str(self.model._meta.get_field(name).verbose_name)
        return label[:1].upper() + label[1:]

    def display(self, obj, name: str) -> str:
        field = self.model._meta.get_field(name)
        value = getattr(obj, name)
        if value is None or value == "":
            return "—"
        if field.choices:
            return str(getattr(obj, f"get_{name}_display")())
        if isinstance(value, bool):
            return "Ya" if value else "Tidak"
        return str(value)

    def filter_options(self, name: str) -> list[tuple[str, str]]:
        field = self.model._meta.get_field(name)
        if field.choices:
            return [(str(value), str(label)) for value, label in field.flatchoices]
        if field.is_relation:
            return [(str(o.pk), str(o)) for o in field.related_model._default_manager.all()]
        return []

    def url(self, name: str, *args) -> str:
        return reverse(f"{self.url_namespace}:{name}", args=args)


def register(spec: DatasetSpec) -> DatasetSpec:
    REGISTRY[spec.key] = spec
    return spec


def get_spec(key: str) -> DatasetSpec:
    return REGISTRY[key]
