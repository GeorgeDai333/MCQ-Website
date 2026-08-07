from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("login/student/", views.student_login, name="student_login"),
    path("login/teacher/", views.teacher_login, name="teacher_login"),
    path("post-login/", views.post_login_redirect, name="post_login_redirect"),
    path("complete-profile/", views.complete_profile, name="complete_profile"),
]
