import re
import uuid
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files import File
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST
from openpyxl import Workbook

from apps.accounts.models import Role
from apps.accounts.permissions import has_role
from apps.core.registry import get_spec

from .commit import CommitBlocked, commit_preview
from .engine import DEFAULT_NULL_TOKENS, MappingConfig, run_dry_run
from .models import ImportBatch, MappingProfile
from .readers import (
    DELIMITERS,
    ENCODINGS,
    MAX_FILE_BYTES,
    ReaderError,
    build_columns,
    list_sheets,
    load_table,
)
from .rollback import can_rollback, rollback_batch

STEPS = (
    ("upload", "Unggah"),
    ("headers", "Header"),
    ("mapping", "Pemetaan"),
    ("preview", "Tinjau"),
    ("done", "Selesai"),
)
STAGING_DIR = "import-staging"


def _require_import_role(request):
    if not has_role(request.user, Role.ADMIN):
        raise PermissionDenied


def _batch_or_404(pk):
    return get_object_or_404(
        ImportBatch.objects.select_related("created_by", "rolled_back_by"), pk=pk
    )


@login_required
def batch_history(request):
    _require_import_role(request)
    batches = ImportBatch.objects.select_related("created_by", "rolled_back_by").all()
    return render(request, "imports/history.html", {"batches": batches})


@login_required
def batch_detail(request, pk):
    _require_import_role(request)
    batch = _batch_or_404(pk)
    can_revert, rollback_reason = can_rollback(batch, request.user)
    return render(
        request,
        "imports/batch_detail.html",
        {"batch": batch, "can_rollback": can_revert, "rollback_reason": rollback_reason},
    )


@login_required
def batch_file(request, pk):
    _require_import_role(request)
    batch = _batch_or_404(pk)
    if not batch.file:
        raise Http404("File asli tidak tersedia untuk batch ini.")
    try:
        file_handle = batch.file.open("rb")
    except OSError as error:
        raise Http404("File asli tidak dapat dibuka.") from error
    return FileResponse(file_handle, as_attachment=True, filename=Path(batch.filename).name)


@login_required
def error_report(request, pk):
    _require_import_role(request)
    batch = _batch_or_404(pk)
    if not batch.error_count:
        raise Http404("Batch ini tidak memiliki baris error yang dilewati.")

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Error impor"
    sheet.append(["Nomor baris", "Pesan error"])
    for entry in (batch.change_log or {}).get("errors", []):
        sheet.append([entry.get("row", ""), entry.get("message", "")])
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="laporan-error-batch-{batch.pk}.xlsx"'
    return response


@login_required
@require_POST
def batch_rollback(request, pk):
    _require_import_role(request)
    batch = _batch_or_404(pk)
    if request.POST.get("confirm") != "1":
        messages.error(request, "Centang konfirmasi untuk menjalankan rollback.")
        return redirect("imports:batch_detail", pk=batch.pk)
    allowed, reason = can_rollback(batch, request.user)
    if not allowed:
        messages.error(request, reason)
        return redirect("imports:batch_detail", pk=batch.pk)
    result = rollback_batch(batch, request.user, reason=request.POST.get("reason", ""))
    messages.success(
        request,
        f"Rollback batch #{batch.pk} selesai: {result['soft_deleted']} data baru dipulihkan "
        f"dan {result['reverted']} perubahan dikembalikan.",
    )
    return redirect("imports:history")


def _state_key(dataset_key):
    return f"import_wizard_{dataset_key}"


def _stage_path(state):
    token = state.get("token", "")
    if not re.fullmatch(r"[a-f0-9]{32}", token):
        raise ReaderError("Sesi unggah tidak valid. Mulai impor kembali.")
    suffix = state.get("suffix", "")
    if suffix not in {".xlsx", ".csv"}:
        raise ReaderError("Format file pada sesi unggah tidak valid. Mulai impor kembali.")
    return Path(settings.MEDIA_ROOT) / STAGING_DIR / f"{token}{suffix}"


def _delete_staged(state):
    try:
        _stage_path(state).unlink(missing_ok=True)
    except (OSError, ReaderError):
        pass


def _mapping(state):
    data = state.get("mapping", {})
    return MappingConfig(
        columns=data.get("columns", {}),
        header_rows=data.get("header_rows", [1]),
        fill_right_rows=data.get("fill_right_rows", []),
        first_data_row=data.get("first_data_row", 2),
        null_tokens=data.get("null_tokens", list(DEFAULT_NULL_TOKENS)),
        value_maps=data.get("value_maps", {}),
    )


def _table(state):
    path = _stage_path(state)
    return load_table(
        path,
        sheet=state.get("sheet"),
        encoding=state.get("encoding"),
        delimiter=state.get("delimiter"),
    )


def _field_choices(spec):
    fields = []
    for name in spec.model._meta.get_fields():
        if not getattr(name, "concrete", False) or name.auto_created or name.primary_key:
            continue
        if name.name in {
            "created_at",
            "updated_at",
            "deleted_at",
            "deleted_by",
            "extra",
            "import_batch",
        }:
            continue
        choices = []
        if name.choices:
            choices = [(str(value), str(label)) for value, label in name.flatchoices]
        fields.append({"name": name.name, "label": spec.field_label(name.name), "choices": choices})
    return fields


def _alias_options(spec, field_name):
    model_field = spec.model._meta.get_field(field_name)
    if model_field.choices:
        return [(str(value), str(label)) for value, label in model_field.flatchoices]
    if field_name in {"provinsi", "kabkota"}:
        from apps.referensi.models import KabKota, Provinsi

        queryset = (
            Provinsi.objects.all()
            if field_name == "provinsi"
            else KabKota.objects.select_related("provinsi")
        )
        return [(str(item), str(item)) for item in queryset]
    return []


def _preview_context(spec, state):
    preview = run_dry_run(spec, _table(state), _mapping(state))
    table = _table(state)
    columns = build_columns(table, _mapping(state).header_rows, _mapping(state).fill_right_rows)
    return preview, columns


def _render(request, spec, state, *, error=None, preview=None, columns=None, result=None):
    stage = state.get("stage", "upload")
    context = {
        "spec": spec,
        "state": state,
        "stage": stage,
        "steps": STEPS,
        "step_index": [item[0] for item in STEPS].index(stage),
        "error": error,
        "encodings": ENCODINGS.keys(),
        "delimiters": [
            (value, {",": "Koma (,)", ";": "Titik koma (;)", "\t": "Tab"}[value])
            for value in DELIMITERS
        ],
        "fields": _field_choices(spec),
        "profiles": MappingProfile.objects.filter(dataset_key=spec.key),
        "result": result,
        "wizard_url": reverse("imports:wizard", args=[spec.key]),
        "dataset_list_url": spec.url("list"),
    }
    if stage == "headers" and state.get("suffix") == ".xlsx":
        try:
            context["sheets"] = list_sheets(_stage_path(state))
        except ReaderError as exc:
            context["error"] = str(exc)
    if stage == "mapping" and state.get("mapping"):
        try:
            table = _table(state)
            mapping = _mapping(state)
            context["columns"] = build_columns(table, mapping.header_rows, mapping.fill_right_rows)
            context["selected_columns"] = mapping.columns
            context["mapping_columns"] = [
                {"column": column, "selected": mapping.columns.get(column.header, "")}
                for column in context["columns"]
            ]
            context["matching_profiles"] = MappingProfile.objects.filter(
                dataset_key=spec.key, header_signature=[c.header for c in context["columns"]]
            )
        except ReaderError as exc:
            context["error"] = str(exc)
    if preview is not None:
        context["preview"] = preview
        context["preview_columns"] = columns or []
        context["unknown_fields"] = [
            {
                "name": name,
                "label": spec.field_label(name),
                "values": sorted(values),
                "options": _alias_options(spec, name),
            }
            for name, values in preview.unknown_values.items()
            if values
        ]
        context["preview_rows"] = preview.rows[:100]
        context["more_rows"] = max(len(preview.rows) - 100, 0)
    return render(request, "imports/wizard.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def wizard(request, dataset_key):
    if not has_role(request.user, Role.ADMIN):
        raise PermissionDenied
    try:
        spec = get_spec(dataset_key)
    except KeyError as error:
        raise PermissionDenied("Dataset tidak tersedia untuk impor.") from error

    key = _state_key(dataset_key)
    state = request.session.get(key, {})
    if state and state.get("user_id") != request.user.pk:
        _delete_staged(state)
        state = {}
        request.session.pop(key, None)

    if request.method == "GET":
        if request.GET.get("baru"):
            _delete_staged(state)
            state = {}
            request.session.pop(key, None)
        if not state:
            state = {"stage": "upload", "user_id": request.user.pk}
            request.session[key] = state
        preview = columns = None
        if state.get("stage") == "preview":
            try:
                preview, columns = _preview_context(spec, state)
            except ReaderError as exc:
                return _render(request, spec, state, error=str(exc))
        return _render(request, spec, state, preview=preview, columns=columns)

    action = request.POST.get("action", "")
    try:
        if action == "upload":
            uploaded = request.FILES.get("file")
            if not uploaded:
                return _render(
                    request, spec, state, error="Pilih file .xlsx atau .csv terlebih dahulu."
                )
            if uploaded.size > MAX_FILE_BYTES:
                return _render(
                    request,
                    spec,
                    state,
                    error=f"Ukuran file melebihi batas {MAX_FILE_BYTES // (1024 * 1024)} MB.",
                )
            suffix = Path(uploaded.name).suffix.lower()
            if suffix not in {".xlsx", ".csv"}:
                return _render(
                    request, spec, state, error="Hanya file .xlsx dan .csv yang dapat diimpor."
                )
            _delete_staged(state)
            staging = Path(settings.MEDIA_ROOT) / STAGING_DIR
            staging.mkdir(parents=True, exist_ok=True)
            token = uuid.uuid4().hex
            path = staging / f"{token}{suffix}"
            written = 0
            with path.open("wb") as target:
                for chunk in uploaded.chunks():
                    written += len(chunk)
                    if written > MAX_FILE_BYTES:
                        path.unlink(missing_ok=True)
                        return _render(
                            request,
                            spec,
                            state,
                            error=(
                                f"Ukuran file melebihi batas {MAX_FILE_BYTES // (1024 * 1024)} MB."
                            ),
                        )
                    target.write(chunk)
            state = {
                "stage": "headers",
                "user_id": request.user.pk,
                "token": token,
                "suffix": suffix,
                "filename": Path(uploaded.name).name[:255],
            }
            state["filename"] = state["filename"] or f"data{suffix}"
            if suffix == ".csv":
                encoding = request.POST.get("encoding", "")
                delimiter = request.POST.get("delimiter", "")
                if encoding not in ENCODINGS or delimiter not in DELIMITERS:
                    _delete_staged(state)
                    state = {"stage": "upload", "user_id": request.user.pk}
                    return _render(
                        request,
                        spec,
                        state,
                        error="Untuk CSV, pilih encoding dan pemisah secara eksplisit.",
                    )
                state.update(encoding=encoding, delimiter=delimiter, sheet="CSV")
            else:
                try:
                    list_sheets(path)
                except ReaderError:
                    path.unlink(missing_ok=True)
                    raise
            request.session[key] = state

        elif action == "headers":
            if not state.get("token"):
                return redirect(request.path + "?baru=1")
            if state["suffix"] == ".xlsx":
                sheet = request.POST.get("sheet", "")
                if sheet not in list_sheets(_stage_path(state)):
                    raise ReaderError("Pilih sheet yang tersedia pada file.")
                state["sheet"] = sheet
            header_rows = [
                int(value)
                for value in request.POST.get("header_rows", "").split(",")
                if value.strip()
            ]
            fill_rows = [
                int(value)
                for value in request.POST.get("fill_right_rows", "").split(",")
                if value.strip()
            ]
            first_row = int(request.POST.get("first_data_row", "0"))
            mapping = MappingConfig(
                header_rows=header_rows,
                fill_right_rows=fill_rows,
                first_data_row=first_row,
                null_tokens=list(DEFAULT_NULL_TOKENS),
            )
            table = _table(state)
            columns = build_columns(table, mapping.header_rows, mapping.fill_right_rows)
            mapping.columns = {column.header: None for column in columns}
            state.update(stage="mapping", mapping=_mapping_dict(mapping))
            request.session[key] = state

        elif action == "profile":
            table = _table(state)
            mapping = _mapping(state)
            columns = build_columns(table, mapping.header_rows, mapping.fill_right_rows)
            profile = get_object_or_404(
                MappingProfile,
                pk=request.POST.get("profile"),
                dataset_key=spec.key,
                header_signature=[column.header for column in columns],
            )
            profile_data = profile.config
            mapping.columns = profile_data.get("columns", {})
            mapping.value_maps = profile_data.get("value_maps", {})
            state.update(mapping=_mapping_dict(mapping), stage="mapping")
            request.session[key] = state

        elif action == "preview":
            table = _table(state)
            mapping = _mapping(state)
            columns = build_columns(table, mapping.header_rows, mapping.fill_right_rows)
            mapping.columns = {
                column.header: (request.POST.get(f"column_{column.index}") or None)
                for column in columns
            }
            state.update(mapping=_mapping_dict(mapping), stage="preview")
            request.session[key] = state
            preview, preview_columns = _preview_context(spec, state)
            return _render(request, spec, state, preview=preview, columns=preview_columns)

        elif action == "resolve":
            mapping = _mapping(state)
            preview, columns = _preview_context(spec, state)
            for field_name, values in preview.unknown_values.items():
                if not values:
                    continue
                options = dict(_alias_options(spec, field_name))
                aliases = mapping.value_maps.setdefault(field_name, {})
                for value in values:
                    target = request.POST.get(f"alias_{field_name}_{value}", "")
                    if target in options:
                        aliases[value] = options[target]
            state.update(mapping=_mapping_dict(mapping), stage="preview")
            request.session[key] = state
            preview, columns = _preview_context(spec, state)
            return _render(request, spec, state, preview=preview, columns=columns)

        elif action == "commit":
            preview, columns = _preview_context(spec, state)
            if not preview.ok:
                return _render(
                    request,
                    spec,
                    state,
                    error="Pemetaan kolom belum valid.",
                    preview=preview,
                    columns=columns,
                )
            if not preview.rows:
                return _render(
                    request,
                    spec,
                    state,
                    error="Tidak ada baris data untuk diimpor. Periksa kembali baris awal data.",
                    preview=preview,
                    columns=columns,
                )
            skip_errors = request.POST.get("error_mode") == "skip"
            with _stage_path(state).open("rb") as handle:
                result = commit_preview(
                    spec,
                    preview,
                    request.user,
                    filename=state["filename"],
                    sheet_name=state.get("sheet", ""),
                    mapping_config=_mapping(state),
                    file=File(handle, name=state["filename"]),
                    reason=request.POST.get("reason", "Impor melalui wizard"),
                    skip_errors=skip_errors,
                )
            profile_name = request.POST.get("profile_name", "").strip()
            if request.POST.get("save_profile") and profile_name:
                config = _mapping_dict(_mapping(state))
                MappingProfile.objects.update_or_create(
                    dataset_key=spec.key,
                    nama=profile_name[:100],
                    defaults={
                        "header_signature": [column.header for column in columns],
                        "config": config,
                        "created_by": request.user,
                    },
                )
            _delete_staged(state)
            state.update(
                stage="done",
                result={
                    "batch_id": result.batch.pk,
                    "created": result.created,
                    "updated": result.updated,
                    "unchanged": result.unchanged,
                    "skipped": result.skipped,
                },
            )
            request.session[key] = state
            messages.success(
                request,
                f"Impor selesai. Batch #{result.batch.pk} tercatat dan dapat di-rollback "
                "sesuai hak akses.",
            )
        elif action == "cancel":
            _delete_staged(state)
            request.session.pop(key, None)
            return redirect(spec.url("list"))
        else:
            return HttpResponseBadRequest("Aksi wizard tidak dikenal.")
    except (ReaderError, ValueError, KeyError, TypeError) as error:
        return _render(request, spec, state, error=str(error))
    except CommitBlocked as error:
        preview, columns = _preview_context(spec, state)
        return _render(request, spec, state, error=str(error), preview=preview, columns=columns)

    return _render(request, spec, state)


def _mapping_dict(mapping):
    return {
        "columns": mapping.columns,
        "header_rows": list(mapping.header_rows),
        "fill_right_rows": list(mapping.fill_right_rows),
        "first_data_row": mapping.first_data_row,
        "null_tokens": list(mapping.null_tokens),
        "value_maps": mapping.value_maps,
    }
