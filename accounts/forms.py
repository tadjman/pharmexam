from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import RoleUtilisateur, User


class SignUpForm(UserCreationForm):
    first_name = forms.CharField(label="Prénom", max_length=150)
    last_name = forms.CharField(label="Nom", max_length=150)
    email = forms.EmailField(label="Adresse email")

    class Meta:
        model = User
        fields = ["last_name", "first_name", "email", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Mot de passe"
        self.fields["password2"].label = "Confirmation du mot de passe"
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "input")

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cette adresse email.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.role = RoleUtilisateur.MEMBRE_POOL
        user.username = User.build_unique_username(user.first_name, user.last_name)
        if commit:
            user.save()
        return user
