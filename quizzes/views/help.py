from django.shortcuts import render

from ..permissions import teacher_or_admin_required


@teacher_or_admin_required
def help_page(request):
    return render(request, "quizzes/help.html")
