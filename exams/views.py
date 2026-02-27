from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView

from academics.models import AnneeUniversitaire
from assignments.models import Surveillance
from rooms.models import AffectationSalle
from .models import SessionExamen, Examen, StatutExamen
from .forms import ExamForm, ExamCompletionRoomForm, ExamCompletionSurveillanceForm


class IsScolariteOrAdminMixin(UserPassesTestMixin):
    def test_func(self):
        u = self.request.user
        return u.is_authenticated and (u.is_superuser or u.is_staff or getattr(u, "role", "") == "SCOLARITE")


def get_active_year(request):
    year_id = request.session.get("active_year_id")
    if year_id:
        return AnneeUniversitaire.objects.filter(pk=year_id).first()
    return AnneeUniversitaire.objects.filter(is_active=True).first()


# ------------------------
# SESSIONS
# ------------------------
class SessionListView(LoginRequiredMixin, ListView):
    model = SessionExamen
    template_name = "exams/session_list.html"
    context_object_name = "sessions"
    paginate_by = 20

    def get_queryset(self):
        year = get_active_year(self.request)
        if not year:
            return SessionExamen.objects.none()
        return SessionExamen.objects.filter(annee_universitaire=year).order_by("-date_debut")


class SessionCreateView(LoginRequiredMixin, IsScolariteOrAdminMixin, CreateView):
    model = SessionExamen
    template_name = "exams/session_form.html"
    fields = ["nom", "date_debut", "date_fin"]
    success_url = reverse_lazy("exams:session_list")

    def dispatch(self, request, *args, **kwargs):
        if not get_active_year(request):
            messages.warning(request, "Sélectionne d’abord une année universitaire active.")
            return redirect("academics:annee_list")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.annee_universitaire = get_active_year(self.request)
        resp = super().form_valid(form)
        messages.success(self.request, "Session créée.")
        return resp


class SessionUpdateView(LoginRequiredMixin, IsScolariteOrAdminMixin, UpdateView):
    model = SessionExamen
    template_name = "exams/session_form.html"
    fields = ["nom", "date_debut", "date_fin"]
    success_url = reverse_lazy("exams:session_list")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Session mise à jour.")
        return resp


class SessionDeleteView(LoginRequiredMixin, IsScolariteOrAdminMixin, DeleteView):
    model = SessionExamen
    template_name = "exams/session_confirm_delete.html"
    success_url = reverse_lazy("exams:session_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Session supprimée.")
        return super().delete(request, *args, **kwargs)


# ------------------------
# EXAMENS
# ------------------------
class ExamListView(LoginRequiredMixin, ListView):
    model = Examen
    template_name = "exams/exam_list.html"
    context_object_name = "examens"
    paginate_by = 20

    def get_queryset(self):
        year = get_active_year(self.request)
        if not year:
            return Examen.objects.none()

        base_qs = Examen.objects.select_related("session", "up", "up__ue", "responsable").filter(
            session__annee_universitaire=year
        ).order_by("date", "heure_debut")

        for exam in base_qs:
            exam.update_statut(save=True)

        qs = Examen.objects.select_related("session", "up", "up__ue", "responsable").filter(
            session__annee_universitaire=year
        ).order_by("date", "heure_debut")

        session_id = self.request.GET.get("session")
        if session_id:
            qs = qs.filter(session_id=session_id)

        statut = self.request.GET.get("statut")
        valid_statuts = {c[0] for c in StatutExamen.choices}
        if statut in valid_statuts:
            qs = qs.filter(statut=statut)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        year = get_active_year(self.request)
        ctx["active_year"] = year
        ctx["sessions"] = SessionExamen.objects.filter(annee_universitaire=year).order_by("-date_debut") if year else []
        ctx["selected_session"] = self.request.GET.get("session", "")
        ctx["selected_statut"] = self.request.GET.get("statut", "")
        ctx["statuts"] = StatutExamen.choices
        ctx["now"] = timezone.now()
        return ctx


class ExamDetailView(LoginRequiredMixin, DetailView):
    model = Examen
    template_name = "exams/exam_detail.html"
    context_object_name = "examen"

    def get_queryset(self):
        year = get_active_year(self.request)
        if not year:
            return Examen.objects.none()
        return (
            Examen.objects.select_related("session", "up", "up__ue", "responsable")
            .prefetch_related("affectations_salles__salle", "surveillances__surveillant")
            .filter(session__annee_universitaire=year)
        )

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        obj.update_statut(save=True)
        return obj


def _completion_metrics(exam: Examen):
    total_capacity = sum(a.capacite_effective for a in exam.affectations_salles.select_related("salle"))
    tiers_required = exam.nb_eleves_tiers_temps > 0
    tiers_count = exam.affectations_salles.filter(is_tiers_temps=True).count()
    surveillants_count = exam.surveillances.count()
    missing_capacity = max(0, exam.nb_eleves - total_capacity)
    missing_surveillants = max(0, exam.nb_surveillants_requis - surveillants_count)
    missing_tiers_room = 1 if (tiers_required and tiers_count == 0) else 0
    return {
        "total_capacity": total_capacity,
        "required_capacity": exam.nb_eleves,
        "capacity_ok": total_capacity >= exam.nb_eleves,
        "missing_capacity": missing_capacity,
        "tiers_required": tiers_required,
        "tiers_count": tiers_count,
        "tiers_ok": (not tiers_required) or tiers_count > 0,
        "missing_tiers_room": missing_tiers_room,
        "surveillants_count": surveillants_count,
        "surveillants_required": exam.nb_surveillants_requis,
        "surveillants_ok": surveillants_count >= exam.nb_surveillants_requis,
        "missing_surveillants": missing_surveillants,
    }


class ExamCompleteView(LoginRequiredMixin, IsScolariteOrAdminMixin, View):
    template_name = "exams/exam_complete.html"

    def dispatch(self, request, *args, **kwargs):
        year = get_active_year(request)
        if not year:
            messages.warning(request, "Sélectionne d’abord une année universitaire active.")
            return redirect("academics:annee_list")
        self.examen = get_object_or_404(
            Examen.objects.select_related("session", "up", "up__ue", "responsable").prefetch_related(
                "affectations_salles__salle", "surveillances__surveillant"
            ),
            pk=kwargs["pk"],
            session__annee_universitaire=year,
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
        elif action == "delete_room":
            room_id = request.POST.get("room_id")
            affectation = get_object_or_404(AffectationSalle, pk=room_id, examen=self.examen)
            remaining_capacity = sum(
                a.capacite_effective for a in self.examen.affectations_salles.exclude(pk=affectation.pk).select_related("salle")
            )
            if self.examen.nb_eleves_tiers_temps > 0 and affectation.is_tiers_temps:
                remaining_tiers = self.examen.affectations_salles.exclude(pk=affectation.pk).filter(is_tiers_temps=True).exists()
                if not remaining_tiers:
                    messages.error(request, "Impossible: une salle tiers-temps est obligatoire pour cet examen.")
                    return redirect("exams:exam_complete", pk=self.examen.pk)
            if remaining_capacity < self.examen.nb_eleves:
                messages.error(
                    request,
                    f"Impossible: capacité insuffisante après suppression ({remaining_capacity} / {self.examen.nb_eleves}).",
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
        metrics = _completion_metrics(self.examen)
        return render(
            request,
            self.template_name,
            {
                "examen": self.examen,
                "room_form": room_form,
                "surveillance_form": surveillance_form,
                "metrics": metrics,
            },
        )


class ExamCreateView(LoginRequiredMixin, IsScolariteOrAdminMixin, CreateView):
    model = Examen
    form_class = ExamForm
    template_name = "exams/exam_form.html"
    success_url = reverse_lazy("exams:exam_list")

    def dispatch(self, request, *args, **kwargs):
        if not get_active_year(request):
            messages.warning(request, "Sélectionne d’abord une année universitaire active.")
            return redirect("academics:annee_list")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["active_year"] = get_active_year(self.request)
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        s = self.request.GET.get("session")
        if s:
            initial["session"] = s
        return initial

    def form_valid(self, form):
        form.instance.statut = StatutExamen.INITIE
        resp = super().form_valid(form)
        self.object.update_statut(save=True)
        messages.success(self.request, "Examen créé (statut : INITIÉ).")
        return resp


class ExamUpdateView(LoginRequiredMixin, IsScolariteOrAdminMixin, UpdateView):
    model = Examen
    form_class = ExamForm
    template_name = "exams/exam_form.html"
    success_url = reverse_lazy("exams:exam_list")

    def get_queryset(self):
        year = get_active_year(self.request)
        if not year:
            return Examen.objects.none()
        return Examen.objects.filter(session__annee_universitaire=year)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["active_year"] = get_active_year(self.request)
        return kwargs

    def form_valid(self, form):
        resp = super().form_valid(form)
        self.object.update_statut(save=True)
        messages.success(self.request, "Examen mis à jour.")
        return resp


class ExamDeleteView(LoginRequiredMixin, IsScolariteOrAdminMixin, DeleteView):
    model = Examen
    template_name = "exams/exam_confirm_delete.html"
    success_url = reverse_lazy("exams:exam_list")

    def get_queryset(self):
        year = get_active_year(self.request)
        if not year:
            return Examen.objects.none()
        return Examen.objects.filter(session__annee_universitaire=year)

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Examen supprimé.")
        return super().delete(request, *args, **kwargs)
