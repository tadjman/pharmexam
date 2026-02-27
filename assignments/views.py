from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView

from academics.models import AnneeUniversitaire
from accounts.models import RoleUtilisateur
from exams.models import Examen

from .forms import SurveillanceFilterForm, SurveillanceForm
from .models import Surveillance


def get_active_year(request):
    year_id = request.session.get("active_year_id")
    if year_id:
        return AnneeUniversitaire.objects.filter(pk=year_id).first()
    return AnneeUniversitaire.objects.filter(is_active=True).first()


def is_scolarite_or_admin(user):
    return user.is_superuser or user.is_staff or getattr(user, "role", "") == RoleUtilisateur.SCOLARITE


class SurveillanceListView(LoginRequiredMixin, ListView):
    model = Surveillance
    template_name = "assignments/surveillance_list.html"
    context_object_name = "surveillances"
    paginate_by = 30

    def dispatch(self, request, *args, **kwargs):
        self.active_year = get_active_year(request)
        if not self.active_year:
            messages.warning(request, "Sélectionne d’abord une année universitaire active.")
            return redirect("academics:annee_list")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = Surveillance.objects.filter(
            examen__session__annee_universitaire=self.active_year
        ).select_related("examen", "examen__session", "surveillant").order_by(
            "examen__date", "examen__heure_debut", "surveillant__username"
        )

        self.filter_form = SurveillanceFilterForm(self.request.GET or None, active_year=self.active_year)
        if self.filter_form.is_valid():
            session = self.filter_form.cleaned_data.get("session")
            examen = self.filter_form.cleaned_data.get("examen")
            surveillant = self.filter_form.cleaned_data.get("surveillant")

            if session:
                qs = qs.filter(examen__session=session)
            if examen:
                qs = qs.filter(examen=examen)
            if surveillant:
                qs = qs.filter(surveillant=surveillant)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_year"] = self.active_year
        ctx["filter_form"] = self.filter_form
        return ctx


class SurveillanceCreateView(LoginRequiredMixin, CreateView):
    model = Surveillance
    form_class = SurveillanceForm
    template_name = "assignments/surveillance_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.active_year = get_active_year(request)
        if not self.active_year:
            messages.warning(request, "Sélectionne d’abord une année universitaire active.")
            return redirect("academics:annee_list")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["active_year"] = self.active_year
        kwargs["request_user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        exam_id = self.request.GET.get("exam")
        if exam_id:
            initial["examen"] = exam_id
        if not is_scolarite_or_admin(self.request.user):
            initial["surveillant"] = self.request.user.pk
        return initial

    def form_valid(self, form):
        if not is_scolarite_or_admin(self.request.user):
            form.instance.surveillant = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Inscription surveillance enregistrée.")
        return response

    def get_success_url(self):
        return reverse("assignments:surveillance_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_year"] = self.active_year
        return ctx


class SurveillanceDeleteView(LoginRequiredMixin, DeleteView):
    model = Surveillance
    template_name = "assignments/surveillance_confirm_delete.html"
    success_url = reverse_lazy("assignments:surveillance_list")

    def get_queryset(self):
        qs = Surveillance.objects.filter(
            examen__session__annee_universitaire=get_active_year(self.request)
        ).select_related("examen", "surveillant")

        if is_scolarite_or_admin(self.request.user):
            return qs
        return qs.filter(surveillant=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Inscription surveillance supprimée.")
        return super().delete(request, *args, **kwargs)


def exam_surveillance_redirect(request, exam_pk):
    exam = get_object_or_404(
        Examen,
        pk=exam_pk,
        session__annee_universitaire=get_active_year(request),
    )
    url = reverse("assignments:surveillance_list")
    return redirect(f"{url}?examen={exam.pk}")
