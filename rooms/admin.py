from django.contrib import admin

from .models import AffectationSalle, Salle


@admin.register(Salle)
class SalleAdmin(admin.ModelAdmin):
    list_display = ("nom", "capacite")
    search_fields = ("nom",)
    fields = ("nom", "capacite")


@admin.register(AffectationSalle)
class AffectationSalleAdmin(admin.ModelAdmin):
    list_display = ("examen", "salle", "temps_majore", "nb_surveillants_requis")
    list_filter = ("temps_majore",)
    search_fields = ("examen__nom", "salle__nom")
