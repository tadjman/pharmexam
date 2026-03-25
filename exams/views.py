from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from academics.models import AnneeUniversitaire, Formation
from assignments.models import Surveillance
from rooms.models import AffectationSalle

from .forms import ExamCompletionRoomForm, ExamCompletionSurveillanceForm, ExamForm, SessionForm
from .models import Examen, SessionExamen, StatutExamen


class IsScolariteOrAdminMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (
            user.is_superuser or user.is_staff or getattr(user, "role", "") == "SCOLARITE"
        )


def get_active_year(request):
    year_id = request.session.get("active_year_id")
    if year_id:
        return AnneeUniversitaire.objects.filter(pk=year_id).first()
    return AnneeUniversitaire.objects.filter(is_active=True).first()


def build_url(name, **params):
    query = urlencode({key: value for key, value in params.items() if value})
    url = reverse(name)
    return f"{url}?{query}" if query else url


class SessionListView(LoginRequiredMixin, ListView):
    model = SessionExamen
    template_name = "exams/session_list.html"
    context_object_name = "sessions"
    paginate_by = 20

    def get_queryset(self):
        self.active_year = get_active_year(self.request)
        self.formations = Formation.objects.select_related("annee_universitaire").order_by(
            "annee_universitaire__date_debut", "nom"
        )
        self.selected_formation = self.request.GET.get("formation", "").strip()
        self.selected_formation_obj = self.formations.filter(pk=self.selected_formation).first() if self.selected_formation else None
        if not self.selected_formation_obj:
            return SessionExamen.objects.none()

        qs = SessionExamen.objects.select_related("formation", "formation__annee_universitaire").filter(
            formation=self.selected_formation_obj
        )
        return qs.order_by("-date_debut", "nom")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_year"] = getattr(self, "active_year", None)
        ctx["selected_formation"] = getattr(self, "selected_formation", "")
        ctx["selected_formation_obj"] = getattr(self, "selected_formation_obj", None)
        ctx["new_session_url"] = build_url("exams:session_create", formation=ctx["selected_formation"])
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class SessionCreateView(LoginRequiredMixin, IsScolariteOrAdminMixin, CreateView):
    model = SessionExamen
    form_class = SessionForm
    template_name = "exams/session_form.html"

    def dispatch(self, request, *args, **kwargs):
        formation_id = request.GET.get("formation")
        self.selected_formation = Formation.objects.select_related("annee_universitaire").filter(pk=formation_id).first()
        self.active_year = self.selected_formation.annee_universitaire if self.selected_formation else get_active_year(request)
        if not self.active_year and not Formation.objects.exists():
            messages.warning(request, "Créez d'abord une formation avant d'ajouter une session.")
            return redirect("academics:formation_list")
        if self.active_year and not Formation.objects.filter(annee_universitaire=self.active_year).exists():
            messages.warning(request, "Créez d'abord une formation pour cette année universitaire avant d'ajouter une session.")
            return redirect(f"{reverse('academics:formation_list')}?year={self.active_year.pk}")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["active_year"] = self.active_year
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        if self.selected_formation:
            initial["formation"] = self.selected_formation.pk
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Session créée.")
        return response

    def get_success_url(self):
        return build_url("exams:session_list", formation=self.object.formation_id)


class SessionUpdateView(LoginRequiredMixin, IsScolariteOrAdminMixin, UpdateView):
    model = SessionExamen
    form_class = SessionForm
    template_name = "exams/session_form.html"

    def get_queryset(self):
        return SessionExamen.objects.all()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["active_year"] = self.object.formation.annee_universitaire
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Session mise à jour.")
        return response

    def get_success_url(self):
        return build_url("exams:session_list", formation=self.object.formation_id)


class SessionDeleteView(LoginRequiredMixin, IsScolariteOrAdminMixin, DeleteView):
    model = SessionExamen
    template_name = "exams/session_confirm_delete.html"
    success_url = reverse_lazy("exams:session_list")

    def get_queryset(self):
        return SessionExamen.objects.all()

    def form_valid(self, form):
        self.object = self.get_object()
        success_url = build_url("exams:session_list", formation=self.object.formation_id)
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(
                self.request,
                "Suppression impossible : cette session contient encore des examens.",
            )
            return redirect(success_url)
        messages.success(self.request, "Session supprimée.")
        return redirect(success_url)


class ExamListView(LoginRequiredMixin, ListView):
    model = Examen
    template_name = "exams/exam_list.html"
    context_object_name = "examens"
    paginate_by = 20
    scope_session_key = "exam_scope"

    def _read_scope_value(self, key, stored_scope):
        if key in self.request.GET:
            return self.request.GET.get(key, "").strip()
        return stored_scope.get(key, "")

    def _persist_scope(self):
        self.request.session[self.scope_session_key] = {
            "year": str(self.selected_year.pk) if self.selected_year else "",
            "formation": self.selected_formation,
            "session": self.selected_session,
        }
        self.request.session.modified = True

    def get_queryset(self):
        self.active_year = get_active_year(self.request)
        self.years = AnneeUniversitaire.objects.order_by("-date_debut", "-date_fin")
        stored_scope = self.request.session.get(self.scope_session_key, {})
        self.selected_year = None
        selected_year_id = self._read_scope_value("year", stored_scope)
        if selected_year_id:
            self.selected_year = self.years.filter(pk=selected_year_id).first()
        if self.selected_year is None:
            self.selected_year = self.active_year or self.years.first()

        if not self.selected_year:
            self.formations = Formation.objects.none()
            self.sessions = SessionExamen.objects.none()
            self.selected_formation = ""
            self.selected_session = ""
            self.selected_formation_obj = None
            self.selected_session_obj = None
            self.formations_payload = []
            self.sessions_payload = []
            self._persist_scope()
            return Examen.objects.none()

        self.formations = Formation.objects.filter(annee_universitaire=self.selected_year).order_by("nom")
        self.selected_formation = self._read_scope_value("formation", stored_scope)
        self.selected_session = self._read_scope_value("session", stored_scope)
        self.formations_payload = [
            {
                "id": str(formation.pk),
                "year_id": str(formation.annee_universitaire_id),
                "label": formation.nom,
            }
            for formation in Formation.objects.select_related("annee_universitaire").order_by(
                "annee_universitaire__date_debut", "nom"
            )
        ]
        all_sessions = SessionExamen.objects.select_related("formation", "formation__annee_universitaire").filter(
            formation__annee_universitaire=self.selected_year
        ).order_by("formation__nom", "-date_debut", "nom")
        self.sessions_payload = [
            {
                "id": str(session.pk),
                "formation_id": str(session.formation_id),
                "label": session.nom,
            }
            for session in all_sessions
        ]

        selected_session_obj = None
        if self.selected_formation and not self.formations.filter(pk=self.selected_formation).exists():
            self.selected_formation = ""
            self.selected_session = ""
        if self.selected_session:
            selected_session_obj = all_sessions.filter(pk=self.selected_session).first()
            if selected_session_obj and not self.selected_formation:
                self.selected_formation = str(selected_session_obj.formation_id)
            elif selected_session_obj is None:
                self.selected_session = ""

        self.selected_formation_obj = self.formations.filter(pk=self.selected_formation).first() if self.selected_formation else None
        self.sessions = all_sessions.filter(formation_id=self.selected_formation) if self.selected_formation else SessionExamen.objects.none()
        self.selected_session_obj = (
            self.sessions.filter(pk=self.selected_session).first()
            if self.selected_session and self.selected_formation
            else None
        )

        if not self.selected_session_obj:
            self.selected_session = ""
            self._persist_scope()
            return Examen.objects.none()

        qs = Examen.objects.select_related(
            "session",
            "session__formation",
            "up",
            "up__ue",
            "responsable",
        ).filter(session=self.selected_session_obj)

        for exam in qs:
            exam.update_statut(save=True)

        self._persist_scope()

        return (
            Examen.objects.select_related(
                "session",
                "session__formation",
                "up",
                "up__ue",
                "responsable",
            )
            .filter(session=self.selected_session_obj)
            .order_by("date", "heure_debut")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_year"] = getattr(self, "active_year", None)
        ctx["years"] = getattr(self, "years", AnneeUniversitaire.objects.none())
        ctx["selected_year"] = getattr(self, "selected_year", None)
        ctx["formations"] = getattr(self, "formations", Formation.objects.none())
        ctx["sessions"] = getattr(self, "sessions", SessionExamen.objects.none())
        ctx["selected_formation"] = getattr(self, "selected_formation", "")
        ctx["selected_session"] = getattr(self, "selected_session", "")
        ctx["selected_formation_obj"] = getattr(self, "selected_formation_obj", None)
        ctx["selected_session_obj"] = getattr(self, "selected_session_obj", None)
        ctx["formations_payload"] = getattr(self, "formations_payload", [])
        ctx["sessions_payload"] = getattr(self, "sessions_payload", [])
        ctx["new_exam_url"] = build_url("exams:exam_create", session=ctx["selected_session"])
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class ExamDetailView(LoginRequiredMixin, DetailView):
    model = Examen
    template_name = "exams/exam_detail.html"
    context_object_name = "examen"

    def get_queryset(self):
        return (
            Examen.objects.select_related("session", "session__formation", "session__formation__annee_universitaire", "up", "up__ue", "responsable")
            .prefetch_related("affectations_salles__salle", "surveillances__surveillant")
        )

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        obj.update_statut(save=True)
        return obj


def completion_metrics(exam: Examen):
    total_capacity = sum(a.capacite_effective for a in exam.affectations_salles.select_related("salle"))
    tiers_required = exam.nb_eleves_tiers_temps > 0
    tiers_count = exam.affectations_salles.filter(is_tiers_temps=True).count()
    surveillants_count = exam.surveillances.count()
    return {
        "total_capacity": total_capacity,
        "required_capacity": exam.nb_eleves,
        "capacity_ok": total_capacity >= exam.nb_eleves,
        "missing_capacity": max(0, exam.nb_eleves - total_capacity),
        "tiers_required": tiers_required,
        "tiers_count": tiers_count,
        "tiers_ok": (not tiers_required) or tiers_count > 0,
        "missing_tiers_room": 1 if tiers_required and tiers_count == 0 else 0,
        "surveillants_count": surveillants_count,
        "surveillants_required": exam.nb_surveillants_requis,
        "surveillants_ok": surveillants_count >= exam.nb_surveillants_requis,
        "missing_surveillants": max(0, exam.nb_surveillants_requis - surveillants_count),
    }


class ExamCompleteView(LoginRequiredMixin, IsScolariteOrAdminMixin, View):
    template_name = "exams/exam_complete.html"

    def dispatch(self, request, *args, **kwargs):
        self.examen = get_object_or_404(
            Examen.objects.select_related("session", "session__formation", "session__formation__annee_universitaire", "up", "up__ue", "responsable").prefetch_related(
                "affectations_salles__salle",
                "surveillances__surveillant",
            ),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        room_form = ExamCompletionRoomForm(examen=self.examen)
        surveillance_form = ExamCompletionSurveillanceForm(examen=self.examen)
        return self.render_page(request, room_form, surveillance_form)

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        room_form = ExamCompletionRoomForm(examen=self.examen)
        surveillance_form = ExamCompletionSurveillanceForm(examen=self.examen)

        if action == "add_room":
            room_form = ExamCompletionRoomForm(request.POST, examen=self.examen)
            if room_form.is_valid():
                room_form.save()
                self.examen.update_statut(save=True)
                messages.success(request, "Salle affectée.")
                return redirect("exams:exam_complete", pk=self.examen.pk)
        elif action == "add_surveillance":
            surveillance_form = ExamCompletionSurveillanceForm(request.POST, examen=self.examen)
            if surveillance_form.is_valid():
                surveillance_form.save()
                self.examen.update_statut(save=True)
                messages.success(request, "Surveillant inscrit.")
                return redirect("exams:exam_complete", pk=self.examen.pk)
        elif action == "update_room":
            room_id = request.POST.get("room_id")
            affectation = get_object_or_404(AffectationSalle, pk=room_id, examen=self.examen)
            room_form = ExamCompletionRoomForm(
                request.POST,
                examen=self.examen,
                instance=affectation,
                prefix=f"room-{affectation.pk}",
            )
            if room_form.is_valid():
                room_form.save()
                self.examen.update_statut(save=True)
                messages.success(request, "Affectation salle mise à jour.")
                return redirect("exams:exam_complete", pk=self.examen.pk)
        elif action == "delete_room":
            room_id = request.POST.get("room_id")
            affectation = get_object_or_404(AffectationSalle, pk=room_id, examen=self.examen)
            remaining_capacity = sum(
                affect.capacite_effective
                for affect in self.examen.affectations_salles.exclude(pk=affectation.pk).select_related("salle")
            )
            if self.examen.nb_eleves_tiers_temps > 0 and affectation.is_tiers_temps:
                remaining_tiers = self.examen.affectations_salles.exclude(pk=affectation.pk).filter(
                    is_tiers_temps=True
                ).exists()
                if not remaining_tiers:
                    messages.error(
                        request,
                        "Suppression impossible : une salle tiers-temps est obligatoire pour cet examen.",
                    )
                    return redirect("exams:exam_complete", pk=self.examen.pk)
            if remaining_capacity < self.examen.nb_eleves:
                messages.error(
                    request,
                    f"Suppression impossible : capacité insuffisante après suppression ({remaining_capacity} / {self.examen.nb_eleves}).",
                )
                return redirect("exams:exam_complete", pk=self.examen.pk)
            affectation.delete()
            self.examen.update_statut(save=True)
            messages.success(request, "Affectation salle supprimée.")
            return redirect("exams:exam_complete", pk=self.examen.pk)
        elif action == "delete_surveillance":
            surveillance_id = request.POST.get("surveillance_id")
            surveillance = get_object_or_404(Surveillance, pk=surveillance_id, examen=self.examen)
            surveillance.delete()
            self.examen.update_statut(save=True)
            messages.success(request, "Inscription surveillance supprimée.")
            return redirect("exams:exam_complete", pk=self.examen.pk)

        return self.render_page(request, room_form, surveillance_form)

    def render_page(self, request, room_form, surveillance_form):
        metrics = completion_metrics(self.examen)
        room_edit_rows = []
        for affectation in self.examen.affectations_salles.all():
            edit_form = ExamCompletionRoomForm(
                examen=self.examen,
                instance=affectation,
                prefix=f"room-{affectation.pk}",
            )
            if room_form.instance.pk == affectation.pk:
                edit_form = room_form
            room_edit_rows.append({"affectation": affectation, "form": edit_form})
        return render(
            request,
            self.template_name,
            {
                "examen": self.examen,
                "room_form": room_form,
                "room_edit_rows": room_edit_rows,
                "surveillance_form": surveillance_form,
                "metrics": metrics,
            },
        )


class ExamCreateView(LoginRequiredMixin, IsScolariteOrAdminMixin, CreateView):
    model = Examen
    form_class = ExamForm
    template_name = "exams/exam_form.html"

    def dispatch(self, request, *args, **kwargs):
        session_id = request.GET.get("session")
        self.preselected_session = SessionExamen.objects.select_related("formation", "formation__annee_universitaire").filter(
            pk=session_id
        ).first() if session_id else None
        year_scope = self.preselected_session.formation.annee_universitaire if self.preselected_session else get_active_year(request)
        if not year_scope and not SessionExamen.objects.exists():
            messages.warning(request, "Créez d'abord une session avant d'initier un examen.")
            return redirect("exams:session_list")
        if year_scope and not SessionExamen.objects.filter(formation__annee_universitaire=year_scope).exists():
            messages.warning(request, "Créez d'abord une session pour cette année universitaire avant d'initier un examen.")
            return redirect("exams:exam_list")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        year_scope = (
            self.preselected_session.formation.annee_universitaire
            if getattr(self, "preselected_session", None)
            else get_active_year(self.request)
        )
        kwargs["active_year"] = year_scope
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        if getattr(self, "preselected_session", None):
            initial["session"] = self.preselected_session.pk
        return initial

    def form_valid(self, form):
        form.instance.statut = StatutExamen.INITIE
        response = super().form_valid(form)
        self.object.update_statut(save=True)
        messages.success(self.request, "Examen créé (statut : INITIÉ).")
        return response

    def get_success_url(self):
        return build_url(
            "exams:exam_list",
            year=self.object.session.formation.annee_universitaire_id,
            formation=self.object.session.formation_id,
            session=self.object.session_id,
        )


class ExamUpdateView(LoginRequiredMixin, IsScolariteOrAdminMixin, UpdateView):
    model = Examen
    form_class = ExamForm
    template_name = "exams/exam_form.html"

    def get_queryset(self):
        return Examen.objects.all()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["active_year"] = self.object.session.formation.annee_universitaire
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.update_statut(save=True)
        messages.success(self.request, "Examen mis à jour.")
        return response

    def get_success_url(self):
        return build_url(
            "exams:exam_list",
            year=self.object.session.formation.annee_universitaire_id,
            formation=self.object.session.formation_id,
            session=self.object.session_id,
        )


class ExamDeleteView(LoginRequiredMixin, IsScolariteOrAdminMixin, DeleteView):
    model = Examen
    template_name = "exams/exam_confirm_delete.html"
    success_url = reverse_lazy("exams:exam_list")

    def get_queryset(self):
        return Examen.objects.all()

    def form_valid(self, form):
        self.object = self.get_object()
        success_url = build_url(
            "exams:exam_list",
            year=self.object.session.formation.annee_universitaire_id,
            formation=self.object.session.formation_id,
            session=self.object.session_id,
        )
        self.object.delete()
        messages.success(self.request, "Examen supprimé.")
        return redirect(success_url)
