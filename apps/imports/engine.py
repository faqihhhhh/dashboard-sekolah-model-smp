"""Mesin impor: mencocokkan kolom, validasi, dan dry-run (tanpa menulis ke DB).

Prinsip:
- Pembaca hanya membaca teks.
- Admin memetakan kolom secara manual ke field model.
- Dry-run memvalidasi setiap baris dan melaporkan semua masalah sekaligus.
- Nilai tak dikenal dikumpulkan agar admin dapat menetapkan nilai baku/alias.
- Tidak pernah menebak.
- Tidak menulis apa pun ke database.
"""

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.registry import DatasetSpec

from .normalize import ChoiceResolver, WilayahResolver, parse_int
from .readers import Table, build_columns, iter_records

DEFAULT_NULL_TOKENS = ("#N/A",)


def is_null_or_empty(val: Any, null_tokens: Iterable[str] = DEFAULT_NULL_TOKENS) -> bool:
    if val is None:
        return True
    text = str(val).strip()
    if not text:
        return True
    tokens = {str(t).strip().upper() for t in null_tokens}
    return text.upper() in tokens


@dataclass
class MappingConfig:
    columns: dict[str, str | None] = field(default_factory=dict)
    header_rows: tuple[int, ...] = (1,)
    fill_right_rows: tuple[int, ...] = ()
    first_data_row: int = 2
    null_tokens: tuple[str, ...] = DEFAULT_NULL_TOKENS
    value_maps: dict[str, dict[str, str]] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.columns, dict):
            raise ValueError("'columns' harus berupa objek JSON.")
        if any(
            not isinstance(header, str) or (target is not None and not isinstance(target, str))
            for header, target in self.columns.items()
        ):
            raise ValueError("Header dan field tujuan pemetaan harus berupa teks.")
        if isinstance(self.header_rows, (list, set)):
            self.header_rows = tuple(self.header_rows)
        if isinstance(self.fill_right_rows, (list, set)):
            self.fill_right_rows = tuple(self.fill_right_rows)
        if isinstance(self.null_tokens, (list, set)):
            self.null_tokens = tuple(self.null_tokens)
        if not isinstance(self.header_rows, tuple) or any(
            not isinstance(row, int) or isinstance(row, bool) or row < 1 for row in self.header_rows
        ):
            raise ValueError("'header_rows' harus berisi nomor baris positif.")
        if not self.header_rows or len(set(self.header_rows)) != len(self.header_rows):
            raise ValueError("Pilih setidaknya satu baris header dan jangan ulangi nomor baris.")
        if not isinstance(self.fill_right_rows, tuple) or any(
            not isinstance(row, int) or isinstance(row, bool) or row < 1
            for row in self.fill_right_rows
        ):
            raise ValueError("'fill_right_rows' harus berisi nomor baris positif.")
        if any(row not in self.header_rows for row in self.fill_right_rows):
            raise ValueError(
                "'fill_right_rows' hanya boleh berisi baris yang dipilih sebagai header."
            )
        if (
            not isinstance(self.first_data_row, int)
            or isinstance(self.first_data_row, bool)
            or self.first_data_row < 1
        ):
            raise ValueError("'first_data_row' harus berupa nomor baris positif.")
        if not isinstance(self.null_tokens, tuple) or any(
            not isinstance(token, str) for token in self.null_tokens
        ):
            raise ValueError("'null_tokens' harus berupa daftar teks.")
        if not isinstance(self.value_maps, dict) or any(
            not isinstance(field_name, str)
            or not isinstance(aliases, dict)
            or any(
                not isinstance(alias, str) or not isinstance(value, str)
                for alias, value in aliases.items()
            )
            for field_name, aliases in self.value_maps.items()
        ):
            raise ValueError("'value_maps' harus memetakan teks alias ke teks nilai baku.")


@dataclass
class RowIssue:
    message: str
    field: str | None = None
    level: str = "error"  # "error" | "warning"

    def __str__(self) -> str:
        return self.message


@dataclass
class RowResult:
    row_number: int
    raw: dict[str, str | None]
    values: dict[str, Any] = field(default_factory=dict)
    issues: list[RowIssue] = field(default_factory=list)
    action: str = "create"  # "create" | "update" | "unchanged"
    existing: Any = None
    changes: list[tuple[str, Any, Any]] = field(default_factory=list)

    @property
    def has_error(self) -> bool:
        return any(issue.level == "error" for issue in self.issues)


@dataclass
class ImportPreview:
    rows: list[RowResult] = field(default_factory=list)
    mapping_errors: list[str] = field(default_factory=list)
    unknown_values: dict[str, set[str]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return len(self.mapping_errors) == 0

    def counts(self) -> dict[str, int]:
        result = {"create": 0, "update": 0, "unchanged": 0, "error": 0}
        for row in self.rows:
            if row.has_error:
                result["error"] += 1
            elif row.action in result:
                result[row.action] += 1
        return result

    def issues(self) -> Iterator[tuple[int, RowIssue]]:
        for row in self.rows:
            for issue in row.issues:
                yield row.row_number, issue


def check_mapping(
    spec: DatasetSpec,
    mapping: MappingConfig,
    available_headers: Sequence[str] | None = None,
) -> list[str]:
    """Memeriksa apakah konfigurasi pemetaan valid sebelum dry-run."""
    errors: list[str] = []

    # 1. Header yang dipetakan harus ada di file bila daftar header diberikan
    if available_headers is not None:
        available_set = set(available_headers)
        for header in mapping.columns:
            if header not in available_set:
                errors.append(f"Header '{header}' tidak ditemukan pada file.")

    system_fields = {
        "created_at",
        "updated_at",
        "deleted_at",
        "deleted_by",
        "extra",
        "import_batch",
    }
    importable_fields = {
        model_field.name
        for model_field in spec.model._meta.fields
        if not model_field.auto_created
        and not model_field.primary_key
        and model_field.name not in system_fields
    }

    # 2. Satu field tidak boleh dipetakan dari lebih dari satu kolom
    target_counts: dict[str, list[str]] = {}
    for header, field_name in mapping.columns.items():
        if field_name is None:
            continue
        if not isinstance(header, str) or not isinstance(field_name, str):
            errors.append("Nama header dan field tujuan pada pemetaan harus berupa teks.")
            continue
        if field_name not in importable_fields:
            errors.append(f"Field tujuan '{field_name}' tidak dapat dipetakan untuk impor.")
            continue
        target_counts.setdefault(field_name, []).append(header)
    for field_name, headers in target_counts.items():
        if len(headers) > 1:
            errors.append(
                f"Field '{field_name}' dipetakan lebih dari satu kali: {', '.join(headers)}."
            )

    for field_name in mapping.value_maps:
        if field_name not in target_counts:
            errors.append(
                f"Pemetaan nilai untuk field '{field_name}' tidak dipakai oleh kolom mana pun."
            )
            continue
        model_field = spec.model._meta.get_field(field_name)
        if field_name not in {"provinsi", "kabkota"} and not model_field.choices:
            errors.append(f"Pemetaan nilai tidak didukung untuk field '{field_name}'.")

    # 3. Kunci natural wajib dipetakan
    for key_field in spec.natural_key:
        if key_field not in target_counts:
            label = spec.field_label(key_field)
            errors.append(f"Field kunci pencocokan '{label}' ({key_field}) belum dipetakan.")

    # 4. Field wajib model harus dipetakan (kecuali provinsi bila kabkota dipetakan)
    for model_field in spec.model._meta.fields:
        if model_field.auto_created:
            continue
        if model_field.name in {
            "created_at",
            "updated_at",
            "deleted_at",
            "deleted_by",
            "extra",
            "import_batch",
        }:
            continue
        if model_field.null or model_field.blank or model_field.has_default():
            continue
        # Provinsi dapat diturunkan dari kabupaten/kota
        if model_field.name == "provinsi" and "kabkota" in target_counts:
            continue
        if model_field.name not in target_counts:
            label = spec.field_label(model_field.name)
            errors.append(f"Field wajib '{label}' ({model_field.name}) belum dipetakan.")

    return errors


def run_dry_run(spec: DatasetSpec, table: Table, mapping: MappingConfig) -> ImportPreview:
    """Menjalankan simulasi impor tanpa menulis ke database."""
    columns = build_columns(table, mapping.header_rows, mapping.fill_right_rows)
    if mapping.first_data_row <= max(mapping.header_rows):
        return ImportPreview(
            rows=[],
            mapping_errors=["Baris awal data harus setelah semua baris header."],
            unknown_values={},
        )
    available_headers = [c.header for c in columns]

    mapping_errors = check_mapping(spec, mapping, available_headers)
    if mapping_errors:
        return ImportPreview(rows=[], mapping_errors=mapping_errors, unknown_values={})

    wilayah_resolver = WilayahResolver()

    choice_resolvers: dict[str, ChoiceResolver] = {}
    for f in spec.model._meta.fields:
        if f.choices:
            combined_aliases = dict(spec.default_aliases.get(f.name, {}))
            try:
                from apps.imports.models import ValueAlias

                for va in ValueAlias.objects.filter(dataset_key=spec.key, field_name=f.name):
                    combined_aliases[va.alias] = va.target_value
            except Exception:
                pass
            combined_aliases.update(mapping.value_maps.get(f.name, {}))
            choice_resolvers[f.name] = ChoiceResolver(f.flatchoices, combined_aliases)

    unknown_values: dict[str, set[str]] = {
        field_name: set() for field_name in mapping.columns.values() if field_name
    }
    seen_keys: dict[tuple, int] = {}
    rows: list[RowResult] = []

    for row_number, record in iter_records(table, columns, mapping.first_data_row):
        row_values: dict[str, Any] = {}
        issues: list[RowIssue] = []

        # --- A. Wilayah: Provinsi ---
        prov_header = next(
            (h for h, fn in mapping.columns.items() if fn == "provinsi"),
            None,
        )
        if prov_header is not None:
            raw_prov = record.get(prov_header)
            if not is_null_or_empty(raw_prov, mapping.null_tokens):
                raw_prov_str = str(raw_prov).strip()
                prov_val = mapping.value_maps.get("provinsi", {}).get(raw_prov_str, raw_prov_str)
                res_prov = wilayah_resolver.resolve_provinsi(prov_val)
                if res_prov.ok:
                    row_values["provinsi"] = res_prov.obj
                else:
                    unknown_values.setdefault("provinsi", set()).add(raw_prov_str)
                    issues.append(RowIssue(message=res_prov.detail, field="provinsi"))

        # --- B. Wilayah: Kab/Kota ---
        kab_header = next(
            (h for h, fn in mapping.columns.items() if fn == "kabkota"),
            None,
        )
        if kab_header is not None:
            raw_kab = record.get(kab_header)
            if not is_null_or_empty(raw_kab, mapping.null_tokens):
                raw_kab_str = str(raw_kab).strip()
                kab_val = mapping.value_maps.get("kabkota", {}).get(raw_kab_str, raw_kab_str)
                prov_context = row_values.get("provinsi")
                res_kab = wilayah_resolver.resolve_kabkota(kab_val, provinsi=prov_context)
                if res_kab.ok:
                    row_values["kabkota"] = res_kab.obj
                    if "provinsi" not in row_values:
                        row_values["provinsi"] = res_kab.obj.provinsi
                else:
                    unknown_values.setdefault("kabkota", set()).add(raw_kab_str)
                    issues.append(RowIssue(message=res_kab.detail, field="kabkota"))

        # --- C. Field-field lain ---
        for header, field_name in mapping.columns.items():
            if not field_name or field_name in ("provinsi", "kabkota"):
                continue
            raw_val = record.get(header)
            if is_null_or_empty(raw_val, mapping.null_tokens):
                continue

            model_field = spec.model._meta.get_field(field_name)

            if field_name in choice_resolvers:
                resolved_choice = choice_resolvers[field_name].resolve(raw_val)
                if resolved_choice is not None:
                    row_values[field_name] = resolved_choice
                else:
                    unknown_values.setdefault(field_name, set()).add(str(raw_val).strip())
                    label = spec.field_label(field_name)
                    issues.append(
                        RowIssue(
                            message=f"Pilihan '{raw_val}' pada field '{label}' tidak dikenali.",
                            field=field_name,
                        )
                    )
            elif isinstance(
                model_field,
                (models.IntegerField, models.PositiveIntegerField, models.SmallIntegerField),
            ):
                try:
                    parsed = parse_int(raw_val)
                    model_field.run_validators(parsed)
                    row_values[field_name] = parsed
                except (ValueError, ValidationError) as error:
                    label = spec.field_label(field_name)
                    detail = (
                        "; ".join(error.messages)
                        if isinstance(error, ValidationError)
                        else "bukan bilangan bulat yang valid"
                    )
                    issues.append(
                        RowIssue(
                            message=f"Nilai '{raw_val}' pada field '{label}' {detail}.",
                            field=field_name,
                        )
                    )
            else:
                clean_val = str(raw_val).strip()
                try:
                    model_field.run_validators(clean_val)
                    row_values[field_name] = clean_val
                except ValidationError as err:
                    issues.append(RowIssue(message="; ".join(err.messages), field=field_name))

        # --- D. Kunci Pencocokan (Natural Key) ---
        missing_keys = [k for k in spec.natural_key if k not in row_values]
        key_tuple = None
        key_repr = ""
        if missing_keys:
            for k in missing_keys:
                if not any(i.field == k for i in issues):
                    issues.append(
                        RowIssue(
                            message=f"Field kunci '{spec.field_label(k)}' wajib diisi.",
                            field=k,
                        )
                    )
        else:
            key_tuple = tuple(row_values[k] for k in spec.natural_key)
            key_repr = ", ".join(f"{spec.field_label(k)}={row_values[k]}" for k in spec.natural_key)
            if key_tuple in seen_keys:
                first_row = seen_keys[key_tuple]
                issues.append(
                    RowIssue(
                        message=(
                            f"Duplikat dalam file: {key_repr} "
                            f"(pertama muncul di baris {first_row})."
                        ),
                        field=spec.natural_key[0],
                    )
                )
            else:
                seen_keys[key_tuple] = row_number

        # --- E. Cek Data di Database & Tentukan Aksi ---
        existing = None
        changes: list[tuple[str, Any, Any]] = []
        action = "create"

        nat_key_has_errors = any(i.field in spec.natural_key for i in issues)
        if key_tuple is not None and not nat_key_has_errors:
            filter_kwargs = {k: row_values[k] for k in spec.natural_key}
            existing = spec.model.all_objects.filter(**filter_kwargs).first()
            if existing is not None and getattr(existing, "is_deleted", False):
                issues.append(
                    RowIssue(
                        message=(
                            f"Data dengan {key_repr} telah dihapus. "
                            "Pulihkan dulu melalui menu Terhapus."
                        ),
                        field=spec.natural_key[0],
                    )
                )

        if existing is not None and not getattr(existing, "is_deleted", False):
            for header, field_name in mapping.columns.items():
                if not field_name or field_name in spec.natural_key:
                    continue
                raw_val = record.get(header)
                if is_null_or_empty(raw_val, mapping.null_tokens):
                    continue
                if field_name not in row_values:
                    continue
                new_val = row_values[field_name]
                old_val = getattr(existing, field_name)
                old_cmp = getattr(old_val, "pk", old_val)
                new_cmp = getattr(new_val, "pk", new_val)
                if old_cmp != new_cmp:
                    changes.append((field_name, old_val, new_val))

            province_header = next(
                (
                    header
                    for header, field_name in mapping.columns.items()
                    if field_name == "provinsi"
                ),
                None,
            )
            province_is_empty = province_header is None or is_null_or_empty(
                record.get(province_header), mapping.null_tokens
            )
            if "kabkota" in row_values and province_is_empty:
                new_prov = row_values["kabkota"].provinsi
                if existing.provinsi_id != new_prov.pk:
                    changes.append(("provinsi", existing.provinsi, new_prov))

            action = "update" if changes else "unchanged"
        else:
            action = "create"
            for f in spec.model._meta.fields:
                if f.auto_created or f.name in {
                    "created_at",
                    "updated_at",
                    "deleted_at",
                    "deleted_by",
                    "extra",
                    "import_batch",
                }:
                    continue
                if f.name in row_values:
                    continue
                if f.has_default():
                    row_values[f.name] = f.get_default()
                elif f.null or f.blank:
                    row_values[f.name] = None
                elif f.name == "provinsi" and "kabkota" in row_values:
                    row_values["provinsi"] = row_values["kabkota"].provinsi
                else:
                    if not any(i.field == f.name for i in issues):
                        label = spec.field_label(f.name)
                        issues.append(
                            RowIssue(
                                message=f"Field wajib '{label}' tidak boleh kosong.",
                                field=f.name,
                            )
                        )
            if "extra" not in row_values and hasattr(spec.model, "extra"):
                row_values["extra"] = {}

        rows.append(
            RowResult(
                row_number=row_number,
                raw=record,
                values=row_values,
                issues=issues,
                action=action,
                existing=existing,
                changes=changes,
            )
        )

    return ImportPreview(rows=rows, mapping_errors=[], unknown_values=unknown_values)
