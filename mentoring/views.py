from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User

from . import services
from .forms import EndReasonForm, MentorFilterForm, MentorForm
from .models import MentorProfile, MentoringRelationship
from .services import MentoringError

RANDOM_PICKS = 3


def _mentoring_context(user):
    return {
        "mentor_profile": services.mentor_profile(user),
        "mentor_rel": services.current_mentor_relationship(user),
        "mentee_rels": list(services.current_mentee_relationships(user)),
    }


def home(request):
    return render(request, "mentoring/home.html", _mentoring_context(request.user))


def mentor_list(request):
    form = MentorFilterForm(request.GET or None)
    filters = form.cleaned_data if form.is_valid() else {}
    random_pick = "random" in request.GET
    if random_pick:
        mentors = services.available_mentors(request.user)[:RANDOM_PICKS]
    else:
        mentors = services.available_mentors(
            request.user, research=filters.get("research"), stage=filters.get("stage")
        )
    return render(
        request,
        "mentoring/mentor_list.html",
        {
            "form": form,
            "mentors": mentors,
            "random_pick": random_pick,
            "filtered": any(filters.values()),
            "mentor_rel": services.current_mentor_relationship(request.user),
        },
    )


def mentor_detail(request, pk):
    profile = get_object_or_404(
        MentorProfile.objects.select_related("user").exclude(status=MentorProfile.Status.LEFT),
        user_id=pk,
        user__is_active=True,
    )
    mentor_rel = services.current_mentor_relationship(request.user)
    return render(
        request,
        "mentoring/mentor_detail.html",
        {
            "profile": profile,
            "mentor_rel": mentor_rel,
            "is_self": profile.user_id == request.user.pk,
            "is_my_mentor": bool(mentor_rel and mentor_rel.mentor_id == profile.user_id),
        },
    )


@require_POST
def choose_mentor(request, pk):
    mentor = get_object_or_404(User, pk=pk, is_active=True)
    try:
        services.choose_mentor(request.user, mentor)
    except MentoringError as error:
        messages.error(request, str(error))
        return redirect("mentoring:mentor_list")
    messages.success(
        request,
        f"🎉 {mentor.first_name} is now your mentor and has been notified that you chose them.",
    )
    return redirect("mentoring:profile")


def mentor_join(request):
    profile = services.mentor_profile(request.user)
    # Pre-fill with earlier answers when someone rejoins the pool.
    instance = MentorProfile.objects.filter(user=request.user).first()
    form = MentorForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        try:
            services.become_mentor(request.user, **form.cleaned_data)
        except MentoringError as error:
            form.add_error("capacity", str(error))
        else:
            if profile:
                messages.success(request, "Mentoring settings updated.")
            else:
                messages.success(request, "🎉 You're now available as a mentor. Thank you!")
            return redirect("mentoring:profile")
    return render(request, "mentoring/mentor_join.html", {"form": form, "mentor_profile": profile})


def profile(request):
    context = _mentoring_context(request.user)
    context["has_history"] = MentoringRelationship.objects.filter(
        Q(mentor=request.user) | Q(mentee=request.user), status=MentoringRelationship.Status.ENDED
    ).exists()
    return render(request, "mentoring/profile.html", context)


def end_relationship(request, pk):
    rel = get_object_or_404(
        MentoringRelationship.objects.filter(Q(mentor=request.user) | Q(mentee=request.user)),
        pk=pk,
        status=MentoringRelationship.Status.ACTIVE,
    )
    other = rel.other_party(request.user)
    form = EndReasonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        services.end_relationship(rel, request.user, form.cleaned_data["reason"])
        messages.info(request, f"Your mentoring relationship with {other.first_name} has ended.")
        return redirect("mentoring:profile")
    return render(
        request,
        "mentoring/confirm.html",
        {
            "title": "End this mentoring relationship?",
            "body": (
                f"Your mentoring relationship with {other} will end and {other.first_name} will be "
                "notified. Either person can end a mentoring relationship at any time. "
                "You don't need to give a reason."
            ),
            "form": form,
            "confirm_label": "End relationship",
            "cancel_label": "Keep relationship",
        },
    )


@require_POST
def pause_mentoring(request):
    services.pause_mentoring(request.user)
    messages.info(request, "Mentoring paused. You won't appear to people looking for a mentor.")
    return redirect("mentoring:profile")


@require_POST
def resume_mentoring(request):
    services.resume_mentoring(request.user)
    messages.success(request, "You're available as a mentor again.")
    return redirect("mentoring:profile")


def stop_mentoring(request):
    if services.mentor_profile(request.user) is None:
        return redirect("mentoring:profile")
    if request.method == "POST":
        services.stop_mentoring(request.user)
        messages.info(request, "You are no longer a mentor. You can come back any time.")
        return redirect("mentoring:profile")
    return render(
        request,
        "mentoring/confirm.html",
        {
            "title": "Stop being a mentor?",
            "body": "You'll be removed from the mentor list. You can become a mentor again whenever you like.",
            "affected": [r.mentee for r in services.current_mentee_relationships(request.user)],
            "affected_intro": "This will end your mentoring relationship with:",
            "confirm_label": "Stop mentoring",
            "cancel_label": "Keep mentoring",
        },
    )


def leave_program(request):
    if request.method == "POST":
        services.leave_program(request.user)
        messages.info(request, "You've left the mentoring program. You're welcome back any time.")
        return redirect("mentoring:profile")
    affected = [r.mentee for r in services.current_mentee_relationships(request.user)]
    mentor_rel = services.current_mentor_relationship(request.user)
    if mentor_rel:
        affected.insert(0, mentor_rel.mentor)
    return render(
        request,
        "mentoring/confirm.html",
        {
            "title": "Leave the mentoring program?",
            "body": (
                "You'll be removed from the mentor list and all your current mentoring "
                "relationships will end. Your account stays, so you can return whenever you like."
            ),
            "affected": affected,
            "affected_intro": "This will end your mentoring relationship with:",
            "confirm_label": "Leave program",
            "cancel_label": "Stay",
        },
    )


def notifications(request):
    items = list(request.user.notifications.all()[:50])
    unread_ids = {n.pk for n in items if n.read_at is None}
    request.user.notifications.filter(read_at__isnull=True).update(read_at=timezone.now())
    return render(request, "mentoring/notifications.html", {"items": items, "unread_ids": unread_ids})


def history(request):
    rels = MentoringRelationship.objects.filter(
        Q(mentor=request.user) | Q(mentee=request.user)
    ).select_related("mentor", "mentee")
    return render(request, "mentoring/history.html", {"rels": rels})


@staff_member_required
def staff_dashboard(request):
    active = Q(user__mentoring_as_mentor__status=MentoringRelationship.Status.ACTIVE)
    mentors = (
        MentorProfile.objects.exclude(status=MentorProfile.Status.LEFT)
        .select_related("user")
        .annotate(n_active=Count("user__mentoring_as_mentor", filter=active))
        .order_by("user__full_name")
    )
    events = []
    for rel in MentoringRelationship.objects.select_related("mentor", "mentee")[:50]:
        events.append((rel.started_at, f"{rel.mentee} matched with {rel.mentor}"))
        if rel.ended_at:
            events.append((rel.ended_at, f"{rel.mentee} / {rel.mentor} relationship ended"))
    events.sort(key=lambda event: event[0], reverse=True)
    return render(
        request,
        "mentoring/staff_dashboard.html",
        {
            "n_participants": User.objects.filter(is_active=True).count(),
            "n_pending": User.objects.filter(is_active=True, last_login__isnull=True).count(),
            "mentors": mentors,
            "n_active_rels": MentoringRelationship.objects.filter(
                status=MentoringRelationship.Status.ACTIVE
            ).count(),
            "events": events[:15],
        },
    )
