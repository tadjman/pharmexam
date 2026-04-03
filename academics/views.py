from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from config.access import ScolariteOrAdminRequiredMixin, is_scolarite_or_admin, render_access_denied

from .forms import (
    AnneeUniversitaireForm,
    FormationForm,
    UEForm,
)
from .models import AnneeUniversitaire, Formation, UE


class IsScolariteOrAdminMixin(ScolariteOrAdminRequiredMixin):
    pass


def get_active_year(request):
    year_id = request.session.get("active_year_id")
    if year_id:
        return AnneeUniversitaire.objects.filter(pk=year_id).first()
    return AnneeUniversitaire.objects.filter(is_active=True).first()


class AnneeListView(LoginRequiredMixin, IsScolariteOrAdminMixin, ListView):
    model = AnneeUniversitaire
    template_name = "academics/annee_list.html"
    context_object_name = "annees"
    paginate_by = 20

    def get_queryset(self):
        return AnneeUniversitaire.objects.annotate(
            formation_count=Count("formations", distinct=True)
        ).order_by("-date_debut", "-date_fin")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_year"] = get_active_year(self.request)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class AnneeDetailView(LoginRequiredMixin, IsScolariteOrAdminMixin, DetailView):
    model = AnneeUniversitaire
    template_name = "academics/annee_detail.html"
    context_object_name = "annee"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_year"] = get_active_year(self.request)
        ctx["formations"] = (
            Formation.objects.filter(annee_universitaire=self.object)
            .annotate(session_count=Count("sessions", distinct=True))
            .order_by("nom")
        )
        return ctx


class AnneeCreateView(LoginRequiredMixin, IsScolariteOrAdminMixin, CreateView):
    model = AnneeUniversitaire
    form_class = AnneeUniversitaireForm
    template_name = "academics/annee_form.html"
    success_url = reverse_lazy("academics:annee_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Année universitaire créée.")
        return response


class AnneeUpdateView(LoginRequiredMixin, IsScolariteOrAdminMixin, UpdateView):
    model = AnneeUniversitaire
    form_class = AnneeUniversitaireForm
    template_name = "academics/annee_form.html"
    success_url = reverse_lazy("academics:annee_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Année universitaire mise à jour.")
        return response


class AnneeDeleteView(LoginRequiredMixin, IsScolariteOrAdminMixin, DeleteView):
    model = AnneeUniversitaire
    template_name = "academics/annee_confirm_delete.html"
    success_url = reverse_lazy("academics:annee_list")

    def form_valid(self, form):
        self.object = self.get_object()
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(
                self.request,
                "Suppression impossible : cette année universitaire contient encore des formations, sessions ou examens liés.",
            )
            return redirect(self.success_url)
        messages.success(self.request, "Année universitaire supprimée.")
        return redirect(self.success_url)


class FormationListView(LoginRequiredMixin, ListView):
    model = Formation
    template_name = "academics/formation_list.html"
    context_object_name = "formations"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        self.active_year = get_active_year(request)
        if not self.active_year and not AnneeUniversitaire.objects.exists():
            messages.warning(request, "Sélectionnez d'abord une année universitaire active.")
            return redirect("academics:annee_list")
        self.selected_year = self.active_year
        if self.selected_year is None:
            self.selected_year = AnneeUniversitaire.objects.order_by("-date_debut").first()
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return (
            Formation.objects.filter(annee_universitaire=self.selected_year)
            .prefetch_related("ues")
            .annotate(session_count=Count("sessions", distinct=True), ue_count=Count("ues", distinct=True))
            .order_by("nom")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_year"] = self.active_year
        ctx["years"] = AnneeUniversitaire.objects.order_by("-date_debut", "-date_fin")
        ctx["selected_year"] = self.selected_year
        ctx["new_formation_url"] = (
            f"{reverse('academics:formation_create')}?year={self.selected_year.pk}"
            if self.selected_year
            else reverse("academics:formation_create")
        )
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class FormationCreateView(LoginRequiredMixin, IsScolariteOrAdminMixin, CreateView):
    model = Formation
    form_class = FormationForm
    template_name = "academics/formation_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.active_year = get_active_year(request)
        year_id = request.GET.get("year")
        self.target_year = (
            AnneeUniversitaire.objects.filter(pk=year_id).first()
            if year_id
            else self.active_year
        )
        if not self.target_year:
            messages.warning(request, "Sélectionnez d'abord une année universitaire active.")
            return redirect("academics:annee_list")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.annee_universitaire = self.target_year
        response = super().form_valid(form)
        messages.success(self.request, "Formation créée.")
        return response

    def get_success_url(self):
        return f"{reverse('academics:formation_list')}?year={self.object.annee_universitaire_id}"


class FormationUpdateView(LoginRequiredMixin, IsScolariteOrAdminMixin, UpdateView):
    model = Formation
    form_class = FormationForm
    template_name = "academics/formation_form.html"

    def get_queryset(self):
        return Formation.objects.all()

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Formation mise à jour.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_delete_formation"] = not self.object.sessions.filter(examens__isnull=False).exists()
        return ctx

    def get_success_url(self):
        return reverse("academics:formation_detail", args=[self.object.pk])


class FormationDeleteView(LoginRequiredMixin, IsScolariteOrAdminMixin, DeleteView):
    model = Formation
    template_name = "academics/formation_confirm_delete.html"
    success_url = reverse_lazy("academics:formation_list")

    def get_queryset(self):
        return Formation.objects.all()

    def form_valid(self, form):
        self.object = self.get_object()
        year_id = self.object.annee_universitaire_id
        if self.object.sessions.filter(examens__isnull=False).exists():
            messages.error(
                self.request,
                "Suppression impossible : cette formation contient encore des examens dans ses sessions.",
            )
            return redirect(reverse("academics:formation_update", args=[self.object.pk]))
        try:
            self.object.sessions.all().delete()
            self.object.delete()
        except ProtectedError:
            messages.error(
                self.request,
                "Suppression impossible : cette formation contient encore des sessions ou des examens liés.",
            )
            return redirect(reverse("academics:formation_update", args=[self.object.pk]))
        messages.success(self.request, "Formation supprimée.")
        return redirect(f"{self.success_url}?year={year_id}")


class FormationDetailView(LoginRequiredMixin, DetailView):
    model = Formation
    template_name = "academics/formation_detail.html"
    context_object_name = "formation"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_year"] = get_active_year(self.request)
        ctx["ues"] = self.object.ues.prefetch_related("responsables").order_by("nom")
        ctx["session_count"] = self.object.sessions.count()
        return ctx


class TeachingOverviewView(LoginRequiredMixin, TemplateView):
    template_name = "academics/teaching_overview.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_year"] = get_active_year(self.request)
        ctx["ue_count"] = UE.objects.count()
        ctx["ues"] = UE.objects.prefetch_related("responsables").order_by("nom")[:8]
        return ctx


class UEListView(LoginRequiredMixin, ListView):
    model = UE
    template_name = "academics/ue_list.html"
    context_object_name = "ues"
    paginate_by = 30

    def get_queryset(self):
        return UE.objects.prefetch_related("responsables", "formations").order_by("nom").distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_year"] = get_active_year(self.request)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class UECreateView(LoginRequiredMixin, IsScolariteOrAdminMixin, CreateView):
    model = UE
    form_class = UEForm
    template_name = "academics/ue_form.html"
    success_url = reverse_lazy("academics:ue_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "UE créée.")
        return response


class UEUpdateView(LoginRequiredMixin, IsScolariteOrAdminMixin, UpdateView):
    model = UE
    form_class = UEForm
    template_name = "academics/ue_form.html"
    success_url = reverse_lazy("academics:ue_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "UE mise à jour.")
        return response


class UEDeleteView(LoginRequiredMixin, IsScolariteOrAdminMixin, DeleteView):
    model = UE
    template_name = "academics/ue_confirm_delete.html"
    success_url = reverse_lazy("academics:ue_list")

    def form_valid(self, form):
        self.object = self.get_object()
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(
                self.request,
                "Suppression impossible : cette UE contient encore des formations ou des examens liés.",
            )
            return redirect(self.success_url)
        messages.success(self.request, "UE supprimée.")
        return redirect(self.success_url)


@login_required
@transaction.atomic
def set_active_year(request, pk):
    if request.method != "POST":
        return redirect("academics:annee_list")

    if not is_scolarite_or_admin(request.user):
        return render_access_denied(request, status=403)

    year = get_object_or_404(AnneeUniversitaire, pk=pk)
    AnneeUniversitaire.objects.filter(is_active=True).exclude(pk=year.pk).update(is_active=False)
    year.is_active = True
    year.save(update_fields=["is_active"])
    request.session["active_year_id"] = str(year.pk)
    messages.success(request, f"Année active définie : {year.nom}")
    return redirect("academics:annee_list")
