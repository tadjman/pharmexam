from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView
from xml.sax.saxutils import escape

from academics.models import AnneeUniversitaire, Formation
from accounts.models import RoleUtilisateur, User
from assignments.models import Surveillance
from exams.models import Examen, SessionExamen, build_session_order_expression


def get_active_year(request):
    year_id = request.session.get("active_year_id")
    if year_id:
        return AnneeUniversitaire.objects.filter(pk=year_id).first()
    return AnneeUniversitaire.objects.filter(is_active=True).first()


def format_minutes(total_minutes: int) -> str:
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h{minutes:02d}"


def get_sessions_queryset(active_year, formation=None):
    sessions = SessionExamen.objects.select_related("formation").filter(
        formation__annee_universitaire=active_year
    )
    if formation is not None:
        sessions = sessions.filter(formation=formation)
    return SessionExamen.ordered_queryset(sessions)


def get_report_rows(active_year, formation=None, session=None, role="", query=""):
    sessions = get_sessions_queryset(active_year, formation=formation)
    surveillance_qs = Surveillance.objects.filter(
        affectation_salle__examen__session__formation__annee_universitaire=active_year
    ).select_related(
        "affectation_salle__examen",
        "affectation_salle__examen__session",
        "affectation_salle__examen__session__formation",
        "affectation_salle__salle",
    )

    if formation is not None:
        surveillance_qs = surveillance_qs.filter(affectation_salle__examen__session__formation=formation)
    if session is not None:
        surveillance_qs = surveillance_qs.filter(affectation_salle__examen__session=session)

    users_qs = User.objects.filter(is_active=True).prefetch_related(
        Prefetch("surveillances", queryset=surveillance_qs, to_attr="report_surveillances")
    ).order_by("username")

    if role in {choice[0] for choice in RoleUtilisateur.choices}:
        users_qs = users_qs.filter(role=role)
    if query:
        users_qs = users_qs.filter(username__icontains=query)

    rows = []
    detail_rows = []
    for user in users_qs:
        surveillances = sorted(
            getattr(user, "report_surveillances", []),
            key=lambda item: (item.examen.date, item.examen.heure_debut, item.examen.nom),
        )
        total_minutes = sum(item.examen.duree_minutes for item in surveillances)
        exam_details = [
            {
                "user_display": user.display_full_name,
                "role": user.get_role_display(),
                "formation": item.affectation_salle.examen.session.formation.nom,
                "session": item.affectation_salle.examen.session.nom,
                "room": item.affectation_salle.salle.nom,
                "name": item.affectation_salle.examen.nom,
                "date": item.affectation_salle.examen.date,
                "time_range": (
                    f"{item.affectation_salle.examen.heure_debut} → "
                    f"{item.affectation_salle.examen.heure_fin}"
                ),
                "duration": format_minutes(item.affectation_salle.examen.duree_minutes),
                "minutes": item.affectation_salle.examen.duree_minutes,
            }
            for item in surveillances
        ]
        detail_rows.extend(exam_details)
        rows.append(
            {
                "user": user,
                "exam_count": len(surveillances),
                "total_minutes": total_minutes,
                "hours_display": format_minutes(total_minutes),
                "exam_details": exam_details,
                "exam_details_export": " | ".join(
                    f"{detail['formation']} / {detail['session']} / {detail['name']} / {detail['room']} "
                    f"({detail['date']} - {detail['time_range']})"
                    for detail in exam_details
                ),
            }
        )

    rows.sort(key=lambda row: (-row["exam_count"], -row["total_minutes"], row["user"].username))
    totals = {
        "users": len(rows),
        "exam_count": sum(row["exam_count"] for row in rows),
        "minutes": sum(row["total_minutes"] for row in rows),
        "hours_display": format_minutes(sum(row["total_minutes"] for row in rows)),
    }
    return sessions, rows, totals, detail_rows


def build_excel_xml(title, rows, detail_rows):
    summary_rows = [
        (
            "<Row>"
            "<Cell><Data ss:Type=\"String\">Surveillant</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Role</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Contact</Data></Cell>"
            "<Cell><Data ss:Type=\"Number\">Examens</Data></Cell>"
            "<Cell><Data ss:Type=\"Number\">Minutes</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Heures</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Détail des examens</Data></Cell>"
            "</Row>"
        )
    ]
    for row in rows:
        summary_rows.append(
            "<Row>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['user'].display_full_name)}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['user'].get_role_display())}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['user'].display_contact)}</Data></Cell>"
            f"<Cell><Data ss:Type=\"Number\">{row['exam_count']}</Data></Cell>"
            f"<Cell><Data ss:Type=\"Number\">{row['total_minutes']}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{row['hours_display']}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['exam_details_export'])}</Data></Cell>"
            "</Row>"
        )

    detailed_rows = [
        (
            "<Row>"
            "<Cell><Data ss:Type=\"String\">Surveillant</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Role</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Formation</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Session</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Salle</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Examen</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Date</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Créneau</Data></Cell>"
            "<Cell><Data ss:Type=\"Number\">Minutes</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Durée</Data></Cell>"
            "</Row>"
        )
    ]
    for item in detail_rows:
        detailed_rows.append(
            "<Row>"
            f"<Cell><Data ss:Type=\"String\">{escape(item['user_display'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(item['role'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(item['formation'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(item['session'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(item['room'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(item['name'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(str(item['date']))}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(item['time_range'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"Number\">{item['minutes']}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(item['duration'])}</Data></Cell>"
            "</Row>"
        )

    return (
        "<?xml version=\"1.0\"?>"
        "<?mso-application progid=\"Excel.Sheet\"?>"
        "<Workbook xmlns=\"urn:schemas-microsoft-com:office:spreadsheet\" "
        "xmlns:o=\"urn:schemas-microsoft-com:office:office\" "
        "xmlns:x=\"urn:schemas-microsoft-com:office:excel\" "
        "xmlns:ss=\"urn:schemas-microsoft-com:office:spreadsheet\">"
        "<Worksheet ss:Name=\"Synthese\"><Table>"
        f"<Row><Cell><Data ss:Type=\"String\">{escape(title)}</Data></Cell></Row>"
        + "".join(summary_rows) +
        "</Table></Worksheet>"
        "<Worksheet ss:Name=\"Detail examens\"><Table>"
        f"<Row><Cell><Data ss:Type=\"String\">{escape(title)} - detail</Data></Cell></Row>"
        + "".join(detailed_rows) +
        "</Table></Worksheet>"
        "</Workbook>"
    )


def get_exam_export_rows(active_year, session=None):
    exams = Examen.objects.filter(
        session__formation__annee_universitaire=active_year
    ).select_related(
        "session",
        "session__formation",
        "ue",
    ).prefetch_related(
        "affectations_salles__salle",
        "affectations_salles__surveillances__surveillant",
    )
    if session is not None:
        exams = exams.filter(session=session)
    exams = exams.annotate(
        session_sort_order=build_session_order_expression("session__nom")
    ).order_by("session__formation__nom", "session_sort_order", "session__nom", "date", "heure_debut", "nom")

    exam_rows = []
    room_rows = []
    surveillance_rows = []

    for exam in exams:
        exam.update_statut(save=True)
        affectations = list(exam.affectations_salles.all())
        surveillances = [surveillance for affectation in affectations for surveillance in affectation.surveillances.all()]
        exam_rows.append(
            {
                "formation": exam.session.formation.nom,
                "session": exam.session.nom,
                "exam": exam.nom,
                "date": str(exam.date),
                "start": str(exam.heure_debut),
                "end": str(exam.heure_fin),
                "statut": exam.statut,
                "ue": exam.ue.nom,
                "required_watchers": sum(affectation.nb_surveillants_requis for affectation in affectations),
                "registered_watchers": len(surveillances),
                "rooms_count": len(affectations),
                "temps_majore_rooms": sum(1 for affectation in affectations if affectation.temps_majore),
            }
        )
        for affectation in affectations:
            room_rows.append(
                {
                    "formation": exam.session.formation.nom,
                    "session": exam.session.nom,
                    "exam": exam.nom,
                    "room": affectation.salle.nom,
                    "temps_majore": "Oui" if affectation.temps_majore else "Non",
                    "required_watchers": affectation.nb_surveillants_requis,
                    "registered_watchers": affectation.surveillances.count(),
                    "lock_start": affectation.salle.heure_debut_verrouillage or "",
                    "lock_end": affectation.salle.heure_fin_verrouillage or "",
                }
            )
            for item in affectation.surveillances.all():
                surveillance_rows.append(
                    {
                        "formation": exam.session.formation.nom,
                        "session": exam.session.nom,
                        "exam": exam.nom,
                        "date": str(exam.date),
                        "room": affectation.salle.nom,
                        "watcher": item.surveillant.display_full_name,
                        "role": item.surveillant.get_role_display(),
                        "time_range": f"{exam.heure_debut} → {exam.heure_fin}",
                        "duration": format_minutes(exam.duree_minutes),
                    }
                )

    return exam_rows, room_rows, surveillance_rows


def build_exam_export_xml(title, exam_rows, room_rows, surveillance_rows):
    exam_sheet_rows = [
        (
            "<Row>"
            "<Cell><Data ss:Type=\"String\">Formation</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Session</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Examen</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Date</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Début</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Fin</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Statut</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">UE</Data></Cell>"
            "<Cell><Data ss:Type=\"Number\">Surveillants requis</Data></Cell>"
            "<Cell><Data ss:Type=\"Number\">Surveillants inscrits</Data></Cell>"
            "<Cell><Data ss:Type=\"Number\">Salles</Data></Cell>"
            "<Cell><Data ss:Type=\"Number\">Salles temps majoré</Data></Cell>"
            "</Row>"
        )
    ]
    for row in exam_rows:
        exam_sheet_rows.append(
            "<Row>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['formation'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['session'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['exam'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['date'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['start'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['end'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['statut'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['ue'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"Number\">{row['required_watchers']}</Data></Cell>"
            f"<Cell><Data ss:Type=\"Number\">{row['registered_watchers']}</Data></Cell>"
            f"<Cell><Data ss:Type=\"Number\">{row['rooms_count']}</Data></Cell>"
            f"<Cell><Data ss:Type=\"Number\">{row['temps_majore_rooms']}</Data></Cell>"
            "</Row>"
        )

    room_sheet_rows = [
        (
            "<Row>"
            "<Cell><Data ss:Type=\"String\">Formation</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Session</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Examen</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Salle</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Temps majoré</Data></Cell>"
            "<Cell><Data ss:Type=\"Number\">Surveillants requis</Data></Cell>"
            "<Cell><Data ss:Type=\"Number\">Surveillants inscrits</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Début verrouillage</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Fin verrouillage</Data></Cell>"
            "</Row>"
        )
    ]
    for row in room_rows:
        room_sheet_rows.append(
            "<Row>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['formation'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['session'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['exam'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['room'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['temps_majore'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"Number\">{row['required_watchers']}</Data></Cell>"
            f"<Cell><Data ss:Type=\"Number\">{row['registered_watchers']}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(str(row['lock_start']))}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(str(row['lock_end']))}</Data></Cell>"
            "</Row>"
        )

    surveillance_sheet_rows = [
        (
            "<Row>"
            "<Cell><Data ss:Type=\"String\">Formation</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Session</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Examen</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Date</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Salle</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Surveillant</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Rôle</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Créneau</Data></Cell>"
            "<Cell><Data ss:Type=\"String\">Durée</Data></Cell>"
            "</Row>"
        )
    ]
    for row in surveillance_rows:
        surveillance_sheet_rows.append(
            "<Row>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['formation'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['session'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['exam'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['date'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['room'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['watcher'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['role'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['time_range'])}</Data></Cell>"
            f"<Cell><Data ss:Type=\"String\">{escape(row['duration'])}</Data></Cell>"
            "</Row>"
        )

    return (
        "<?xml version=\"1.0\"?>"
        "<?mso-application progid=\"Excel.Sheet\"?>"
        "<Workbook xmlns=\"urn:schemas-microsoft-com:office:spreadsheet\" "
        "xmlns:o=\"urn:schemas-microsoft-com:office:office\" "
        "xmlns:x=\"urn:schemas-microsoft-com:office:excel\" "
        "xmlns:ss=\"urn:schemas-microsoft-com:office:spreadsheet\">"
        "<Worksheet ss:Name=\"Examens\"><Table>"
        f"<Row><Cell><Data ss:Type=\"String\">{escape(title)}</Data></Cell></Row>"
        + "".join(exam_sheet_rows) +
        "</Table></Worksheet>"
        "<Worksheet ss:Name=\"Salles\"><Table>"
        f"<Row><Cell><Data ss:Type=\"String\">{escape(title)} - salles</Data></Cell></Row>"
        + "".join(room_sheet_rows) +
        "</Table></Worksheet>"
        "<Worksheet ss:Name=\"Surveillances\"><Table>"
        f"<Row><Cell><Data ss:Type=\"String\">{escape(title)} - surveillances</Data></Cell></Row>"
        + "".join(surveillance_sheet_rows) +
        "</Table></Worksheet>"
        "</Workbook>"
    )


class ActivityReportView(LoginRequiredMixin, TemplateView):
    template_name = "reports/activity_report.html"

    def dispatch(self, request, *args, **kwargs):
        self.active_year = get_active_year(request)
        if not self.active_year:
            messages.warning(request, "Sélectionnez d'abord une année universitaire active.")
            return redirect("academics:annee_list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        _, rows, totals, detail_rows = get_report_rows(self.active_year)

        ctx["active_year"] = self.active_year
        ctx["rows"] = rows
        ctx["detail_rows"] = detail_rows
        ctx["totals"] = totals
        return ctx


class ExportCenterView(LoginRequiredMixin, TemplateView):
    template_name = "reports/export_center.html"

    def dispatch(self, request, *args, **kwargs):
        self.active_year = get_active_year(request)
        if not self.active_year:
            messages.warning(request, "Sélectionnez d'abord une année universitaire active.")
            return redirect("academics:annee_list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_year"] = self.active_year
        ctx["formations"] = Formation.objects.filter(annee_universitaire=self.active_year).prefetch_related(
            Prefetch("sessions", queryset=SessionExamen.ordered_queryset())
        ).order_by("nom")
        return ctx


class BaseExportView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        self.active_year = get_active_year(request)
        if not self.active_year:
            messages.warning(request, "Sélectionnez d'abord une année universitaire active.")
            return redirect("academics:annee_list")
        return super().dispatch(request, *args, **kwargs)


class YearExportView(BaseExportView):
    def get(self, request, *args, **kwargs):
        _, rows, _, detail_rows = get_report_rows(self.active_year)
        title = f"Suivi annee {self.active_year.nom}"
        response = HttpResponse(build_excel_xml(title, rows, detail_rows), content_type="application/vnd.ms-excel")
        response["Content-Disposition"] = f'attachment; filename="suivi-{self.active_year.nom}.xls"'
        return response


class SessionExportView(BaseExportView):
    def get(self, request, *args, **kwargs):
        session = get_object_or_404(
            SessionExamen,
            pk=kwargs["pk"],
            formation__annee_universitaire=self.active_year,
        )
        _, rows, _, detail_rows = get_report_rows(self.active_year, formation=session.formation, session=session)
        title = f"Suivi session {session.nom}"
        response = HttpResponse(build_excel_xml(title, rows, detail_rows), content_type="application/vnd.ms-excel")
        response["Content-Disposition"] = f'attachment; filename="suivi-{session.nom}.xls"'
        return response


class ExamYearExportView(BaseExportView):
    def get(self, request, *args, **kwargs):
        exam_rows, room_rows, surveillance_rows = get_exam_export_rows(self.active_year)
        title = f"Export examens {self.active_year.nom}"
        response = HttpResponse(
            build_exam_export_xml(title, exam_rows, room_rows, surveillance_rows),
            content_type="application/vnd.ms-excel",
        )
        response["Content-Disposition"] = f'attachment; filename="examens-{self.active_year.nom}.xls"'
        return response


class ExamSessionExportView(BaseExportView):
    def get(self, request, *args, **kwargs):
        session = get_object_or_404(
            SessionExamen,
            pk=kwargs["pk"],
            formation__annee_universitaire=self.active_year,
        )
        exam_rows, room_rows, surveillance_rows = get_exam_export_rows(self.active_year, session=session)
        title = f"Export examens {session.nom}"
        response = HttpResponse(
            build_exam_export_xml(title, exam_rows, room_rows, surveillance_rows),
            content_type="application/vnd.ms-excel",
        )
        response["Content-Disposition"] = f'attachment; filename="examens-{session.nom}.xls"'
        return response
