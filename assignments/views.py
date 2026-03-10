from django.shortcuts import redirect


def assignments_root_redirect(request):
    return redirect("exams:exam_list")
