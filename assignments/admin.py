from django.contrib import admin

from .models import Surveillance


@admin.register(Surveillance)
class SurveillanceAdmin(admin.ModelAdmin):
    list_display = ("surveillant", "examen", "get_session", "get_annee", "created_at")
    list_filter = ("examen__session__annee_universitaire", "examen__session", "examen", "surveillant")
    search_fields = ("surveillant__username", "examen__nom", "examen__session__nom")
    autocomplete_fields = ("surveillant", "examen")

    @admin.display(ordering="examen__session", description="Session")
    def get_session(self, obj):
        return obj.examen.session

    @admin.display(ordering="examen__session__annee_universitaire", description="Année")
    def get_annee(self, obj):
        return obj.examen.session.annee_universitaire
