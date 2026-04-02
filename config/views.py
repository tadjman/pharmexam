from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.utils import timezone
from django.views.generic import TemplateView

from academics.models import AnneeUniversitaire, Formation
from assignments.models import Surveillance
from exams.models import Examen, SessionExamen, StatutExamen
from rooms.models import Salle


def get_active_year(request):
    year_id = request.session.get("active_year_id")
    if year_id:
        return AnneeUniversitaire.objects.filter(pk=year_id).first()
    return AnneeUniversitaire.objects.filter(is_active=True).first()


class TableauDeBordView(LoginRequiredMixin, TemplateView):
    template_name = "pages/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        active_year = get_active_year(self.request)
        ctx["active_year"] = active_year

        sessions = SessionExamen.objects.none()
        formations = Formation.objects.none()
        exams = Examen.objects.none()
        surveillances = Surveillance.objects.none()
        upcoming_exams = []
        exams_by_status = {
            StatutExamen.INITIE: 0,
            StatutExamen.INCOMPLET: 0,
            StatutExamen.COMPLET: 0,
            StatutExamen.TERMINE: 0,
        }

        if active_year:
            formations = Formation.objects.filter(annee_universitaire=active_year).annotate(
                session_count=Count("sessions", distinct=True),
                exam_count=Count("sessions__examens", distinct=True),
            ).order_by("nom")
            sessions = SessionExamen.objects.filter(formation__annee_universitaire=active_year)
            exams = Examen.objects.filter(session__formation__annee_universitaire=active_year).select_related(
                "session",
                "session__formation",
                "ue",
            )
            for exam in exams:
                exam.update_statut(save=True)
            exams = Examen.objects.filter(session__formation__annee_universitaire=active_year).select_related(
                "session",
                "session__formation",
                "ue",
            )
            surveillances = Surveillance.objects.filter(
                affectation_salle__examen__session__formation__annee_universitaire=active_year
            )
            status_counts = exams.values("statut").annotate(total=Count("id"))
            exams_by_status.update({row["statut"]: row["total"] for row in status_counts})
            now = timezone.now()
            upcoming_exams = [
                exam for exam in exams.order_by("date", "heure_debut")
                if exam.end_dt >= now
            ][:5]

        total_exams = exams.count()
        completion_rate = int((exams_by_status[StatutExamen.COMPLET] / total_exams) * 100) if total_exams else 0

        ctx["kpis"] = {
            "years": AnneeUniversitaire.objects.count(),
            "formations": formations.count(),
            "sessions": sessions.count(),
            "exams": total_exams,
            "surveillances": surveillances.count(),
            "rooms": Salle.objects.count(),
            "completion_rate": completion_rate,
            "complete": exams_by_status[StatutExamen.COMPLET],
            "incomplete": exams_by_status[StatutExamen.INCOMPLET],
            "initie": exams_by_status[StatutExamen.INITIE],
            "termine": exams_by_status[StatutExamen.TERMINE],
        }
        ctx["formations"] = formations
        ctx["upcoming_exams"] = upcoming_exams
        ctx["incomplete_exams"] = list(
            exams.filter(statut__in=[StatutExamen.INITIE, StatutExamen.INCOMPLET]).order_by("date", "heure_debut")[:5]
        ) if active_year else []
        return ctx
