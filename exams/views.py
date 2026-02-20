from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView

from academics.models import AnneeUniversitaire
from .models import SessionExamen, Examen, StatutExamen
from .forms import ExamForm


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
        return Examen.objects.select_related("session", "up", "up__ue", "responsable").filter(
            session__annee_universitaire=year
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