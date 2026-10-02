from django.shortcuts import redirect
from django.urls import reverse


class ProfileCompletionMiddleware:
    """Send signed-in participants to the welcome step until their profile is filled in."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and not user.profile_completed:
            exempt = (
                reverse("accounts:welcome"),
                reverse("accounts:logout"),
                reverse("admin:index"),
                "/static/",
                "/media/",
            )
            if not request.path.startswith(exempt):
                return redirect("accounts:welcome")
        return self.get_response(request)
