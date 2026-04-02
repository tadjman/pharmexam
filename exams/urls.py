from django.urls import path
from . import views

app_name = "exams"

urlpatterns = [
    path("sessions/", views.SessionListView.as_view(), name="session_list"),
    path("sessions/nouvelle/", views.SessionCreateView.as_view(), name="session_create"),
    path("sessions/<uuid:pk>/modifier/", views.SessionUpdateView.as_view(), name="session_update"),
    path("sessions/<uuid:pk>/supprimer/", views.SessionDeleteView.as_view(), name="session_delete"),

    path("examens/", views.ExamListView.as_view(), name="exam_list"),
    path("examens/nouveau/", views.ExamCreateView.as_view(), name="exam_create"),
    path("examens/<uuid:pk>/", views.ExamDetailView.as_view(), name="exam_detail"),
    path("examens/<uuid:pk>/completer/", views.ExamCompleteView.as_view(), name="exam_complete"),
    path("examens/<uuid:pk>/completer/salles/ajouter/", views.ExamRoomCreateView.as_view(), name="exam_room_create"),
    path("examens/<uuid:pk>/completer/salles/<uuid:room_pk>/modifier/", views.ExamRoomUpdateView.as_view(), name="exam_room_update"),
    path("examens/<uuid:pk>/completer/salles/<uuid:room_pk>/supprimer/", views.ExamRoomDeleteView.as_view(), name="exam_room_delete"),
    path("examens/<uuid:pk>/completer/salles/<uuid:room_pk>/inscription/", views.ExamRoomRegisterView.as_view(), name="exam_room_register"),
    path("examens/<uuid:pk>/completer/surveillances/<uuid:surveillance_pk>/supprimer/", views.ExamSurveillanceDeleteView.as_view(), name="exam_surveillance_delete"),
    path("examens/<uuid:pk>/completer/surveillances/<uuid:surveillance_pk>/responsabilites/", views.ExamSurveillanceResponsibilityUpdateView.as_view(), name="exam_surveillance_responsibility"),
    path("examens/<uuid:pk>/modifier/", views.ExamUpdateView.as_view(), name="exam_update"),
    path("examens/<uuid:pk>/supprimer/", views.ExamDeleteView.as_view(), name="exam_delete"),
]
