from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.models import Role
from apps.accounts.permissions import has_role

from .forms import VideoPraktikForm
from .models import KerangkaPraktik, VideoPraktik


@login_required
@require_http_methods(["GET"])
def video_list(request):
    if not has_role(request.user, Role.VIEWER):
        raise PermissionDenied

    videos = VideoPraktik.objects.select_related("sekolah", "sekolah__provinsi", "sekolah__kabkota")
    if not has_role(request.user, Role.ADMIN):
        videos = videos.filter(dipublikasikan=True)
    framework = request.GET.get("kerangka", "")
    if framework in KerangkaPraktik.values:
        videos = videos.filter(kerangka=framework)
    query = request.GET.get("q", "").strip()[:100]
    if query:
        videos = videos.filter(sekolah__nama__icontains=query) | videos.filter(
            judul__icontains=query
        )
    return render(
        request,
        "galeri/list.html",
        {
            "videos": videos,
            "query": query,
            "framework": framework,
            "frameworks": KerangkaPraktik.choices,
            "can_manage": has_role(request.user, Role.ADMIN),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def video_manage(request, pk=None):
    if not has_role(request.user, Role.ADMIN):
        raise PermissionDenied
    video = get_object_or_404(VideoPraktik, pk=pk) if pk is not None else VideoPraktik()
    form = VideoPraktikForm(request.POST or None, instance=video)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved._history_user = request.user
        saved._change_reason = "Kelola video praktik baik"
        saved.full_clean()
        saved.save()
        messages.success(request, "Video praktik baik berhasil disimpan.")
        return redirect("galeri:list")
    return render(
        request,
        "galeri/form.html",
        {"form": form, "video": video, "is_update": bool(video.pk)},
    )


@login_required
@require_http_methods(["POST"])
def video_delete(request, pk):
    if not has_role(request.user, Role.ADMIN):
        raise PermissionDenied
    video = get_object_or_404(VideoPraktik, pk=pk)
    video.soft_delete(request.user)
    messages.success(request, "Video praktik baik dihapus dari galeri.")
    return redirect("galeri:list")
