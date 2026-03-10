from django.urls import path

from . import views

app_name = "rooms"

urlpatterns = [
    path("salles/", views.SalleListView.as_view(), name="salle_list"),
    path("salles/nouvelle/", views.SalleCreateView.as_view(), name="salle_create"),
    path("salles/<uuid:pk>/modifier/", views.SalleUpdateView.as_view(), name="salle_update"),
    path("salles/<uuid:pk>/supprimer/", views.SalleDeleteView.as_view(), name="salle_delete"),
]
