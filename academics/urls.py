from django.urls import path
from . import views

app_name = "academics"

urlpatterns = [
    path("annees/", views.AnneeListView.as_view(), name="annee_list"),
    path("annees/nouvelle/", views.AnneeCreateView.as_view(), name="annee_create"),
    path("annees/<uuid:pk>/modifier/", views.AnneeUpdateView.as_view(), name="annee_update"),
    path("annees/<uuid:pk>/supprimer/", views.AnneeDeleteView.as_view(), name="annee_delete"),
    path("annees/<uuid:pk>/activer/", views.set_active_year, name="annee_set_active"),
    path("ues/", views.UEListView.as_view(), name="ue_list"),
    path("ues/nouvelle/", views.UECreateView.as_view(), name="ue_create"),
    path("ues/<uuid:pk>/modifier/", views.UEUpdateView.as_view(), name="ue_update"),
    path("ues/<uuid:pk>/supprimer/", views.UEDeleteView.as_view(), name="ue_delete"),
    path("ups/", views.UPListView.as_view(), name="up_list"),
    path("ups/nouvelle/", views.UPCreateView.as_view(), name="up_create"),
    path("ups/<uuid:pk>/modifier/", views.UPUpdateView.as_view(), name="up_update"),
    path("ups/<uuid:pk>/supprimer/", views.UPDeleteView.as_view(), name="up_delete"),
]
