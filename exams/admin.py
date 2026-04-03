from django.contrib import admin

from .models import Examen, SessionExamen


@admin.register(SessionExamen)
class SessionExamenAdmin(admin.ModelAdmin):
    list_display = ("nom", "formation", "get_annee")
    list_filter = ("formation__annee_universitaire", "formation")
    search_fields = ("nom", "formation__nom", "formation__annee_universitaire__nom")
    autocomplete_fields = ("formation",)

    @admin.display(ordering="formation__annee_universitaire", description="Année")
    def get_annee(self, obj):
        return obj.formation.annee_universitaire


@admin.register(Examen)
class ExamenAdmin(admin.ModelAdmin):
    list_display = (
        "nom",
        "session",
        "get_formation",
        "ue",
        "date",
        "heure_debut",
        "heure_fin",
        "statut",
    )
    list_filter = ("statut", "session__formation__annee_universitaire", "session__formation", "session")
    search_fields = ("nom", "ue__code_ue", "ue__nom", "session__nom")
    autocomplete_fields = ("session", "ue")

    @admin.display(ordering="session__formation", description="Formation")
    def get_formation(self, obj):
        return obj.session.formation
