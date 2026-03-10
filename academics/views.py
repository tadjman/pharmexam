from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Q
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from .forms import UEFilterForm, UEForm, UPFilterForm, UPForm
from .models import AnneeUniversitaire, UE, UP

# Create your views here.

class IsScolariteOrAdminMixin(UserPassesTestMixin):
    def test_func(self):
        u = self.request.user
        return u.is_authenticated and (u.is_superuser or u.is_staff or getattr(u, "role", "") == "SCOLARITE")


class AnneeListView(LoginRequiredMixin, ListView):
    model = AnneeUniversitaire
    template_name = "academics/annee_list.html"
    context_object_name = "annees"
    paginate_by = 20

    def get_queryset(self):
        return AnneeUniversitaire.objects.order_by("-date_debut", "-date_fin")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class AnneeCreateView(LoginRequiredMixin, IsScolariteOrAdminMixin, CreateView):
    model = AnneeUniversitaire
    template_name = "academics/annee_form.html"
    fields = ["nom", "date_debut", "date_fin", "is_active"]
    success_url = reverse_lazy("academics:annee_list")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Année universitaire créée.")
        return resp


class AnneeUpdateView(LoginRequiredMixin, IsScolariteOrAdminMixin, UpdateView):
    model = AnneeUniversitaire
    template_name = "academics/annee_form.html"
    fields = ["nom", "date_debut", "date_fin", "is_active"]
    success_url = reverse_lazy("academics:annee_list")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Année universitaire mise à jour.")
        return resp


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
                "Suppression impossible : cette année universitaire contient encore des sessions ou des examens liés.",
            )
            return redirect(self.success_url)
        messages.success(self.request, "Année universitaire supprimée.")
        return redirect(self.success_url)


class UEListView(LoginRequiredMixin, ListView):
    model = UE
    template_name = "academics/ue_list.html"
    context_object_name = "ues"
    paginate_by = 30

    def get_queryset(self):
        qs = UE.objects.prefetch_related("responsables").order_by("nom")
        self.filter_form = UEFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            q = self.filter_form.cleaned_data.get("q")
            responsable = self.filter_form.cleaned_data.get("responsable")
            if q:
                qs = qs.filter(nom__icontains=q)
            if responsable:
                qs = qs.filter(responsables=responsable)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_form"] = self.filter_form
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
                "Suppression impossible : cette UE contient encore des UP ou des examens liés.",
            )
            return redirect(self.success_url)
        messages.success(self.request, "UE supprimée.")
        return redirect(self.success_url)


class UPListView(LoginRequiredMixin, ListView):
    model = UP
    template_name = "academics/up_list.html"
    context_object_name = "ups"
    paginate_by = 30

    def get_queryset(self):
        qs = UP.objects.select_related("ue").prefetch_related("responsables").order_by("ue__nom", "nom")
        self.filter_form = UPFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            q = self.filter_form.cleaned_data.get("q")
            ue = self.filter_form.cleaned_data.get("ue")
            responsable = self.filter_form.cleaned_data.get("responsable")
            if q:
                qs = qs.filter(Q(nom__icontains=q) | Q(matiere__icontains=q))
            if ue:
                qs = qs.filter(ue=ue)
            if responsable:
                qs = qs.filter(responsables=responsable)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_form"] = self.filter_form
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class UPCreateView(LoginRequiredMixin, IsScolariteOrAdminMixin, CreateView):
    model = UP
    form_class = UPForm
    template_name = "academics/up_form.html"
    success_url = reverse_lazy("academics:up_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "UP créée.")
        return response


class UPUpdateView(LoginRequiredMixin, IsScolariteOrAdminMixin, UpdateView):
    model = UP
    form_class = UPForm
    template_name = "academics/up_form.html"
    success_url = reverse_lazy("academics:up_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "UP mise à jour.")
        return response


class UPDeleteView(LoginRequiredMixin, IsScolariteOrAdminMixin, DeleteView):
    model = UP
    template_name = "academics/up_confirm_delete.html"
    success_url = reverse_lazy("academics:up_list")

    def form_valid(self, form):
        self.object = self.get_object()
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(
                self.request,
                "Suppression impossible : cette UP est encore utilisée par un ou plusieurs examens.",
            )
            return redirect(self.success_url)
        messages.success(self.request, "UP supprimée.")
        return redirect(self.success_url)


@login_required
@transaction.atomic
def set_active_year(request, pk):
    if request.method != "POST":
        return redirect("academics:annee_list")

    user = request.user
    if not (user.is_superuser or user.is_staff or getattr(user, "role", "") == "SCOLARITE"):
        messages.error(request, "Action non autorisée : seule la scolarité peut changer l'année active.")
        return redirect("academics:annee_list")

    year = get_object_or_404(AnneeUniversitaire, pk=pk)

    # Désactive toutes les autres
    AnneeUniversitaire.objects.filter(is_active=True).exclude(pk=year.pk).update(is_active=False)
    year.is_active = True
    year.save(update_fields=["is_active"])

    # Stocke dans la session (année sélectionnée)
    request.session["active_year_id"] = str(year.pk)

    messages.success(request, f"Année active définie : {year.nom}")
    return redirect("academics:annee_list")
