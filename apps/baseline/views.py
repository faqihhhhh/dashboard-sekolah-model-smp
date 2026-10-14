import uuid
from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files import File
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.accounts.models import Role
from apps.accounts.permissions import has_role
from apps.imports.readers import (
    DELIMITERS,
    ENCODINGS,
    MAX_FILE_BYTES,
    ReaderError,
    build_columns,
    list_sheets,
    load_table,
)
from apps.imports.views import STAGING_DIR, _delete_staged, _stage_path
from apps.referensi.models import JenisPeriode, Periode

from .importing import (
    BaselineCommitBlocked,
    BaselineMapping,
    commit_baseline_preview,
    run_baseline_dry_run,
)
from .models import KamusIndikator, LevelIndikator, RatingIndikator

SESSION_KEY = "baseline_import_wizard"
STEPS = (
    ("upload", "Unggah"),
    ("headers", "Header"),
    ("mapping", "Pemetaan"),
    ("preview", "Tinjau"),
    ("done", "Selesai"),
)


def _table(state):
    return load_table(
        _stage_path(state),
        sheet=state.get("sheet"),
        encoding=state.get("encoding"),
        delimiter=state.get("delimiter"),
    )


def _mapping(state):
    targets = state.get("targets", {})
    npsn_header = None
    summary_columns = {}
    profile_columns = {}
    indicator_columns = {}
    unique_targets = set()
    for header, target in targets.items():
        if target == "npsn":
            if target in unique_targets:
                raise ReaderError("Petakan hanya satu kolom sebagai NPSN.")
            unique_targets.add(target)
            npsn_header = header
        elif target.startswith("summary:"):
            field_name = target.split(":", 1)[1]
            if field_name in summary_columns:
                raise ReaderError(f"Field ringkasan {field_name} dipetakan lebih dari sekali.")
            summary_columns[field_name] = header
        elif target == "profile_data":
            profile_columns[header] = header
        elif target.startswith("indicator:"):
            try:
                indicator = KamusIndikator.objects.get(
                    pk=int(target.split(":", 1)[1]), level=LevelIndikator.L3, aktif=True
                )
            except (ValueError, KamusIndikator.DoesNotExist) as error:
                raise ReaderError(
                    "Pemetaan indikator tidak valid. Pilih ulang indikator."
                ) from error
            indicator_columns[header] = indicator
    if not npsn_header:
        raise ReaderError("Petakan satu kolom sebagai NPSN.")
    return BaselineMapping(
        npsn_header=npsn_header,
        indicator_columns=indicator_columns,
        summary_columns=summary_columns,
        profile_columns=profile_columns,
        header_rows=tuple(state.get("header_rows", [1])),
        fill_right_rows=tuple(state.get("fill_right_rows", [])),
        first_data_row=state.get("first_data_row", 2),
        value_maps=state.get("value_maps", {}),
    )


def _period(state):
    period = Periode.objects.filter(pk=state.get("periode_id"), jenis=JenisPeriode.BASELINE).first()
    if period is None:
        raise ReaderError("Pilih Periode Baseline yang masih tersedia.")
    return period


def _preview(state):
    return run_baseline_dry_run(_table(state), periode=_period(state), mapping=_mapping(state))


def _unknown_ratings(preview):
    unknown = defaultdict(set)
    for row in preview.rows:
        for issue in row.issues:
            if issue.raw_value:
                unknown[issue.header].add(issue.raw_value)
    return [
        {"header": header, "value": value}
        for header in sorted(unknown)
        for value in sorted(unknown[header])
    ]


def _render(request, state, *, error=None, preview=None):
    stage = state.get("stage", "upload")
    context = {
        "state": state,
        "stage": stage,
        "steps": STEPS,
        "step_index": [step[0] for step in STEPS].index(stage),
        "error": error,
        "encodings": ENCODINGS.keys(),
        "delimiters": [
            (value, {",": "Koma (,)", ";": "Titik koma (;)", "\t": "Tab"}[value])
            for value in DELIMITERS
        ],
        "wizard_url": reverse("baseline:import_wizard"),
        "periods": Periode.objects.filter(jenis=JenisPeriode.BASELINE),
        "rating_choices": RatingIndikator.choices,
    }
    if stage == "headers" and state.get("suffix") == ".xlsx":
        try:
            context["sheets"] = list_sheets(_stage_path(state))
        except ReaderError as exc:
            context["error"] = str(exc)
    if stage == "mapping" and state.get("mapping_ready"):
        try:
            table = _table(state)
            columns = build_columns(table, state["header_rows"], state.get("fill_right_rows", []))
            context["columns"] = [
                {
                    "column": column,
                    "selected": state.get("targets", {}).get(column.header, ""),
                }
                for column in columns
            ]
            context["indicators"] = [
                {"indicator": indicator, "target": f"indicator:{indicator.pk}"}
                for indicator in KamusIndikator.objects.filter(
                    level=LevelIndikator.L3, aktif=True
                ).order_by("kerangka", "urutan", "kode")
            ]
        except (ReaderError, KeyError) as exc:
            context["error"] = str(exc)
    if preview is not None:
        unknown = _unknown_ratings(preview)
        context.update(
            preview=preview,
            preview_rows=preview.rows[:100],
            more_rows=max(len(preview.rows) - 100, 0),
            unknown_ratings=unknown,
        )
    return render(request, "baseline/import_wizard.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def import_wizard(request):
    if not has_role(request.user, Role.ADMIN):
        raise PermissionDenied
    state = request.session.get(SESSION_KEY, {})
    if state and state.get("user_id") != request.user.pk:
        _delete_staged(state)
        state = {}
        request.session.pop(SESSION_KEY, None)

    if request.method == "GET":
        if request.GET.get("baru"):
            _delete_staged(state)
            state = {}
            request.session.pop(SESSION_KEY, None)
        if not state:
            state = {"stage": "upload", "user_id": request.user.pk}
            request.session[SESSION_KEY] = state
        preview = None
        if state.get("stage") == "preview":
            try:
                preview = _preview(state)
            except (ReaderError, ValueError, KeyError) as exc:
                return _render(request, state, error=str(exc))
        return _render(request, state, preview=preview)

    action = request.POST.get("action", "")
    try:
        if action == "upload":
            uploaded = request.FILES.get("file")
            if uploaded is None:
                return _render(request, state, error="Pilih file .xlsx atau .csv terlebih dahulu.")
            if uploaded.size > MAX_FILE_BYTES:
                return _render(request, state, error="Ukuran file melebihi batas 20 MB.")
            suffix = Path(uploaded.name).suffix.lower()
            if suffix not in {".xlsx", ".csv"}:
                return _render(request, state, error="Hanya file .xlsx dan .csv yang didukung.")
            _delete_staged(state)
            staging = Path(settings.MEDIA_ROOT) / STAGING_DIR
            staging.mkdir(parents=True, exist_ok=True)
            token = uuid.uuid4().hex
            state = {
                "stage": "headers",
                "user_id": request.user.pk,
                "token": token,
                "suffix": suffix,
                "filename": Path(uploaded.name).name[:255] or f"data{suffix}",
            }
            path = _stage_path(state)
            written = 0
            with path.open("wb") as target:
                for chunk in uploaded.chunks():
                    written += len(chunk)
                    if written > MAX_FILE_BYTES:
                        path.unlink(missing_ok=True)
                        return _render(request, state, error="Ukuran file melebihi batas 20 MB.")
                    target.write(chunk)
            if suffix == ".csv":
                encoding = request.POST.get("encoding", "")
                delimiter = request.POST.get("delimiter", "")
                if encoding not in ENCODINGS or delimiter not in DELIMITERS:
                    _delete_staged(state)
                    return _render(
                        request,
                        {"stage": "upload", "user_id": request.user.pk},
                        error="Pilih encoding dan pemisah untuk file CSV.",
                    )
                state.update(encoding=encoding, delimiter=delimiter, sheet="CSV")
            else:
                list_sheets(path)
            request.session[SESSION_KEY] = state

        elif action == "headers":
            if state.get("suffix") == ".xlsx":
                sheet = request.POST.get("sheet", "")
                if sheet not in list_sheets(_stage_path(state)):
                    raise ReaderError("Pilih sheet yang tersedia pada file.")
                state["sheet"] = sheet
            try:
                headers = tuple(
                    int(item.strip()) for item in request.POST["header_rows"].split(",")
                )
                fill = tuple(
                    int(item.strip())
                    for item in request.POST.get("fill_right_rows", "").split(",")
                    if item.strip()
                )
                first_row = int(request.POST["first_data_row"])
            except (ValueError, KeyError) as error:
                raise ReaderError("Nomor baris header dan data harus berupa angka.") from error
            table = _table(state)
            columns = build_columns(table, headers, fill)
            if first_row <= max(headers):
                raise ReaderError("Baris pertama data harus setelah semua baris header.")
            state.update(
                stage="mapping",
                header_rows=list(headers),
                fill_right_rows=list(fill),
                first_data_row=first_row,
                targets={column.header: "" for column in columns},
                mapping_ready=True,
            )
            request.session[SESSION_KEY] = state

        elif action == "preview":
            table = _table(state)
            columns = build_columns(table, state["header_rows"], state.get("fill_right_rows", []))
            targets = {}
            for column in columns:
                target = request.POST.get(f"column_{column.index}", "")
                if target:
                    targets[column.header] = target
            state["targets"] = targets
            state["periode_id"] = request.POST.get("periode_id", "")
            state["stage"] = "preview"
            state.setdefault("value_maps", {})
            request.session[SESSION_KEY] = state
            return _render(request, state, preview=_preview(state))

        elif action == "resolve":
            preview = _preview(state)
            unknown = _unknown_ratings(preview)
            value_maps = state.setdefault("value_maps", {})
            valid_ratings = dict(RatingIndikator.choices)
            for index, item in enumerate(unknown):
                target = request.POST.get(f"rating_{index}", "")
                if target in valid_ratings:
                    value_maps.setdefault(item["header"], {})[item["value"]] = target
            request.session[SESSION_KEY] = state
            return _render(request, state, preview=_preview(state))

        elif action == "commit":
            preview = _preview(state)
            if not preview.ok and request.POST.get("error_mode") != "skip":
                return _render(request, state, preview=preview)
            with _stage_path(state).open("rb") as handle:
                result = commit_baseline_preview(
                    preview,
                    periode=_period(state),
                    mapping=_mapping(state),
                    user=request.user,
                    filename=state["filename"],
                    sheet_name=state.get("sheet", ""),
                    file=File(handle, name=state["filename"]),
                    reason=request.POST.get("reason", "Impor baseline melalui wizard"),
                    skip_errors=request.POST.get("error_mode") == "skip",
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
            request.session[SESSION_KEY] = state
            messages.success(request, f"Impor baseline tersimpan sebagai Batch #{result.batch.pk}.")

        elif action == "cancel":
            _delete_staged(state)
            request.session.pop(SESSION_KEY, None)
            return redirect("imports:history")
        else:
            return HttpResponseBadRequest("Aksi impor baseline tidak dikenal.")
    except (ReaderError, ValueError, KeyError, TypeError, BaselineCommitBlocked) as exc:
        if state.get("stage") == "preview":
            try:
                return _render(request, state, error=str(exc), preview=_preview(state))
            except (ReaderError, ValueError, KeyError):
                pass
        return _render(request, state, error=str(exc))

    return _render(request, state)
