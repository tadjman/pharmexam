from django.contrib import admin

from .models import AnneeUniversitaire, Formation, UE, UP


@admin.register(AnneeUniversitaire)
class AnneeUniversitaireAdmin(admin.ModelAdmin):
    list_display = ("nom", "date_debut", "date_fin", "is_active")
    list_filter = ("is_active",)
    search_fields = ("nom",)
    ordering = ("-date_debut",)
    fields = ("date_debut", "date_fin", "is_active")


@admin.register(Formation)
class FormationAdmin(admin.ModelAdmin):
    list_display = ("nom", "annee_universitaire")
    list_filter = ("annee_universitaire",)
    search_fields = ("nom", "annee_universitaire__nom")
    autocomplete_fields = ("annee_universitaire",)


@admin.register(UE)
class UEAdmin(admin.ModelAdmin):
    list_display = ("code_ue", "nom", "formation")
    search_fields = ("code_ue", "nom", "formation__nom")
    autocomplete_fields = ("formation",)
    filter_horizontal = ("ups",)


@admin.register(UP)
class UPAdmin(admin.ModelAdmin):
    list_display = ("nom",)
    search_fields = ("nom",)
