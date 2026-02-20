from django.urls import path
from . import views

app_name = "academics"

urlpatterns = [
    path("annees/", views.AnneeListView.as_view(), name="annee_list"),
    path("annees/nouvelle/", views.AnneeCreateView.as_view(), name="annee_create"),
    path("annees/<uuid:pk>/modifier/", views.AnneeUpdateView.as_view(), name="annee_update"),
    path("annees/<uuid:pk>/supprimer/", views.AnneeDeleteView.as_view(), name="annee_delete"),
    path("annees/<uuid:pk>/activer/", views.set_active_year, name="annee_set_active"),
]
