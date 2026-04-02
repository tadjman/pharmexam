from django.contrib import admin

from .models import Surveillance


@admin.register(Surveillance)
class SurveillanceAdmin(admin.ModelAdmin):
    list_display = (
        "surveillant",
        "get_salle",
        "get_examen",
        "is_responsable_general",
        "is_responsable_salle",
        "get_session",
        "get_formation",
        "get_annee",
        "created_at",
    )
    list_filter = (
        "affectation_salle__examen__session__formation__annee_universitaire",
        "affectation_salle__examen__session__formation",
        "affectation_salle__examen__session",
        "affectation_salle__examen",
        "affectation_salle__salle",
        "is_responsable_general",
        "is_responsable_salle",
        "surveillant",
    )
    search_fields = (
        "surveillant__username",
        "affectation_salle__examen__nom",
        "affectation_salle__examen__session__nom",
        "affectation_salle__salle__nom",
    )
    autocomplete_fields = ("surveillant", "affectation_salle")

    @admin.display(ordering="affectation_salle__salle", description="Salle")
    def get_salle(self, obj):
        return obj.affectation_salle.salle

    @admin.display(ordering="affectation_salle__examen", description="Examen")
    def get_examen(self, obj):
        return obj.affectation_salle.examen

    @admin.display(ordering="affectation_salle__examen__session", description="Session")
    def get_session(self, obj):
        return obj.affectation_salle.examen.session

    @admin.display(ordering="affectation_salle__examen__session__formation", description="Formation")
    def get_formation(self, obj):
        return obj.affectation_salle.examen.session.formation

    @admin.display(ordering="affectation_salle__examen__session__formation__annee_universitaire", description="Année")
    def get_annee(self, obj):
        return obj.affectation_salle.examen.session.formation.annee_universitaire
