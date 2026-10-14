"""Modul pembatalan (rollback) batch impor.

Aturan hak akses:
- Admin hanya dapat membatalkan batch impor milik sendiri.
- Super Admin dapat membatalkan batch impor milik siapa saja.
- Guest dan Viewer tidak memiliki hak akses.

Semua perubahan dibatalkan dalam satu transaksi atomic:
- Baris yang dibuat pada batch ini di-soft-delete.
- Baris yang diperbarui pada batch ini dikembalikan ke nilai sebelum impor.
- Pelaku dan waktu rollback dicatat, dan riwayat (HistoricalRecords) dibuat.
"""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.permissions import has_role
from apps.core.registry import get_spec
from apps.imports.models import ImportBatch, ImportBatchStatus


def can_rollback(batch: ImportBatch, user) -> tuple[bool, str]:
    """Memeriksa apakah pengguna berhak membatalkan batch impor ini."""
    if batch.status == ImportBatchStatus.ROLLED_BACK:
        return False, "Batch impor ini sudah dibatalkan sebelumnya."
    if not getattr(user, "is_authenticated", False):
        return False, "Pengguna belum masuk."
    if has_role(user, Role.SUPER_ADMIN):
        return True, ""
    if has_role(user, Role.ADMIN):
        if batch.created_by_id == user.pk:
            return True, ""
        return False, "Anda hanya dapat membatalkan batch impor milik sendiri."
    return False, "Anda tidak memiliki hak akses untuk membatalkan batch impor."


def rollback_batch(batch: ImportBatch, user, reason: str | None = None) -> dict[str, int]:
    """Membatalkan seluruh perubahan yang dibuat oleh satu batch impor."""
    ok, err_msg = can_rollback(batch, user)
    if not ok:
        if batch.status == ImportBatchStatus.ROLLED_BACK:
            raise ValueError(err_msg)
        raise PermissionDenied(err_msg)

    if batch.dataset_key == "baseline":
        from apps.baseline.importing import rollback_baseline_batch

        return rollback_baseline_batch(batch, user, reason)

    spec = get_spec(batch.dataset_key)
    change_log = batch.change_log or {}
    created_pks = change_log.get("created_pks", [])
    updated_items = change_log.get("updated", [])

    rollback_reason = (
        reason or f"Rollback batch #{batch.pk} ({batch.filename}) oleh {user.get_username()}"
    )
    result = {"soft_deleted": 0, "reverted": 0}

    with transaction.atomic():
        # 1. Soft delete data yang dibuat
        for pk in created_pks:
            obj = spec.model.all_objects.select_for_update().filter(pk=pk).first()
            if obj and not getattr(obj, "is_deleted", False):
                obj._history_user = user
                obj._change_reason = rollback_reason
                obj.soft_delete(user=user)
                result["soft_deleted"] += 1

        # 2. Kembalikan data yang diperbarui ke nilai sebelumnya
        for item in updated_items:
            pk = item.get("pk")
            prev_fields = item.get("prev_fields", {})
            prev_batch_id = item.get("prev_batch_id")

            obj = spec.model.all_objects.select_for_update().filter(pk=pk).first()
            if obj:
                for f_name, f_val in prev_fields.items():
                    if f_name.endswith("_id") and hasattr(obj, f_name):
                        setattr(obj, f_name, f_val)
                        rel_name = f_name[:-3]
                        if hasattr(obj, "_state") and rel_name in obj._state.fields_cache:
                            del obj._state.fields_cache[rel_name]
                    else:
                        setattr(obj, f_name, f_val)
                if hasattr(obj, "import_batch_id"):
                    obj.import_batch_id = prev_batch_id
                obj._history_user = user
                obj._change_reason = rollback_reason
                obj.full_clean()
                obj.save()
                result["reverted"] += 1

        # 3. Tandai batch sebagai dibatalkan
        batch.status = ImportBatchStatus.ROLLED_BACK
        batch.rolled_back_by = user
        batch.rolled_back_at = timezone.now()
        batch._history_user = user
        batch._change_reason = rollback_reason
        batch.save()

    return result
