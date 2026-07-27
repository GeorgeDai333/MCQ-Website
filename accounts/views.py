from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from .models import Profile, TeacherAllowlistEntry

INTENT_SESSION_KEY = "login_intent"


def landing(request):
    if request.user.is_authenticated:
        return redirect("accounts:post_login_redirect")
    return render(request, "accounts/landing.html")


def student_login(request):
    request.session[INTENT_SESSION_KEY] = Profile.ROLE_STUDENT
    return redirect(reverse("google_login"))


def teacher_login(request):
    request.session[INTENT_SESSION_KEY] = Profile.ROLE_TEACHER
    return redirect(reverse("google_login"))


@login_required
def post_login_redirect(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    intent = request.session.pop(INTENT_SESSION_KEY, None)

    # Re-check the allowlist on every login (not just signup), so a user who
    # signed up before their email was added to the allowlist still gets
    # promoted once an admin adds them.
    if profile.role != Profile.ROLE_TEACHER:
        email = (request.user.email or "").strip().lower()
        if email and TeacherAllowlistEntry.objects.filter(email=email).exists():
            profile.role = Profile.ROLE_TEACHER
            profile.save(update_fields=["role"])

    if intent == Profile.ROLE_TEACHER and profile.role != Profile.ROLE_TEACHER:
        messages.info(
            request,
            "This Google account isn't approved as a teacher yet, so you've "
            "been signed in as a student. Ask an administrator to add your "
            "email to the teacher allowlist if this is unexpected.",
        )

    if profile.role == Profile.ROLE_TEACHER:
        return redirect("quizzes:teacher_dashboard")
    return redirect("quizzes:student_dashboard")
