from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from django.contrib import admin
from django.contrib.auth.models import Group

from .models import Profile, TeacherAllowlistEntry

# Unregister built-in/allauth admin sections that aren't meant to be hand-edited
# here: Groups are unused by this app's permission model, and the Google
# SocialApp/SocialAccount/SocialToken rows are provisioned by the
# setup_google_app management command and allauth's login flow, not by admins
# clicking around in Django admin.
admin.site.unregister(Group)
admin.site.unregister(SocialAccount)
admin.site.unregister(SocialApp)
admin.site.unregister(SocialToken)


@admin.register(TeacherAllowlistEntry)
class TeacherAllowlistEntryAdmin(admin.ModelAdmin):
    list_display = ("email", "note", "created_at")
    search_fields = ("email", "note")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "onboarding_completed", "created_at")
    list_filter = ("role", "onboarding_completed")
    search_fields = ("user__username", "user__email")
