from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from accounts.models import RoleUtilisateur
from academics.utils import get_active_year
from exams.models import Examen, StatutExamen


class TableauDeBordView(LoginRequiredMixin, TemplateView):
    template_name = "pages/dashboard.html"

    status_priority = {
        StatutExamen.INCOMPLET: 0,
        StatutExamen.INITIE: 1,
        StatutExamen.COMPLET: 2,
        StatutExamen.TERMINE: 3,
    }

    status_badges = {
        StatutExamen.INITIE: "",
        StatutExamen.INCOMPLET: "badge--warning",
        StatutExamen.COMPLET: "badge--success",
        StatutExamen.TERMINE: "badge--info",
    }

    def _get_exam_missing_surveillants(self, affectations):
        return sum(
            max(0, affectation.nb_surveillants_requis - len(affectation.surveillances.all()))
            for affectation in affectations
        )

    def _build_exam_attention_item(self, exam):
        affectations = list(exam.affectations_salles.all())
        missing_surveillants = self._get_exam_missing_surveillants(affectations)
        room_count = len(affectations)
        needs_rooms = room_count == 0
        return {
            "exam": exam,
            "missing_surveillants": missing_surveillants,
            "room_count": room_count,
            "needs_rooms": needs_rooms,
            "has_missing_surveillants": missing_surveillants > 0,
            "status_badge_class": self.status_badges.get(exam.statut, ""),
            "status_priority": self.status_priority.get(exam.statut, 99),
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        active_year = get_active_year(self.request)
        ctx["active_year"] = active_year
        ctx["is_admin_scope"] = self.request.user.is_superuser or self.request.user.is_staff or (
            getattr(self.request.user, "role", "") == RoleUtilisateur.SCOLARITE
        )

        exams_by_status = {
            StatutExamen.INITIE: 0,
            StatutExamen.INCOMPLET: 0,
            StatutExamen.COMPLET: 0,
            StatutExamen.TERMINE: 0,
        }

        exams = []
        incomplete_exams = []
        formations_requiring_attention = []
        missing_surveillants_total = 0

        if active_year:
            exams = list(
                Examen.objects.filter(session__formation__annee_universitaire=active_year)
                .select_related("session", "session__formation", "ue")
                .prefetch_related("affectations_salles__surveillances")
                .order_by("date", "heure_debut", "nom")
            )
            for exam in exams:
                exam.update_statut(save=True)
                exams_by_status[exam.statut] = exams_by_status.get(exam.statut, 0) + 1

            formation_index = {}
            for exam in exams:
                if exam.statut not in {StatutExamen.INITIE, StatutExamen.INCOMPLET}:
                    continue

                attention_item = self._build_exam_attention_item(exam)
                incomplete_exams.append(attention_item)
                missing_surveillants_total += attention_item["missing_surveillants"]

                formation = exam.session.formation
                formation_entry = formation_index.setdefault(
                    formation.pk,
                    {
                        "formation": formation,
                        "session_names": set(),
                        "exam_count": 0,
                        "missing_surveillants": 0,
                    },
                )
                formation_entry["session_names"].add(exam.session.nom)
                formation_entry["exam_count"] += 1
                formation_entry["missing_surveillants"] += attention_item["missing_surveillants"]

            formations_requiring_attention = sorted(
                [
                    {
                        "formation": entry["formation"],
                        "session_count": len(entry["session_names"]),
                        "exam_count": entry["exam_count"],
                        "missing_surveillants": entry["missing_surveillants"],
                    }
                    for entry in formation_index.values()
                ],
                key=lambda item: (
                    -item["missing_surveillants"],
                    -item["exam_count"],
                    item["formation"].nom.lower(),
                ),
            )

            incomplete_exams.sort(
                key=lambda item: (
                    item["status_priority"],
                    -(1 if item["has_missing_surveillants"] else 0),
                    -item["missing_surveillants"],
                    item["exam"].date,
                    item["exam"].heure_debut,
                    item["exam"].nom.lower(),
                )
            )

        ctx["status_cards"] = [
            {
                "label": "Initié",
                "value": exams_by_status[StatutExamen.INITIE],
                "badge_class": "",
                "panel_class": "status-panel--initie",
            },
            {
                "label": "Incomplet",
                "value": exams_by_status[StatutExamen.INCOMPLET],
                "badge_class": "badge--warning",
                "panel_class": "status-panel--warning",
            },
            {
                "label": "Complet",
                "value": exams_by_status[StatutExamen.COMPLET],
                "badge_class": "badge--success",
                "panel_class": "status-panel--success",
            },
            {
                "label": "Terminé",
                "value": exams_by_status[StatutExamen.TERMINE],
                "badge_class": "badge--info",
                "panel_class": "status-panel--info",
            },
        ]
        ctx["exams_to_complete_count"] = len(incomplete_exams)
        ctx["missing_surveillants_total"] = missing_surveillants_total
        ctx["formations_requiring_attention"] = formations_requiring_attention
        ctx["incomplete_exams"] = incomplete_exams[:6]
        ctx["has_urgent_needs"] = bool(missing_surveillants_total or incomplete_exams)
        ctx["dashboard_message"] = (
            "Des examens incomplets ou initiés sont actuellement enregistrés sur l'année active."
            if ctx["has_urgent_needs"]
            else "Aucun examen incomplet ou initié n'est actuellement enregistré sur l'année active."
        )
        return ctx
