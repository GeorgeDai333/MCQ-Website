from allauth.account.signals import user_signed_up
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile, TeacherAllowlistEntry

User = get_user_model()


@receiver(post_save, sender=User)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    """Every User gets a Profile, defaulting to student.

    This covers users created outside the Google-login flow too (e.g. via
    createsuperuser), so `request.user.profile` is always safe to access.
    """
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(user_signed_up)
def assign_role_from_allowlist(request, user, **kwargs):
    """On first login (via allauth, e.g. Google), set role from the
    TeacherAllowlistEntry table. Role is otherwise immutable via any
    user-facing UI, though it is re-synced against the allowlist on every
    login in accounts.views.post_login_redirect (so being added to the
    allowlist after signup still takes effect).
    """
    profile, _ = Profile.objects.get_or_create(user=user)
    email = (user.email or "").strip().lower()
    if email and TeacherAllowlistEntry.objects.filter(email=email).exists():
        profile.role = Profile.ROLE_TEACHER
    else:
        profile.role = Profile.ROLE_STUDENT
    profile.save(update_fields=["role"])
