from django.urls import path

from . import views

app_name = "rooms"

urlpatterns = [
    path("salles/", views.SalleListView.as_view(), name="salle_list"),
    path("salles/nouvelle/", views.SalleCreateView.as_view(), name="salle_create"),
    path("salles/<uuid:pk>/modifier/", views.SalleUpdateView.as_view(), name="salle_update"),
    path("salles/<uuid:pk>/supprimer/", views.SalleDeleteView.as_view(), name="salle_delete"),
    path("examens/<uuid:exam_pk>/salles/", views.AffectationListView.as_view(), name="affectation_list"),
    path("examens/<uuid:exam_pk>/salles/nouvelle/", views.AffectationCreateView.as_view(), name="affectation_create"),
    path(
        "examens/<uuid:exam_pk>/salles/<uuid:pk>/modifier/",
        views.AffectationUpdateView.as_view(),
        name="affectation_update",
    ),
    path(
        "examens/<uuid:exam_pk>/salles/<uuid:pk>/supprimer/",
        views.AffectationDeleteView.as_view(),
        name="affectation_delete",
    ),
]
