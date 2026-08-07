from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import path

from .views import help as help_views
from .views import student, teacher

app_name = "quizzes"


@login_required
def dashboard(request):
    profile = getattr(request.user, "profile", None)
    if profile is not None and profile.is_teacher:
        return redirect("quizzes:teacher_dashboard")
    return redirect("quizzes:student_dashboard")


urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("help/", help_views.help_page, name="help"),
    # Teacher
    path("teacher/", teacher.teacher_dashboard, name="teacher_dashboard"),
    path("teacher/quizzes/new/", teacher.teacher_quiz_create, name="teacher_quiz_create"),
    path(
        "teacher/quizzes/<int:pk>/upload/",
        teacher.teacher_quiz_upload,
        name="teacher_quiz_upload",
    ),
    path(
        "teacher/quizzes/<int:pk>/review/",
        teacher.teacher_quiz_review,
        name="teacher_quiz_review",
    ),
    path(
        "teacher/quizzes/<int:pk>/edit/",
        teacher.teacher_quiz_edit,
        name="teacher_quiz_edit",
    ),
    path(
        "teacher/quizzes/<int:pk>/delete/",
        teacher.teacher_quiz_delete,
        name="teacher_quiz_delete",
    ),
    path(
        "teacher/quizzes/<int:pk>/export.csv",
        teacher.teacher_quiz_export_csv,
        name="teacher_quiz_export_csv",
    ),
    path(
        "teacher/quizzes/<int:pk>/export.docx",
        teacher.teacher_quiz_export_docx,
        name="teacher_quiz_export_docx",
    ),
    path(
        "teacher/quizzes/<int:pk>/students/",
        teacher.teacher_quiz_students,
        name="teacher_quiz_students",
    ),
    path(
        "teacher/quizzes/<int:pk>/students/<int:student_id>/grant-retake/",
        teacher.teacher_grant_retake,
        name="teacher_grant_retake",
    ),
    # Student
    path(
        "student/quizzes/<int:pk>/start/",
        student.student_start_attempt,
        name="student_start_attempt",
    ),
    path("student/", student.student_dashboard, name="student_dashboard"),
    path(
        "student/attempts/<int:pk>/",
        student.student_take_attempt,
        name="student_take_attempt",
    ),
    path(
        "student/attempts/<int:pk>/autosave/",
        student.student_autosave_attempt,
        name="student_autosave_attempt",
    ),
    path(
        "student/attempts/<int:pk>/submit/",
        student.student_submit_attempt,
        name="student_submit_attempt",
    ),
    path(
        "student/attempts/<int:pk>/results/",
        student.student_attempt_results,
        name="student_attempt_results",
    ),
]
