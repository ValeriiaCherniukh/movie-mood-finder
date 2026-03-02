import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Title, UserTitle

logger = logging.getLogger(__name__)



@login_required
def my_lists(request):
    qs = UserTitle.objects.select_related("title").filter(user=request.user)

    tabs = [
        ("planned", "Planned"),
        ("watching", "Watching"),
        ("watched", "Watched"),
        ("liked", "Liked"),
        ("disliked", "Disliked"),
    ]

    active = request.GET.get("status") or request.session.get("my_lists_active", "planned")

    # якщо статус прийшов у GET — запам’ятай його
    request.session["my_lists_active"] = active

    active_items = qs.filter(status=active)

    already = qs.values_list("title_id", flat=True)
    available_titles = Title.objects.exclude(id__in=already).order_by("name")

    return render(request, "tracker/my_lists.html", {
        "tabs": tabs,
        "active": active,
        "items": active_items,
        "available_titles": available_titles,
    })

@login_required
@require_POST
def add_to_list(request):
    title_id = request.POST.get("title_id")
    status = request.POST.get("status", "planned")

    title = get_object_or_404(Title, id=title_id)

    UserTitle.objects.update_or_create(
        user=request.user,
        title=title,
        defaults={"status": status}
    )

    return redirect(f"{reverse('my_lists')}?status={new_status}")


@login_required
@require_POST
def update_status(request, pk):
    ut = get_object_or_404(UserTitle, pk=pk, user=request.user)
    new_status = request.POST.get("status")
    if new_status:
        ut.status = new_status
        ut.save()
    return redirect("my_lists")


@login_required
@require_POST
def remove_from_list(request, pk):
    ut = get_object_or_404(UserTitle, pk=pk, user=request.user)
    ut.delete()
    return redirect("my_lists")


@login_required
@require_POST
def add_tmdb_to_list(request):
    print("=== ADD_TMDB HIT ===", flush=True)
    print("POST status =", request.POST.get("status"), flush=True)
    print("POST next   =", request.POST.get("next"), flush=True)
    print("REFERER     =", request.META.get("HTTP_REFERER"), flush=True)

    tmdb_id = request.POST.get("tmdb_id")
    name = request.POST.get("name")
    description = request.POST.get("description", "")
    poster_path = request.POST.get("poster_path", "")
    status = request.POST.get("status", "planned")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("results")

    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=False):
        next_url = reverse("results")

    if not tmdb_id or not name:
        return redirect(next_url)

    tmdb_id = int(tmdb_id)

    title, _ = Title.objects.get_or_create(
        tmdb_id=tmdb_id,
        defaults={"name": name, "description": description, "poster_path": poster_path}
    )

    ut, created = UserTitle.objects.get_or_create(
        user=request.user,
        title=title,
        defaults={"status": status}
    )

    # оновлюємо статус, якщо запис вже існував
    if not created and ut.status != status:
        ut.status = status
        ut.save(update_fields=["status"])
        action = "UPDATED"
    else:
        action = "CREATED" if created else "NO_CHANGE"

    print("POST next =", request.POST.get("next"))
    print("HTTP_REFERER =", request.META.get("HTTP_REFERER"))
    print("FINAL next_url =", next_url)
    print("ACTION =", action, "| CURRENT =", ut.status, "| REQUESTED =", status)

    logger.warning("ADD_TMDB: tmdb_id=%s status=%s created=%s next=%s",
                   tmdb_id, status, created, next_url)

    request.session["my_lists_active"] = status
    return redirect(next_url)
