from django.shortcuts import redirect
from django.urls import reverse

# Paths a not-yet-onboarded user must still be able to reach: the profile
# setup page itself, logout, static files, and Django admin (superusers
# managing the allowlist shouldn't be blocked by student/teacher onboarding).
EXEMPT_PREFIXES = ("/admin/", "/static/", "/accounts/")


class RequireProfileSetupMiddleware:
    """Forces every authenticated user to confirm their username and real
    name before reaching any other page, not just right after login --
    otherwise navigating away from the complete-profile page (back button,
    a bookmark) would skip it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and not user.is_superuser
            and not request.path.startswith(EXEMPT_PREFIXES)
        ):
            profile = getattr(user, "profile", None)
            if profile is not None and not profile.onboarding_completed:
                return redirect(reverse("accounts:complete_profile"))
        return self.get_response(request)
