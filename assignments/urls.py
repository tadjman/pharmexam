from django.urls import path

from . import views

app_name = "assignments"

urlpatterns = [
    path("surveillances/", views.SurveillanceListView.as_view(), name="surveillance_list"),
    path("surveillances/nouvelle/", views.SurveillanceCreateView.as_view(), name="surveillance_create"),
    path("surveillances/<uuid:pk>/supprimer/", views.SurveillanceDeleteView.as_view(), name="surveillance_delete"),
    path("examens/<uuid:exam_pk>/surveillances/", views.exam_surveillance_redirect, name="exam_surveillance_redirect"),
]
