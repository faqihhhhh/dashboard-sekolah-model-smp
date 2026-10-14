"""Transformasi kolom rating baseline menjadi hasil indikator format panjang."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.baseline.models import (
    HasilBaseline,
    HasilIndikator,
    KamusIndikator,
    LevelIndikator,
    RatingIndikator,
)
from apps.imports.engine import DEFAULT_NULL_TOKENS, is_null_or_empty
from apps.imports.models import ImportBatch, ImportBatchStatus
from apps.imports.normalize import ChoiceResolver
from apps.imports.readers import ReaderError, Table, build_columns, iter_records
from apps.referensi.models import JenisPeriode, Periode
from apps.sekolah.models import Sekolah

RATING_RESOLVER = ChoiceResolver(RatingIndikator.choices)


@dataclass(frozen=True)
class IndicatorValue:
    indikator: KamusIndikator
    rating: str


@dataclass(frozen=True)
class IndicatorIssue:
    header: str
    message: str
    raw_value: str | None = None


@dataclass
class IndicatorTransform:
    values: list[IndicatorValue] = field(default_factory=list)
    issues: list[IndicatorIssue] = field(default_factory=list)
    mapping_errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.mapping_errors and not self.issues


def transform_indicator_values(
    record: Mapping[str, Any],
    column_map: Mapping[str, KamusIndikator],
    *,
    null_tokens: tuple[str, ...] = DEFAULT_NULL_TOKENS,
    value_maps: Mapping[str, Mapping[str, str]] | None = None,
) -> IndicatorTransform:
    """Ubah nilai rating yang dipetakan manual menjadi baris panjang.

    Pemetaan header ke indikator sepenuhnya diberikan pemanggil. Sel kosong atau token null
    diabaikan agar pembaruan tidak menghapus rating yang sudah tersimpan.
    """
    result = IndicatorTransform()
    value_maps = value_maps or {}
    seen_indicators: dict[tuple[str, str, str], str] = {}

    for header, indicator in column_map.items():
        indicator_key = (indicator.kerangka, indicator.level, indicator.kode)
        previous_header = seen_indicators.get(indicator_key)
        if previous_header is not None:
            result.mapping_errors.append(
                f"Indikator {indicator.kode} dipetakan dari dua kolom: "
                f"{previous_header} dan {header}."
            )
            continue
        seen_indicators[indicator_key] = header
        if indicator.level != LevelIndikator.L3:
            result.mapping_errors.append(f"Kolom '{header}' harus dipetakan ke indikator Level 3.")
            continue
        if header not in record:
            result.mapping_errors.append(f"Header '{header}' tidak ada pada baris sumber.")
            continue

        raw = record[header]
        if is_null_or_empty(raw, null_tokens):
            continue
        raw_text = str(raw).strip()
        canonical = value_maps.get(header, {}).get(raw_text, raw_text)
        rating = RATING_RESOLVER.resolve(canonical)
        if rating is None:
            result.issues.append(
                IndicatorIssue(
                    header=header,
                    message=f"Rating '{raw_text}' pada kolom '{header}' tidak dikenali.",
                    raw_value=raw_text,
                )
            )
            continue
        result.values.append(IndicatorValue(indikator=indicator, rating=rating))

    return result


@dataclass
class BaselineMapping:
    """Pemetaan kolom yang dipilih Admin untuk satu format workbook."""

    npsn_header: str
    indicator_columns: Mapping[str, KamusIndikator] = field(default_factory=dict)
    summary_columns: Mapping[str, str] = field(default_factory=dict)
    profile_columns: Mapping[str, str] = field(default_factory=dict)
    header_rows: tuple[int, ...] = (1,)
    fill_right_rows: tuple[int, ...] = ()
    first_data_row: int = 2
    null_tokens: tuple[str, ...] = DEFAULT_NULL_TOKENS
    value_maps: Mapping[str, Mapping[str, str]] = field(default_factory=dict)


@dataclass
class BaselineRowPreview:
    row_number: int
    npsn: str
    school: Sekolah | None = None
    existing: HasilBaseline | None = None
    action: str = "create"
    values: dict[str, Any] = field(default_factory=dict)
    profile_updates: dict[str, str] = field(default_factory=dict)
    indicators: list[IndicatorValue] = field(default_factory=list)
    issues: list[IndicatorIssue] = field(default_factory=list)

    @property
    def has_error(self) -> bool:
        return bool(self.issues)


@dataclass
class BaselinePreview:
    rows: list[BaselineRowPreview] = field(default_factory=list)
    mapping_errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.mapping_errors and not any(row.has_error for row in self.rows)

    def counts(self) -> dict[str, int]:
        result = {"create": 0, "update": 0, "unchanged": 0, "error": 0}
        for row in self.rows:
            if row.has_error:
                result["error"] += 1
            else:
                result[row.action] += 1
        return result


def run_baseline_dry_run(
    table: Table,
    *,
    periode: Periode,
    mapping: BaselineMapping,
) -> BaselinePreview:
    """Validasi impor baseline lebar tanpa menulis data ke database."""
    if periode.jenis != JenisPeriode.BASELINE:
        return BaselinePreview(mapping_errors=["Periode yang dipilih harus berjenis Baseline."])
    try:
        columns = build_columns(table, mapping.header_rows, mapping.fill_right_rows)
    except ReaderError as error:
        return BaselinePreview(mapping_errors=[str(error)])
    if mapping.first_data_row <= max(mapping.header_rows):
        return BaselinePreview(mapping_errors=["Baris awal data harus setelah semua baris header."])

    available = {column.header for column in columns}
    mapped_headers = {
        mapping.npsn_header,
        *mapping.summary_columns.values(),
        *mapping.profile_columns.keys(),
        *mapping.indicator_columns.keys(),
    }
    errors = [
        f"Header '{header}' tidak ditemukan pada file." for header in mapped_headers - available
    ]
    allowed_fields = {"skor_pm", "profil_pm", "skor_kka", "profil_kka"}
    invalid_fields = set(mapping.summary_columns) - allowed_fields
    if invalid_fields:
        errors.append(f"Field ringkasan tidak didukung: {', '.join(sorted(invalid_fields))}.")
    selected_headers = [
        mapping.npsn_header,
        *mapping.summary_columns.values(),
        *mapping.profile_columns,
        *mapping.indicator_columns,
    ]
    if len(selected_headers) != len(set(selected_headers)):
        errors.append("Satu kolom tidak boleh dipetakan ke lebih dari satu tujuan.")
    profile_keys = list(mapping.profile_columns.values())
    if any(not key.strip() for key in profile_keys):
        errors.append("Kunci data profil tidak boleh kosong.")
    if len(profile_keys) != len(set(profile_keys)):
        errors.append("Kunci data profil tidak boleh dipetakan dari beberapa kolom.")
    empty_record = {header: None for header in mapping.indicator_columns}
    mapped_indicators = transform_indicator_values(empty_record, mapping.indicator_columns)
    errors.extend(mapped_indicators.mapping_errors)
    if errors:
        return BaselinePreview(mapping_errors=errors)

    summary_fields = {name: HasilBaseline._meta.get_field(name) for name in mapping.summary_columns}
    seen_npsn: dict[str, int] = {}
    rows: list[BaselineRowPreview] = []
    for row_number, record in iter_records(table, columns, mapping.first_data_row):
        raw_npsn = record.get(mapping.npsn_header)
        npsn = "" if is_null_or_empty(raw_npsn, mapping.null_tokens) else str(raw_npsn).strip()
        row = BaselineRowPreview(row_number=row_number, npsn=npsn)
        if not npsn:
            row.issues.append(IndicatorIssue(mapping.npsn_header, "NPSN wajib diisi."))
        elif len(npsn) != 8 or not npsn.isdigit():
            row.issues.append(
                IndicatorIssue(mapping.npsn_header, "NPSN harus terdiri dari 8 digit angka.")
            )
        elif npsn in seen_npsn:
            row.issues.append(
                IndicatorIssue(
                    mapping.npsn_header,
                    f"NPSN duplikat dalam file; pertama muncul pada baris {seen_npsn[npsn]}.",
                )
            )
        else:
            seen_npsn[npsn] = row_number

        if npsn and len(npsn) == 8 and npsn.isdigit():
            school = Sekolah.all_objects.filter(npsn=npsn).first()
            if school is None:
                row.issues.append(
                    IndicatorIssue(mapping.npsn_header, "Sekolah dengan NPSN ini tidak ditemukan.")
                )
            elif school.is_deleted:
                row.issues.append(
                    IndicatorIssue(mapping.npsn_header, "Sekolah telah dihapus; pulihkan dahulu.")
                )
            else:
                row.school = school

        for field_name, header in mapping.summary_columns.items():
            raw = record.get(header)
            if is_null_or_empty(raw, mapping.null_tokens):
                continue
            try:
                if field_name in {"skor_pm", "skor_kka"}:
                    value = Decimal(str(raw).strip())
                else:
                    value = str(raw).strip()
                summary_fields[field_name].run_validators(value)
                row.values[field_name] = value
            except (InvalidOperation, ValueError, ValidationError) as error:
                detail = (
                    "; ".join(error.messages)
                    if isinstance(error, ValidationError)
                    else "bukan angka desimal yang valid"
                )
                row.issues.append(IndicatorIssue(header, f"Nilai {field_name} {detail}."))

        for header, key in mapping.profile_columns.items():
            raw = record.get(header)
            if not is_null_or_empty(raw, mapping.null_tokens):
                row.profile_updates[key] = str(raw).strip()
                row.values.setdefault("profil_data", {})[key] = str(raw).strip()

        indicator_result = transform_indicator_values(
            record,
            mapping.indicator_columns,
            null_tokens=mapping.null_tokens,
            value_maps=mapping.value_maps,
        )
        row.indicators = indicator_result.values
        row.issues.extend(indicator_result.issues)

        if row.school is not None:
            row.existing = HasilBaseline.all_objects.filter(
                sekolah=row.school, periode=periode
            ).first()
            if row.existing and row.existing.is_deleted:
                row.issues.append(
                    IndicatorIssue(
                        mapping.npsn_header, "Hasil baseline telah dihapus; pulihkan dahulu."
                    )
                )
            if row.existing is not None and not row.existing.is_deleted:
                profile_data = dict(row.existing.profil_data)
                profile_data.update(row.profile_updates)
                if row.profile_updates:
                    row.values["profil_data"] = profile_data
                changed = any(
                    getattr(row.existing, name) != value for name, value in row.values.items()
                )
                existing_indicators = {
                    item.indikator_id: item
                    for item in HasilIndikator.all_objects.filter(hasil_baseline=row.existing)
                }
                for value in row.indicators:
                    old = existing_indicators.get(value.indikator.pk)
                    if old and old.is_deleted:
                        row.issues.append(
                            IndicatorIssue(
                                value.indikator.kode,
                                "Hasil indikator telah dihapus; pulihkan dahulu.",
                            )
                        )
                changed |= any(
                    existing_indicators.get(value.indikator.pk) is None
                    or existing_indicators[value.indikator.pk].rating != value.rating
                    for value in row.indicators
                )
                row.action = "update" if changed else "unchanged"

        rows.append(row)

    return BaselinePreview(rows=rows)


class BaselineCommitBlocked(Exception):
    """Commit impor baseline dibatalkan tanpa menyimpan perubahan parsial."""


@dataclass
class BaselineCommitResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: list[tuple[int, str]] = field(default_factory=list)
    batch: ImportBatch | None = None


def _baseline_mapping_json(mapping: BaselineMapping, periode: Periode) -> dict[str, Any]:
    return {
        "periode_id": periode.pk,
        "npsn_header": mapping.npsn_header,
        "summary_columns": dict(mapping.summary_columns),
        "profile_columns": dict(mapping.profile_columns),
        "indicator_columns": {
            header: {
                "kerangka": indicator.kerangka,
                "level": indicator.level,
                "kode": indicator.kode,
            }
            for header, indicator in mapping.indicator_columns.items()
        },
        "header_rows": list(mapping.header_rows),
        "fill_right_rows": list(mapping.fill_right_rows),
        "first_data_row": mapping.first_data_row,
        "null_tokens": list(mapping.null_tokens),
        "value_maps": dict(mapping.value_maps),
    }


def _history_change(obj, user, reason: str) -> None:
    obj._history_user = user if getattr(user, "is_authenticated", False) else None
    obj._change_reason = reason[:100]


def _commit_baseline_row(row, periode, batch, user, reason, change_log):
    created = row.action == "create"
    previous = {}
    previous_batch_id = None
    if created:
        baseline = HasilBaseline(
            sekolah=row.school,
            periode=periode,
            **row.values,
            import_batch=batch,
        )
        baseline.full_clean()
        _history_change(baseline, user, reason)
        baseline.save()
        change_log["created_baseline_pks"].append(baseline.pk)
    else:
        baseline = HasilBaseline.all_objects.select_for_update().get(pk=row.existing.pk)
        if baseline.is_deleted:
            raise BaselineCommitBlocked("Hasil baseline telah dihapus sejak dry-run.")
        previous_batch_id = baseline.import_batch_id
        for field_name, value in row.values.items():
            if field_name == "profil_data":
                merged = dict(baseline.profil_data)
                merged.update(row.profile_updates)
                value = merged
            if getattr(baseline, field_name) != value:
                old_value = getattr(baseline, field_name)
                previous[field_name] = (
                    str(old_value) if isinstance(old_value, Decimal) else old_value
                )
                setattr(baseline, field_name, value)

    baseline_changed = created or bool(previous)
    baseline_indicators = {
        item.indikator_id: item
        for item in HasilIndikator.all_objects.select_for_update().filter(hasil_baseline=baseline)
    }
    created_indicator_pks = []
    updated_indicators = []
    for value in row.indicators:
        existing_indicator = baseline_indicators.get(value.indikator.pk)
        if existing_indicator is not None and existing_indicator.is_deleted:
            raise BaselineCommitBlocked(
                f"Hasil indikator {value.indikator.kode} telah dihapus sejak dry-run."
            )
        if existing_indicator is None:
            indicator_result = HasilIndikator(
                hasil_baseline=baseline,
                indikator=value.indikator,
                rating=value.rating,
                import_batch=batch,
            )
            indicator_result.full_clean()
            _history_change(indicator_result, user, reason)
            indicator_result.save()
            created_indicator_pks.append(indicator_result.pk)
        elif existing_indicator.rating != value.rating:
            updated_indicators.append(
                {
                    "pk": existing_indicator.pk,
                    "prev_rating": existing_indicator.rating,
                    "prev_batch_id": existing_indicator.import_batch_id,
                }
            )
            existing_indicator.rating = value.rating
            existing_indicator.import_batch = batch
            existing_indicator.full_clean()
            _history_change(existing_indicator, user, reason)
            existing_indicator.save()

    if created:
        change_log["created_indicator_pks"].extend(created_indicator_pks)
    elif previous or created_indicator_pks or updated_indicators:
        change_log["updated_baselines"].append(
            {
                "pk": baseline.pk,
                "prev_fields": previous,
                "prev_batch_id": previous_batch_id,
            }
        )
        if created_indicator_pks or updated_indicators:
            change_log["updated_indicators"].append(
                {
                    "created_pks": created_indicator_pks,
                    "updated": updated_indicators,
                }
            )

    if not created and (baseline_changed or created_indicator_pks or updated_indicators):
        baseline.import_batch = batch
        baseline.full_clean()
        _history_change(baseline, user, reason)
        baseline.save()
    changed = bool(previous or created_indicator_pks or updated_indicators)
    return created, changed if not created else False


def commit_baseline_preview(
    preview: BaselinePreview,
    *,
    periode: Periode,
    mapping: BaselineMapping,
    user,
    filename: str = "data.xlsx",
    sheet_name: str = "",
    file=None,
    reason: str = "Impor baseline",
    skip_errors: bool = False,
) -> BaselineCommitResult:
    """Simpan hasil preview baseline sebagai satu batch transaksional."""
    if preview.mapping_errors:
        raise BaselineCommitBlocked("Pemetaan bermasalah: " + "; ".join(preview.mapping_errors))
    if any(row.has_error for row in preview.rows) and not skip_errors:
        row = next(row for row in preview.rows if row.has_error)
        raise BaselineCommitBlocked(f"Baris {row.row_number}: {row.issues[0].message}")
    if not preview.rows:
        raise BaselineCommitBlocked("Tidak ada baris data untuk disimpan.")
    if not getattr(user, "is_authenticated", False):
        raise BaselineCommitBlocked("Pengguna harus masuk untuk menyimpan impor.")

    result = BaselineCommitResult()
    change_log = {
        "created_baseline_pks": [],
        "created_indicator_pks": [],
        "updated_baselines": [],
        "updated_indicators": [],
        "errors": [],
    }
    reason = (reason or "Impor baseline")[:100]
    with transaction.atomic():
        batch = ImportBatch.objects.create(
            dataset_key="baseline",
            filename=filename,
            sheet_name=sheet_name,
            file=file,
            mapping_config=_baseline_mapping_json(mapping, periode),
            total_rows=len(preview.rows),
            created_by=user,
            status=ImportBatchStatus.COMMITTED,
        )
        batch_reason = f"{reason} (Batch #{batch.pk})"[:100]

        for row in preview.rows:
            if row.has_error:
                result.skipped += 1
                message = "; ".join(issue.message for issue in row.issues)
                result.errors.append((row.row_number, message))
                continue
            try:
                with transaction.atomic():
                    created, updated = _commit_baseline_row(
                        row, periode, batch, user, batch_reason, change_log
                    )
            except (ValidationError, IntegrityError, HasilBaseline.DoesNotExist) as error:
                if not skip_errors:
                    raise BaselineCommitBlocked(f"Baris {row.row_number}: {error}") from error
                result.skipped += 1
                result.errors.append((row.row_number, str(error)))
                continue
            except BaselineCommitBlocked as error:
                if not skip_errors:
                    raise BaselineCommitBlocked(f"Baris {row.row_number}: {error}") from error
                result.skipped += 1
                result.errors.append((row.row_number, str(error)))
                continue

            if created:
                result.created += 1
            elif updated:
                result.updated += 1
            else:
                result.unchanged += 1

        batch.created_count = result.created
        batch.updated_count = result.updated
        batch.unchanged_count = result.unchanged
        batch.skipped_count = result.skipped
        batch.error_count = len(result.errors)
        change_log["errors"] = [
            {"row": row_number, "message": message} for row_number, message in result.errors
        ]
        batch.change_log = change_log
        _history_change(batch, user, batch_reason)
        batch.save()
        result.batch = batch

    return result


def rollback_baseline_batch(batch: ImportBatch, user, reason: str | None = None) -> dict[str, int]:
    """Pulihkan perubahan pada HasilBaseline dan HasilIndikator dari satu batch."""
    change_log = batch.change_log or {}
    rollback_reason = reason or f"Rollback batch #{batch.pk} ({batch.filename})"
    result = {"soft_deleted": 0, "reverted": 0}

    with transaction.atomic():
        for pk in change_log.get("created_indicator_pks", []):
            item = HasilIndikator.all_objects.select_for_update().filter(pk=pk).first()
            if item and not item.is_deleted:
                _history_change(item, user, rollback_reason)
                item.soft_delete(user=user)
                result["soft_deleted"] += 1

        for pk in change_log.get("created_baseline_pks", []):
            baseline = HasilBaseline.all_objects.select_for_update().filter(pk=pk).first()
            if baseline and not baseline.is_deleted:
                _history_change(baseline, user, rollback_reason)
                baseline.soft_delete(user=user)
                result["soft_deleted"] += 1

        for group in change_log.get("updated_indicators", []):
            for entry in group.get("updated", []):
                item = HasilIndikator.all_objects.select_for_update().filter(pk=entry["pk"]).first()
                if item:
                    item.rating = entry["prev_rating"]
                    item.import_batch_id = entry.get("prev_batch_id")
                    item.full_clean()
                    _history_change(item, user, rollback_reason)
                    item.save()
                    result["reverted"] += 1
            for pk in group.get("created_pks", []):
                item = HasilIndikator.all_objects.select_for_update().filter(pk=pk).first()
                if item and not item.is_deleted:
                    _history_change(item, user, rollback_reason)
                    item.soft_delete(user=user)
                    result["soft_deleted"] += 1

        for entry in change_log.get("updated_baselines", []):
            baseline = HasilBaseline.all_objects.select_for_update().filter(pk=entry["pk"]).first()
            if baseline:
                for field_name, value in entry.get("prev_fields", {}).items():
                    setattr(baseline, field_name, value)
                baseline.import_batch_id = entry.get("prev_batch_id")
                baseline.full_clean()
                _history_change(baseline, user, rollback_reason)
                baseline.save()
                result["reverted"] += 1

        batch.status = ImportBatchStatus.ROLLED_BACK
        batch.rolled_back_by = user
        batch.rolled_back_at = timezone.now()
        _history_change(batch, user, rollback_reason)
        batch.save()

    return result
