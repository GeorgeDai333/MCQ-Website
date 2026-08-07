from django.conf import settings
from django.db import models


class TeacherAllowlistEntry(models.Model):
    """Emails pre-approved to receive the teacher role on first login.

    Managed exclusively through Django admin -- there is no student/teacher
    facing UI to add to this table, since anyone able to add themselves
    would defeat the point of gating the teacher role.
    """

    email = models.EmailField(unique=True, db_index=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Teacher allowlist entry"
        verbose_name_plural = "Teacher allowlist entries"

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class Profile(models.Model):
    ROLE_STUDENT = "student"
    ROLE_TEACHER = "teacher"
    ROLE_CHOICES = [
        (ROLE_STUDENT, "Student"),
        (ROLE_TEACHER, "Teacher"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="profile",
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_STUDENT)
    onboarding_completed = models.BooleanField(
        default=False,
        help_text="Set once the user has confirmed their username and real name.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} ({self.role})"

    @property
    def is_teacher(self):
        return self.role == self.ROLE_TEACHER
