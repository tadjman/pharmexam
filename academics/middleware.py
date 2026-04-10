from django.shortcuts import redirect
from django.urls import reverse

from .utils import get_active_year


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
                    year = get_active_year(request, persist_session=True)
                    if year is None:
                        return redirect(reverse("academics:annee_list"))

        return self.get_response(request)
