from django.core.management.base import BaseCommand

from quizzes.models import QuizAttempt
from quizzes.services.grading import ensure_not_expired


class Command(BaseCommand):
    help = (
        "Auto-submit and grade any in-progress attempt whose deadline has "
        "passed but that nobody has revisited since (expiry is normally "
        "self-healing on next touch; this catches attempts nobody ever "
        "touches again). Safe to run repeatedly, e.g. via cron."
    )

    def handle(self, *args, **options):
        stale = QuizAttempt.objects.filter(submitted_at__isnull=True)
        count = 0
        for attempt in stale:
            before = attempt.submitted_at
            ensure_not_expired(attempt)
            attempt.refresh_from_db()
            if before is None and attempt.submitted_at is not None:
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Auto-submitted {count} expired attempt(s)."))
