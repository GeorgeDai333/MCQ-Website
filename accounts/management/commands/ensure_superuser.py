import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Create a superuser from DJANGO_SUPERUSER_USERNAME / "
        "DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD env vars, if one "
        "doesn't already exist. Safe to run on every boot -- a no-op once "
        "the account has been created, so it doesn't clobber a password "
        "changed later via the admin."
    )

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        if not username or not password:
            self.stdout.write(
                "DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_PASSWORD not "
                "set; skipping."
            )
            return

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Superuser '{username}' already exists; skipping.")
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'."))
