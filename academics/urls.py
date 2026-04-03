from django.urls import path

from . import views

app_name = "academics"

urlpatterns = [
    path("annees/", views.AnneeListView.as_view(), name="annee_list"),
    path("annees/<uuid:pk>/", views.AnneeDetailView.as_view(), name="annee_detail"),
    path("enseignement/", views.TeachingOverviewView.as_view(), name="teaching_overview"),
    path("annees/nouvelle/", views.AnneeCreateView.as_view(), name="annee_create"),
    path("annees/<uuid:pk>/modifier/", views.AnneeUpdateView.as_view(), name="annee_update"),
    path("annees/<uuid:pk>/supprimer/", views.AnneeDeleteView.as_view(), name="annee_delete"),
    path("annees/<uuid:pk>/activer/", views.set_active_year, name="annee_set_active"),
    path("formations/", views.FormationListView.as_view(), name="formation_list"),
    path("formations/nouvelle/", views.FormationCreateView.as_view(), name="formation_create"),
    path("formations/<uuid:pk>/", views.FormationDetailView.as_view(), name="formation_detail"),
    path("formations/<uuid:pk>/modifier/", views.FormationUpdateView.as_view(), name="formation_update"),
    path("formations/<uuid:pk>/supprimer/", views.FormationDeleteView.as_view(), name="formation_delete"),
    path("ues/", views.UEListView.as_view(), name="ue_list"),
    path("ues/nouvelle/", views.UECreateView.as_view(), name="ue_create"),
    path("ues/<uuid:pk>/modifier/", views.UEUpdateView.as_view(), name="ue_update"),
    path("ues/<uuid:pk>/supprimer/", views.UEDeleteView.as_view(), name="ue_delete"),
]
