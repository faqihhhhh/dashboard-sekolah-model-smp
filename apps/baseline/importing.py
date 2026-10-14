"""Transformasi kolom rating baseline menjadi hasil indikator format panjang."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError

from apps.baseline.models import (
    HasilBaseline,
    HasilIndikator,
    KamusIndikator,
    LevelIndikator,
    RatingIndikator,
)
from apps.imports.engine import DEFAULT_NULL_TOKENS, is_null_or_empty
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
                )
            )
            continue
        result.values.append(IndicatorValue(indikator=indicator, rating=rating))

    return result


@dataclass
class BaselineMapping:
    """Pemetaan kolom yang dipilih Admin untuk satu format workbook."""

    npsn_header: str
    indicator_columns: Mapping[str, KamusIndikator]
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
                row.issues.append(IndicatorIssue(header, f"Nilai skor {detail}."))

        for header, key in mapping.profile_columns.items():
            raw = record.get(header)
            if not is_null_or_empty(raw, mapping.null_tokens):
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
                profile_data.update(row.values.get("profil_data", {}))
                if "profil_data" in row.values:
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
