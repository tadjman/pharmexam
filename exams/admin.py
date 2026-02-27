from django.contrib import admin

from .models import Examen, SessionExamen


@admin.register(SessionExamen)
class SessionExamenAdmin(admin.ModelAdmin):
    list_display = ("nom", "annee_universitaire", "date_debut", "date_fin")
    list_filter = ("annee_universitaire",)
    search_fields = ("nom", "annee_universitaire__nom")
    autocomplete_fields = ("annee_universitaire",)


@admin.register(Examen)
class ExamenAdmin(admin.ModelAdmin):
    list_display = (
        "nom",
        "session",
        "up",
        "responsable",
        "date",
        "heure_debut",
        "heure_fin",
        "statut",
    )
    list_filter = ("statut", "session__annee_universitaire", "session")
    search_fields = ("nom", "up__nom", "up__ue__nom", "responsable__username", "session__nom")
    autocomplete_fields = ("session", "up", "responsable")
