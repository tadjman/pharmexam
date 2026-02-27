from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from academics.models import AnneeUniversitaire
from exams.models import Examen

from .forms import AffectationSalleForm, SalleForm
from .models import AffectationSalle, Salle


class IsScolariteOrAdminMixin(UserPassesTestMixin):
    def test_func(self):
        u = self.request.user
        return u.is_authenticated and (u.is_superuser or u.is_staff or getattr(u, "role", "") == "SCOLARITE")


def get_active_year(request):
    year_id = request.session.get("active_year_id")
    if year_id:
        return AnneeUniversitaire.objects.filter(pk=year_id).first()
    return AnneeUniversitaire.objects.filter(is_active=True).first()


def _exam_metrics(exam: Examen):
    affectations = exam.affectations_salles.select_related("salle")
    total = sum(a.capacite_effective for a in affectations)
    required = exam.nb_eleves
    tiers_required = exam.nb_eleves_tiers_temps > 0
    tiers_ok = affectations.filter(is_tiers_temps=True).exists()
    return {
        "total_capacity": total,
        "required_capacity": required,
        "remaining_capacity": required - total,
        "capacity_ok": total >= required,
        "tiers_required": tiers_required,
        "tiers_ok": (not tiers_required) or tiers_ok,
    }


def _notify_exam_constraints(request, exam: Examen):
    metrics = _exam_metrics(exam)
    if not metrics["capacity_ok"]:
        messages.warning(
            request,
            f"Capacité insuffisante: {metrics['total_capacity']} / {metrics['required_capacity']}.",
        )
    if not metrics["tiers_ok"]:
        messages.warning(request, "Une salle tiers-temps est obligatoire pour cet examen.")


def _get_exam_or_404(request, exam_pk):
    year = get_active_year(request)
    if not year:
        return None
    return get_object_or_404(Examen, pk=exam_pk, session__annee_universitaire=year)


class SalleListView(LoginRequiredMixin, ListView):
    model = Salle
    template_name = "rooms/salle_list.html"
    context_object_name = "salles"
    paginate_by = 30

    def get_queryset(self):
        return Salle.objects.order_by("nom")


class SalleCreateView(LoginRequiredMixin, IsScolariteOrAdminMixin, CreateView):
    model = Salle
    form_class = SalleForm
    template_name = "rooms/salle_form.html"
    success_url = reverse_lazy("rooms:salle_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Salle créée.")
        return response


class SalleUpdateView(LoginRequiredMixin, IsScolariteOrAdminMixin, UpdateView):
    model = Salle
    form_class = SalleForm
    template_name = "rooms/salle_form.html"
    success_url = reverse_lazy("rooms:salle_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Salle mise à jour.")
        return response


class SalleDeleteView(LoginRequiredMixin, IsScolariteOrAdminMixin, DeleteView):
    model = Salle
    template_name = "rooms/salle_confirm_delete.html"
    success_url = reverse_lazy("rooms:salle_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Salle supprimée.")
        return super().delete(request, *args, **kwargs)


class AffectationListView(LoginRequiredMixin, ListView):
    model = AffectationSalle
    template_name = "rooms/affectation_list.html"
    context_object_name = "affectations"

    def dispatch(self, request, *args, **kwargs):
        exam = _get_exam_or_404(request, kwargs["exam_pk"])
        if exam is None:
            messages.warning(request, "Sélectionne d’abord une année universitaire active.")
            return redirect("academics:annee_list")
        self.examen = exam
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return (
            AffectationSalle.objects.filter(examen=self.examen)
            .select_related("salle", "examen")
            .order_by("salle__nom")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["examen"] = self.examen
        ctx["metrics"] = _exam_metrics(self.examen)
        return ctx


class AffectationCreateView(LoginRequiredMixin, IsScolariteOrAdminMixin, CreateView):
    model = AffectationSalle
    form_class = AffectationSalleForm
    template_name = "rooms/affectation_form.html"

    def dispatch(self, request, *args, **kwargs):
        exam = _get_exam_or_404(request, kwargs["exam_pk"])
        if exam is None:
            messages.warning(request, "Sélectionne d’abord une année universitaire active.")
            return redirect("academics:annee_list")
        self.examen = exam
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["examen"] = self.examen
        return kwargs

    def form_valid(self, form):
        form.instance.examen = self.examen
        response = super().form_valid(form)
        messages.success(self.request, "Salle affectée à l’examen.")
        _notify_exam_constraints(self.request, self.examen)
        return response

    def get_success_url(self):
        return reverse("rooms:affectation_list", kwargs={"exam_pk": self.examen.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["examen"] = self.examen
        return ctx


class AffectationUpdateView(LoginRequiredMixin, IsScolariteOrAdminMixin, UpdateView):
    model = AffectationSalle
    form_class = AffectationSalleForm
    template_name = "rooms/affectation_form.html"

    def dispatch(self, request, *args, **kwargs):
        exam = _get_exam_or_404(request, kwargs["exam_pk"])
        if exam is None:
            messages.warning(request, "Sélectionne d’abord une année universitaire active.")
            return redirect("academics:annee_list")
        self.examen = exam
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return AffectationSalle.objects.filter(examen=self.examen)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["examen"] = self.examen
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Affectation mise à jour.")
        _notify_exam_constraints(self.request, self.examen)
        return response

    def get_success_url(self):
        return reverse("rooms:affectation_list", kwargs={"exam_pk": self.examen.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["examen"] = self.examen
        return ctx


class AffectationDeleteView(LoginRequiredMixin, IsScolariteOrAdminMixin, DeleteView):
    model = AffectationSalle
    template_name = "rooms/affectation_confirm_delete.html"

    def dispatch(self, request, *args, **kwargs):
        exam = _get_exam_or_404(request, kwargs["exam_pk"])
        if exam is None:
            messages.warning(request, "Sélectionne d’abord une année universitaire active.")
            return redirect("academics:annee_list")
        self.examen = exam
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return AffectationSalle.objects.filter(examen=self.examen).select_related("salle")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.examen.nb_eleves_tiers_temps > 0 and self.object.is_tiers_temps:
            remaining_tiers = (
                self.examen.affectations_salles.exclude(pk=self.object.pk).filter(is_tiers_temps=True).exists()
            )
            if not remaining_tiers:
                messages.error(request, "Impossible: une salle tiers-temps est obligatoire pour cet examen.")
                return redirect(self.get_success_url())

        remaining_capacity = sum(
            a.capacite_effective
            for a in self.examen.affectations_salles.exclude(pk=self.object.pk).select_related("salle")
        )
        if remaining_capacity < self.examen.nb_eleves:
            messages.error(
                request,
                f"Impossible: capacité totale insuffisante après suppression ({remaining_capacity} / {self.examen.nb_eleves}).",
            )
            return redirect(self.get_success_url())

        response = super().delete(request, *args, **kwargs)
        messages.success(request, "Affectation supprimée.")
        _notify_exam_constraints(request, self.examen)
        return response

    def get_success_url(self):
        return reverse("rooms:affectation_list", kwargs={"exam_pk": self.examen.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["examen"] = self.examen
        return ctx
