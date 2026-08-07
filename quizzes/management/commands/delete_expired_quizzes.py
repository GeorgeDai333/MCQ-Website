from django.core.management.base import BaseCommand
from django.utils import timezone

from quizzes.models import Quiz


class Command(BaseCommand):
    help = (
        "Permanently delete quizzes (and their question banks, attempts, and "
        "results) whose teacher-set expiration time has passed. This is "
        "separate from closing_time, which only locks students out. Safe to "
        "run repeatedly, e.g. via cron."
    )

    def handle(self, *args, **options):
        expired = Quiz.objects.filter(expiration_time__lte=timezone.now())
        count = expired.count()
        titles = list(expired.values_list("title", flat=True))
        expired.delete()
        for title in titles:
            self.stdout.write(f"Deleted expired quiz: {title}")
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} expired quiz(zes)."))
