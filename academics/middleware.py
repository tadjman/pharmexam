from django.shortcuts import redirect
from django.urls import reverse
from .models import AnneeUniversitaire


class RequireActiveYearMiddleware:
    """
    Si l'utilisateur est connecté, on exige une année active sélectionnée
    pour accéder au cœur de l'app.

    Exceptions : login/logout/admin + pages de gestion des années.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            path = request.path

            allowed_prefixes = (
                "/admin/",
                "/login/",
                "/logout/",
                "/annees/",  # pages années
                "/static/",
            )

            if not path.startswith(allowed_prefixes):
                year_id = request.session.get("active_year_id")
                if year_id is None:
                    # fallback DB (si une année is_active existe)
                    year = AnneeUniversitaire.objects.filter(is_active=True).first()
                    if year:
                        request.session["active_year_id"] = str(year.pk)
                    else:
                        return redirect(reverse("academics:annee_list"))

        return self.get_response(request)
