from django.urls import path
from . import views

app_name = "exams"

urlpatterns = [
    # Sessions
    path("sessions/", views.SessionListView.as_view(), name="session_list"),
    path("sessions/nouvelle/", views.SessionCreateView.as_view(), name="session_create"),
    path("sessions/<uuid:pk>/modifier/", views.SessionUpdateView.as_view(), name="session_update"),
    path("sessions/<uuid:pk>/supprimer/", views.SessionDeleteView.as_view(), name="session_delete"),

    # Examens
    path("examens/", views.ExamListView.as_view(), name="exam_list"),
    path("examens/nouveau/", views.ExamCreateView.as_view(), name="exam_create"),
    path("examens/<uuid:pk>/", views.ExamDetailView.as_view(), name="exam_detail"),
    path("examens/<uuid:pk>/modifier/", views.ExamUpdateView.as_view(), name="exam_update"),
    path("examens/<uuid:pk>/supprimer/", views.ExamDeleteView.as_view(), name="exam_delete"),
]