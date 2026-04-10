from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User

    list_display = ("username", "email", "role", "up", "is_staff", "is_superuser", "is_active")
    list_filter = ("role", "up", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email", "first_name", "last_name", "up__nom")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Informations personnelles"), {"fields": ("first_name", "last_name", "email")}),
        (_("Rôle"), {"fields": ("role", "up")}),
        (
            _("Permissions"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (_("Dates importantes"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "role", "up", "password1", "password2", "is_staff", "is_superuser", "is_active"),
        }),
    )
