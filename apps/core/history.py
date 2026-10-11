"""Menyusun riwayat perubahan (django-simple-history) menjadi baris yang mudah dibaca."""

from django.utils import timezone
from django.utils.formats import date_format

EXCLUDED_FIELDS = ["updated_at"]


def _display_value(field, value) -> str:
    if value is None or value == "":
        return "—"
    if field.choices:
        return str(dict(field.flatchoices).get(value, value))
    if field.is_relation:
        related = field.related_model._base_manager.filter(pk=value).first()
        return str(related) if related else f"#{value}"
    if isinstance(value, bool):
        return "Ya" if value else "Tidak"
    if hasattr(value, "tzinfo") and hasattr(value, "hour"):
        return date_format(timezone.localtime(value), "d M Y, H:i")
    return str(value)


def _changes(model, record, previous) -> list[dict]:
    """Field yang nilainya berbeda antara dua catatan riwayat berurutan.

    Dibandingkan langsung (bukan lewat diff_against milik pustaka) karena diff_against
    melewatkan field yang tidak editable seperti deleted_at, padahal penghapusan dan
    pemulihan harus tercatat.
    """
    changes = []
    for field in sorted(record.tracked_fields, key=lambda f: f.name):
        if field.name in EXCLUDED_FIELDS:
            continue
        old, new = getattr(previous, field.attname), getattr(record, field.attname)
        if old == new:
            continue
        model_field = model._meta.get_field(field.name)
        label = str(model_field.verbose_name)
        changes.append(
            {
                "field": field.name,
                "label": label[:1].upper() + label[1:],
                "old": _display_value(model_field, old),
                "new": _display_value(model_field, new),
            }
        )
    return changes


def build_history(obj) -> list[dict]:
    """Daftar entri riwayat (terbaru dulu): siapa, kapan, jenis, dan perubahan per field."""
    model = type(obj)
    records = list(
        obj.history.select_related("history_user").order_by("-history_date", "-history_id")
    )
    entries = []
    for index, record in enumerate(records):
        previous = records[index + 1] if index + 1 < len(records) else None
        changes = _changes(model, record, previous) if previous is not None else []
        kind = "Dibuat" if previous is None else "Diubah"
        for change in changes:
            if change["field"] == "deleted_at":
                kind = "Dipulihkan" if change["new"] == "—" else "Dihapus"
        entries.append({"record": record, "kind": kind, "changes": changes})
    return entries
