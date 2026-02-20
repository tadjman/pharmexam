from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from .models import AnneeUniversitaire

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

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Année universitaire supprimée.")
        return super().delete(request, *args, **kwargs)


@login_required
@transaction.atomic
def set_active_year(request, pk):
    if request.method != "POST":
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
