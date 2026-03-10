from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("suivi/", views.ActivityReportView.as_view(), name="activity_report"),
    path("exports/", views.ExportCenterView.as_view(), name="export_center"),
    path("suivi/export/annee/", views.YearExportView.as_view(), name="export_year"),
    path("suivi/export/session/<uuid:pk>/", views.SessionExportView.as_view(), name="export_session"),
    path("exports/examens/annee/", views.ExamYearExportView.as_view(), name="export_exam_year"),
    path("exports/examens/session/<uuid:pk>/", views.ExamSessionExportView.as_view(), name="export_exam_session"),
]
