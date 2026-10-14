"""Tahap commit impor: menyimpan hasil dry-run ke database dalam satu transaksi.

Dry-run (engine.run_dry_run) tidak menulis apa pun. Fungsi di sini baru menulis, setelah admin
meninjau ringkasannya.

Aturan:
- Pemetaan bermasalah = tidak ada yang disimpan.
- Bila ada baris error: batal seluruhnya (bawaan), atau baris error dilewati (skip_errors=True).
  Dalam kedua kasus, baris valid tidak pernah tersimpan setengah-setengah: semuanya atau tidak
  sama sekali (satu transaksi).
- Baris yang diperbarui diambil ulang dengan penguncian di dalam transaksi, lalu HANYA field
  yang berubah menurut dry-run yang ditulis. Perubahan lain yang dibuat orang lain setelah
  dry-run tidak tertimpa.
- Siapa dan alasan perubahan dicatat di riwayat (django-simple-history).
"""

from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.core.registry import DatasetSpec

from .engine import ImportPreview, RowResult

REASON_MAX = 100  # batas panjang history_change_reason


class CommitBlocked(Exception):
    """Commit tidak dijalankan. Pesannya aman ditampilkan kepada admin."""


@dataclass
class CommitResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0  # baris error yang dilewati (hanya bila skip_errors=True)
    errors: list[tuple[int, str]] = field(default_factory=list)  # (nomor baris, pesan)

    @property
    def saved(self) -> int:
        return self.created + self.updated


def _messages(error: ValidationError) -> str:
    return "; ".join(error.messages)


def _history_user(user):
    return user if getattr(user, "is_authenticated", False) else None


def commit_preview(
    spec: DatasetSpec,
    preview: ImportPreview,
    user=None,
    *,
    reason: str = "Impor data",
    skip_errors: bool = False,
) -> CommitResult:
    if not preview.ok:
        raise CommitBlocked("Pemetaan kolom masih bermasalah: " + " ".join(preview.mapping_errors))

    n_error = sum(1 for row in preview.rows if row.has_error)
    if n_error and not skip_errors:
        raise CommitBlocked(
            f"{n_error} baris masih error. Perbaiki file, atau pilih untuk melewati baris error."
        )

    result = CommitResult()
    history_user = _history_user(user)
    change_reason = reason[:REASON_MAX]

    with transaction.atomic():
        for row in preview.rows:
            if row.has_error:
                result.skipped += 1
                continue
            if row.action == "unchanged":
                result.unchanged += 1
                continue
            try:
                with transaction.atomic():  # savepoint per baris
                    _save_row(spec, row, history_user, change_reason)
            except (ValidationError, IntegrityError, LookupError) as error:
                message = _messages(error) if isinstance(error, ValidationError) else str(error)
                if not skip_errors:
                    raise CommitBlocked(f"Baris {row.row_number}: {message}") from error
                result.skipped += 1
                result.errors.append((row.row_number, message))
                continue
            if row.action == "create":
                result.created += 1
            else:
                result.updated += 1
    return result


def _save_row(spec: DatasetSpec, row: RowResult, history_user, change_reason: str) -> None:
    if row.action == "create":
        obj = spec.model(**row.values)
    elif row.action == "update":
        # Ambil ulang dengan kunci; terapkan hanya field yang berubah menurut dry-run.
        try:
            obj = spec.model.all_objects.select_for_update().get(pk=row.existing.pk)
        except spec.model.DoesNotExist as error:
            raise LookupError("data sudah tidak ada sejak dry-run") from error
        if getattr(obj, "is_deleted", False):
            raise LookupError("data telah dihapus sejak dry-run")
        for name, _old, new in row.changes:
            setattr(obj, name, new)
    else:  # pragma: no cover - dijaga oleh pemanggil
        raise ValueError(f"aksi tidak dikenal: {row.action}")

    obj.full_clean()  # aturan lintas-field (mis. kabupaten/kota harus di provinsi itu)
    obj._history_user = history_user
    obj._change_reason = change_reason
    obj.save()
