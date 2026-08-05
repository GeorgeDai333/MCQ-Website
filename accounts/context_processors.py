import os


def admin_test_credentials(request):
    """Surface the admin login credentials on the admin login page during
    the testing phase. Reads the same DJANGO_SUPERUSER_* env vars that
    ensure_superuser.py provisions the account from, so the banner never
    drifts from what's actually configured to log in.
    """
    return {
        "admin_test_username": os.environ.get("DJANGO_SUPERUSER_USERNAME", ""),
        "admin_test_password": os.environ.get("DJANGO_SUPERUSER_PASSWORD", ""),
    }
