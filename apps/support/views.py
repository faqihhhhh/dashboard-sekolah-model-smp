from collections import Counter, defaultdict

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.formats import date_format
from django.views.decorators.http import require_http_methods

from apps.accounts.models import Role
from apps.accounts.permissions import has_role
from apps.core.aggregates import parse_home_filters
from apps.referensi.models import Provinsi
from apps.sekolah.models import Pengusul, Sekolah

from .forms import DokumenDukunganForm
from .models import DokumenDukungan, JenisSurat


def dashboard(request):
    filter_params = request.GET.copy()
    filter_params.pop("provinsi", None)
    filters = parse_home_filters(filter_params)
    province_options = list(Provinsi.objects.order_by("nama"))
    requested_provinces = set(request.GET.getlist("provinsi"))
    selected_provinces = [
        province.kode for province in province_options if province.kode in requested_provinces
    ]
    schools = Sekolah.objects.select_related("provinsi", "kabkota").prefetch_related(
        "dokumen_dukungan"
    )
    query = request.GET.get("q", "").strip()[:100]
    if query:
        schools = schools.filter(Q(npsn__icontains=query) | Q(nama__icontains=query))
    if selected_provinces:
        schools = schools.filter(provinsi__kode__in=selected_provinces)
    if filters.get("pengusul"):
        schools = schools.filter(pengusul=filters["pengusul"])
    schools = list(schools)

    can_view_documents = has_role(request.user, Role.VIEWER)
    documents = defaultdict(dict)
    available = set()
    for school in schools:
        for document in school.dokumen_dukungan.all():
            documents[school.pk][document.jenis] = document
            available.add((school.pk, document.jenis))

    summaries = []
    for proposer, proposer_label in Pengusul.choices:
        eligible = sum(school.pengusul == proposer for school in schools)
        for kind, title, description in (
            (
                JenisSurat.REKOMENDASI,
                f"USULAN {proposer_label.upper()}",
                "Surat rekomendasi dan dukungan",
            ),
            (
                JenisSurat.KESIAPAN,
                f"USULAN {proposer_label.upper()}",
                "Surat kesiapan dan komitmen satuan pendidikan",
            ),
        ):
            count = sum(
                (school.pk, kind) in available for school in schools if school.pengusul == proposer
            )
            summaries.append(
                {
                    "key": f"{proposer}-{kind}",
                    "title": title,
                    "description": description,
                    "eligible": eligible,
                    "available": count,
                    "missing": eligible - count,
                    "percent": round(count * 100 / eligible, 1) if eligible else 0,
                    "tone": "blue" if proposer == Pengusul.DINAS else "green",
                }
            )

    chart = _cumulative_chart(schools, documents)

    rows = []
    for school in schools:
        docs = documents[school.pk]
        cells = []
        for kind in JenisSurat.values:
            document = docs.get(kind)
            cells.append(
                {
                    "available": bool(document),
                    "url": reverse("support:open_document", args=[document.pk])
                    if document and can_view_documents
                    else None,
                    "manage_url": reverse("support:manage_document", args=[school.pk, kind])
                    if has_role(request.user, Role.ADMIN)
                    else None,
                    "label": "Lihat"
                    if can_view_documents and document
                    else "Sudah tersedia"
                    if document
                    else "Belum tersedia",
                }
            )
        rows.append({"school": school, "documents": cells})

    return render(
        request,
        "support/dashboard.html",
        {
            "rows": rows,
            "summaries": summaries,
            "q": query,
            "province_options": province_options,
            "selected_provinces": selected_provinces,
            "selected_proposer": filters.get("pengusul", ""),
            "proposer_options": Pengusul.choices,
            "can_edit": has_role(request.user, Role.ADMIN),
            "can_view_documents": can_view_documents,
            "chart": chart,
        },
    )


def _cumulative_chart(schools, documents):
    labels_by_key = {
        (Pengusul.DINAS, JenisSurat.REKOMENDASI): "Dinas · Rekomendasi",
        (Pengusul.DINAS, JenisSurat.KESIAPAN): "Dinas · Kesiapan",
        (Pengusul.MITRA, JenisSurat.REKOMENDASI): "Mitra · Rekomendasi",
        (Pengusul.MITRA, JenisSurat.KESIAPAN): "Mitra · Kesiapan",
    }
    colors = ("#4386ad", "#79b3d2", "#c56f2f", "#e8ad7b")
    events = Counter()
    for school in schools:
        for document in documents[school.pk].values():
            month = document.created_at.date().replace(day=1)
            events[(school.pengusul, document.jenis, month)] += 1
    months = sorted({month for _proposer, _kind, month in events})
    if not months:
        return {"empty": True, "labels": [], "lines": []}

    lines = []
    max_value = max(
        sum(count for (proposer, kind, _month), count in events.items() if (proposer, kind) == key)
        for key in labels_by_key
    )
    max_value = max(max_value, 1)
    for key, color in zip(labels_by_key, colors, strict=True):
        cumulative = 0
        values = []
        for month_index, month in enumerate(months):
            cumulative += events[(key[0], key[1], month)]
            x = 50 if len(months) == 1 else round(month_index * 100 / (len(months) - 1), 2)
            y = round(100 - cumulative * 90 / max_value, 2)
            values.append({"x": x, "y": y, "value": cumulative})
        points = " ".join(f"{point['x']},{point['y']}" for point in values)
        lines.append({"name": labels_by_key[key], "color": color, "points": points})
    return {
        "empty": False,
        "labels": [
            {
                "label": date_format(month, "M Y"),
                "x": 50 if len(months) == 1 else round(i * 100 / (len(months) - 1), 2),
            }
            for i, month in enumerate(months)
        ],
        "lines": lines,
    }


@require_http_methods(["GET"])
def open_document(request, pk):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('accounts:login')}?next={request.path}")
    if not has_role(request.user, Role.VIEWER):
        raise PermissionDenied
    document = get_object_or_404(DokumenDukungan.objects.select_related("sekolah"), pk=pk)
    if document.tautan_drive:
        return HttpResponseRedirect(document.tautan_drive)
    if not document.berkas:
        raise Http404("Dokumen tidak tersedia.")
    response = FileResponse(document.berkas.open("rb"), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="surat-{document.sekolah.npsn}.pdf"'
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@require_http_methods(["GET", "POST"])
def manage_document(request, school_pk, kind):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('accounts:login')}?next={request.path}")
    if not has_role(request.user, Role.ADMIN):
        raise PermissionDenied
    if kind not in JenisSurat.values:
        raise Http404("Jenis surat tidak dikenal.")
    school = get_object_or_404(Sekolah.objects.select_related("provinsi"), pk=school_pk)
    previous_document = (
        DokumenDukungan.all_objects.filter(sekolah=school, jenis=kind)
        .order_by("-updated_at", "-pk")
        .first()
    )
    document = previous_document if previous_document and not previous_document.is_deleted else None
    if request.method == "POST" and request.POST.get("action") == "pulihkan":
        if not has_role(request.user, Role.SUPER_ADMIN):
            raise PermissionDenied
        if previous_document and previous_document.is_deleted:
            previous_document.restore()
            messages.success(request, "Dokumen surat berhasil dipulihkan.")
        return redirect("support:dashboard")
    if request.method == "POST" and request.POST.get("action") == "hapus":
        if document:
            document.soft_delete(request.user)
            messages.success(request, "Dokumen surat ditandai belum tersedia.")
        return redirect("support:dashboard")

    form = DokumenDukunganForm(
        request.POST or None,
        request.FILES or None,
        instance=document or DokumenDukungan(sekolah=school, jenis=kind),
        school=school,
        kind=kind,
    )
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.sekolah = school
        saved.jenis = kind
        saved.full_clean()
        saved.save()
        messages.success(request, "Dokumen surat berhasil disimpan.")
        return redirect("support:dashboard")
    return render(
        request,
        "support/manage_document.html",
        {
            "form": form,
            "school": school,
            "kind_label": JenisSurat(kind).label,
            "document": document,
            "previous_document": previous_document
            if previous_document and previous_document.is_deleted
            else None,
        },
    )
