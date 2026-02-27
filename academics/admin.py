from django.contrib import admin

from .models import AnneeUniversitaire, UE, UP


@admin.register(AnneeUniversitaire)
class AnneeUniversitaireAdmin(admin.ModelAdmin):
    list_display = ("nom", "date_debut", "date_fin", "is_active")
    list_filter = ("is_active",)
    search_fields = ("nom",)
    ordering = ("-date_debut",)


@admin.register(UE)
class UEAdmin(admin.ModelAdmin):
    list_display = ("nom",)
    search_fields = ("nom",)
    filter_horizontal = ("responsables",)


@admin.register(UP)
class UPAdmin(admin.ModelAdmin):
    list_display = ("nom", "ue", "matiere")
    list_filter = ("ue",)
    search_fields = ("nom", "matiere", "ue__nom")
    autocomplete_fields = ("ue",)
    filter_horizontal = ("responsables",)
