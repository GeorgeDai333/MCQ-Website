from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import Http404


def teacher_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Login required.")
        profile = getattr(request.user, "profile", None)
        if profile is None or not profile.is_teacher:
            raise PermissionDenied("Teacher access required.")
        return view_func(request, *args, **kwargs)

    return wrapper


def teacher_or_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Login required.")
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        profile = getattr(request.user, "profile", None)
        if profile is None or not profile.is_teacher:
            raise PermissionDenied("Teacher or admin access required.")
        return view_func(request, *args, **kwargs)

    return wrapper


def require_quiz_owner(quiz, user):
    if quiz.owner_id != user.id:
        raise Http404("Quiz not found.")


def require_attempt_owner(attempt, user):
    if attempt.student_id != user.id:
        raise Http404("Attempt not found.")
