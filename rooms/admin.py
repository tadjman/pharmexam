from django.contrib import admin

from .models import AffectationSalle, Salle


@admin.register(Salle)
class SalleAdmin(admin.ModelAdmin):
    list_display = ("nom", "capacite_max", "heure_deverrouillage", "heure_verrouillage")
    search_fields = ("nom",)


@admin.register(AffectationSalle)
class AffectationSalleAdmin(admin.ModelAdmin):
    list_display = ("examen", "salle", "is_tiers_temps", "capacite_reservee")
    list_filter = ("is_tiers_temps",)
    search_fields = ("examen__nom", "salle__nom")
