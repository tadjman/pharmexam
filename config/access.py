from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import render


ACCESS_DENIED_MESSAGE = (
    "Désolé vous n'avez pas accès à cette page, veuillez vous referer "
    "a un membre du personnel scolarité ou au service informatique."
)


def is_scolarite_or_admin(user):
    return user.is_authenticated and (
        user.is_superuser or user.is_staff or getattr(user, "role", "") == "SCOLARITE"
    )


def render_access_denied(request, *, status=403):
    active_year = None
    year_id = request.session.get("active_year_id")
    if year_id:
        from academics.models import AnneeUniversitaire

        active_year = AnneeUniversitaire.objects.filter(pk=year_id).first()
    return render(
        request,
        "errors/access_denied.html",
        {
            "active_year": active_year,
            "access_denied_message": ACCESS_DENIED_MESSAGE,
        },
        status=status,
    )


class ScolariteOrAdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return is_scolarite_or_admin(self.request.user)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        return render_access_denied(self.request, status=403)
