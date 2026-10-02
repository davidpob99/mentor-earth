from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_not_required
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CodeForm, EmailForm, ProfileForm
from .models import LoginCode, User

SESSION_EMAIL_KEY = "login_email"


def _send_code(user):
    recent = timezone.now() - timedelta(seconds=settings.LOGIN_CODE_RESEND_SECONDS)
    if user.login_codes.filter(created_at__gte=recent, used_at__isnull=True).exists():
        return  # A code was just sent; don't spam the inbox.
    _, code = LoginCode.issue(user)
    send_mail(
        subject=f"Your mentoring sign-in code: {code}",
        message=(
            f"Hi {user.first_name},\n\n"
            f"Your sign-in code is {code}.\n"
            f"It expires in {settings.LOGIN_CODE_TTL_MINUTES} minutes.\n\n"
            "If you didn't ask for it, you can ignore this email."
        ),
        from_email=None,
        recipient_list=[user.email],
    )


@login_not_required
def login_request(request):
    if request.user.is_authenticated:
        return redirect("mentoring:home")
    form = EmailForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        user = User.objects.filter(email=email, is_active=True).first()
        if user:
            _send_code(user)
        # Same response whether or not the email is invited.
        request.session[SESSION_EMAIL_KEY] = email
        return redirect("accounts:verify")
    return render(request, "accounts/login.html", {"form": form})


@login_not_required
def login_verify(request):
    email = request.session.get(SESSION_EMAIL_KEY)
    if not email:
        return redirect("accounts:login")
    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = User.objects.filter(email=email, is_active=True).first()
        login_code = user.login_codes.first() if user else None
        if login_code and login_code.check_code(form.cleaned_data["code"]):
            del request.session[SESSION_EMAIL_KEY]
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect("mentoring:home")
        form.add_error("code", "That code is invalid or has expired.")
    return render(request, "accounts/verify.html", {"form": form, "email": email})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("accounts:login")


def welcome(request):
    if request.user.profile_completed:
        return redirect("mentoring:home")
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Welcome, {request.user.first_name}! 👋")
        return redirect("mentoring:home")
    return render(request, "accounts/welcome.html", {"form": form})


def profile_edit(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("mentoring:profile")
    return render(request, "accounts/profile_edit.html", {"form": form})
