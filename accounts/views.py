from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import FormView

from .forms import SignUpForm


class SignUpView(FormView):
    template_name = "registration/signup.html"
    form_class = SignUpForm
    success_url = reverse_lazy("dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, "Compte créé.")
        return redirect(self.get_success_url())
