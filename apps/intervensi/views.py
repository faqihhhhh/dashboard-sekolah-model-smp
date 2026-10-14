from django.shortcuts import render

from apps.accounts.models import Role
from apps.accounts.permissions import has_role

from .data import FRAMEWORKS, TARGETS, intervention_data


def dashboard(request):
    framework = request.GET.get("kerangka", "pm")
    target = request.GET.get("sasaran", "kepala_sekolah")
    if framework not in FRAMEWORKS:
        framework = "pm"
    if target not in TARGETS:
        target = "kepala_sekolah"

    can_view_detail = has_role(getattr(request, "user", None), Role.VIEWER)
    context = {
        "framework": framework,
        "target": target,
        "framework_label": FRAMEWORKS[framework],
        "target_label": TARGETS[target],
        "frameworks": FRAMEWORKS.items(),
        "targets": TARGETS.items(),
        "can_view_detail": can_view_detail,
    }
    if can_view_detail:
        data = intervention_data(framework, target)
        context.update(data)
        context["category_count"] = sum(len(rows) for rows in data.values())
    return render(request, "intervensi/dashboard.html", context)
