"""Tahap commit impor: menyimpan hasil dry-run ke database dalam satu transaksi.

Dry-run (engine.run_dry_run) tidak menulis apa pun. Fungsi di sini baru menulis, setelah admin
meninjau ringkasannya.

Aturan:
- Pemetaan bermasalah = tidak ada yang disimpan.
- Bila ada baris error: batal seluruhnya (bawaan), atau baris error dilewati (skip_errors=True).
  Dalam kedua kasus, baris valid tidak pernah tersimpan setengah-setengah: semuanya atau tidak
  sama sekali (satu transaksi).
- Baris yang diperbarui diambil ulang dengan penguncian di dalam transaksi (select_for_update),
  lalu HANYA field yang berubah menurut dry-run yang ditulis. Perubahan lain yang dibuat orang
  lain setelah dry-run tidak tertimpa.
- Siapa dan alasan perubahan dicatat di riwayat (django-simple-history).
- ImportBatch dicatat sebagai sumber perubahan pada model melalui FK import_batch.
"""

from dataclasses import dataclass, field
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.core.registry import DatasetSpec
from apps.imports.engine import ImportPreview, MappingConfig, RowResult
from apps.imports.models import ImportBatch, ImportBatchStatus, ValueAlias
from apps.referensi.models import AliasKabKota, AliasProvinsi, KabKota, Provinsi

REASON_MAX = 100


class CommitBlocked(Exception):
    """Commit tidak dijalankan. Pesannya aman ditampilkan kepada admin."""

    pass


@dataclass
class CommitResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: list[tuple[int, str]] = field(default_factory=list)
    batch: ImportBatch | None = None

    @property
    def total_processed(self) -> int:
        return self.created + self.updated + self.unchanged + self.skipped


def _messages(error: ValidationError) -> str:
    if hasattr(error, "message_dict"):
        items = [
            f"{field_name}: {', '.join(msgs)}" for field_name, msgs in error.message_dict.items()
        ]
        return "; ".join(items)
    return "; ".join(error.messages)


def _save_row(
    spec: DatasetSpec,
    row: RowResult,
    batch: ImportBatch,
    history_user,
    change_reason: str,
    change_log: dict[str, Any],
) -> None:
    if row.action == "create":
        obj = spec.model(**row.values)
        if hasattr(obj, "import_batch"):
            obj.import_batch = batch
        obj.full_clean()
        obj._history_user = history_user
        obj._change_reason = change_reason
        obj.save()
        change_log.setdefault("created_pks", []).append(obj.pk)

    elif row.action == "update":
        try:
            obj = spec.model.all_objects.select_for_update().get(pk=row.existing.pk)
        except spec.model.DoesNotExist as error:
            raise LookupError("data sudah tidak ada sejak dry-run") from error

        if getattr(obj, "is_deleted", False):
            raise LookupError("data telah dihapus sejak dry-run")

        prev_fields: dict[str, Any] = {}
        for name, _old, new in row.changes:
            model_field = spec.model._meta.get_field(name)
            if model_field.is_relation:
                prev_fields[f"{name}_id"] = getattr(obj, f"{name}_id")
            else:
                prev_fields[name] = getattr(obj, name)
            setattr(obj, name, new)

        prev_batch_id = getattr(obj, "import_batch_id", None)
        change_log.setdefault("updated", []).append(
            {
                "pk": obj.pk,
                "prev_fields": prev_fields,
                "prev_batch_id": prev_batch_id,
            }
        )

        if hasattr(obj, "import_batch"):
            obj.import_batch = batch
        obj.full_clean()
        obj._history_user = history_user
        obj._change_reason = change_reason
        obj.save()

    else:
        raise ValueError(f"aksi tidak dikenal: {row.action}")


def commit_preview(
    spec: DatasetSpec,
    preview: ImportPreview,
    user,
    filename: str = "",
    sheet_name: str = "",
    mapping_config: MappingConfig | None = None,
    file=None,
    reason: str = "Impor data",
    skip_errors: bool = False,
) -> CommitResult:
    if not preview.ok:
        msg = "; ".join(preview.mapping_errors)
        raise CommitBlocked(f"Pemetaan bermasalah: {msg}")

    has_errors = any(row.has_error for row in preview.rows)
    if has_errors and not skip_errors:
        first_error = next(
            (r.row_number, issue.message)
            for r in preview.rows
            for issue in r.issues
            if issue.level == "error"
        )
        raise CommitBlocked(f"Baris {first_error[0]}: {first_error[1]}")

    result = CommitResult()
    change_log: dict[str, Any] = {"created_pks": [], "updated": []}

    history_user = user if getattr(user, "is_authenticated", False) else None
    change_reason = (reason or "Impor data")[:REASON_MAX]

    mapping_dict: dict[str, Any] = {}
    if mapping_config is not None:
        if hasattr(mapping_config, "__dict__"):
            mapping_dict = {
                "columns": mapping_config.columns,
                "header_rows": list(mapping_config.header_rows),
                "fill_right_rows": list(mapping_config.fill_right_rows),
                "first_data_row": mapping_config.first_data_row,
                "null_tokens": list(mapping_config.null_tokens),
                "value_maps": mapping_config.value_maps,
            }
        elif isinstance(mapping_config, dict):
            mapping_dict = dict(mapping_config)

    with transaction.atomic():
        batch = ImportBatch.objects.create(
            dataset_key=spec.key,
            filename=filename or "data",
            sheet_name=sheet_name or "",
            file=file,
            mapping_config=mapping_dict,
            total_rows=len(preview.rows),
            created_by=user,
            status=ImportBatchStatus.COMMITTED,
        )

        batch_reason = f"{change_reason} (Batch #{batch.pk})"

        for row in preview.rows:
            if row.has_error:
                if skip_errors:
                    result.skipped += 1
                    msg = "; ".join(str(i) for i in row.issues)
                    result.errors.append((row.row_number, msg))
                    continue
                else:
                    msg = "; ".join(str(i) for i in row.issues)
                    raise CommitBlocked(f"Baris {row.row_number}: {msg}")

            if row.action == "unchanged":
                result.unchanged += 1
                continue

            try:
                with transaction.atomic():
                    _save_row(spec, row, batch, history_user, batch_reason, change_log)
            except (ValidationError, IntegrityError, LookupError) as error:
                err_msg = _messages(error) if isinstance(error, ValidationError) else str(error)
                if not skip_errors:
                    raise CommitBlocked(f"Baris {row.row_number}: {err_msg}") from error
                result.skipped += 1
                result.errors.append((row.row_number, err_msg))
                continue

            if row.action == "create":
                result.created += 1
            elif row.action == "update":
                result.updated += 1

        # Simpan alias wilayah ke referensi wilayah agar bisa dipakai pada impor berikutnya.
        if mapping_config and getattr(mapping_config, "value_maps", None):
            for field_name, aliases in mapping_config.value_maps.items():
                if field_name not in ("provinsi", "kabkota"):
                    continue
                target_model = Provinsi if field_name == "provinsi" else KabKota
                alias_model = AliasProvinsi if field_name == "provinsi" else AliasKabKota
                relation_name = "provinsi" if field_name == "provinsi" else "kabkota"
                for alias_str, target_val in aliases.items():
                    target = target_model.objects.filter(
                        nama__iexact=str(target_val).strip()
                    ).first()
                    if target is None:
                        raise CommitBlocked(
                            f"Nilai baku wilayah '{target_val}' tidak lagi tersedia. "
                            "Ulangi pemetaan wilayah."
                        )
                    alias = str(alias_str).strip()
                    existing_alias = alias_model.objects.filter(alias__iexact=alias).first()
                    if existing_alias:
                        setattr(existing_alias, relation_name, target)
                        existing_alias.save(update_fields=[relation_name])
                    else:
                        alias_model.objects.create(**{relation_name: target, "alias": alias})

        # Simpan alias pilihan lain ke database (ValueAlias).
        if mapping_config and getattr(mapping_config, "value_maps", None):
            for field_name, aliases in mapping_config.value_maps.items():
                if field_name not in ("provinsi", "kabkota"):
                    for alias_str, target_val in aliases.items():
                        ValueAlias.objects.update_or_create(
                            dataset_key=spec.key,
                            field_name=field_name,
                            alias=alias_str.strip(),
                            defaults={"target_value": str(target_val).strip(), "created_by": user},
                        )

        batch.created_count = result.created
        batch.updated_count = result.updated
        batch.unchanged_count = result.unchanged
        batch.skipped_count = result.skipped
        batch.error_count = len(result.errors)
        change_log["errors"] = [
            {"row": row_number, "message": message} for row_number, message in result.errors
        ]
        batch.change_log = change_log
        batch.save()

        result.batch = batch

    return result
