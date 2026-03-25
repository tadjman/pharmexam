from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import SalleForm
from .models import Salle


class IsScolariteOrAdminMixin(UserPassesTestMixin):
    def test_func(self):
        u = self.request.user
        return u.is_authenticated and (u.is_superuser or u.is_staff or getattr(u, "role", "") == "SCOLARITE")
class SalleListView(LoginRequiredMixin, ListView):
    model = Salle
    template_name = "rooms/salle_list.html"
    context_object_name = "salles"
    paginate_by = 30

    def get_queryset(self):
        return Salle.objects.order_by("nom")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


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

    def form_valid(self, form):
        self.object = self.get_object()
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(
                self.request,
                "Suppression impossible : cette salle est encore affectée à un ou plusieurs examens.",
            )
            return redirect(self.success_url)
        messages.success(self.request, "Salle supprimée.")
        return redirect(self.success_url)
