from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Upsert the allauth Google SocialApp and the current Site from "
        "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / SITE_DOMAIN env vars, so "
        "Google login works without a manual admin click-through in every "
        "fresh environment."
    )

    def handle(self, *args, **options):
        from allauth.socialaccount.models import SocialApp

        client_id = settings.GOOGLE_CLIENT_ID
        client_secret = settings.GOOGLE_CLIENT_SECRET
        if not client_id or not client_secret:
            raise CommandError(
                "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are not set in the environment."
            )

        site, _ = Site.objects.update_or_create(
            id=settings.SITE_ID,
            defaults={"domain": settings.SITE_DOMAIN, "name": settings.SITE_DOMAIN},
        )

        app, created = SocialApp.objects.update_or_create(
            provider="google",
            name="Google",
            defaults={"client_id": client_id, "secret": client_secret},
        )
        app.sites.set([site])

        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} Google SocialApp for site {site.domain}."))
