from django import forms

from accounts.models import RoleUtilisateur, User

from .models import AnneeUniversitaire, Formation, UE, UP


class AnneeUniversitaireForm(forms.ModelForm):
    class Meta:
        model = AnneeUniversitaire
        fields = ["date_debut", "date_fin", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date_debut"].widget.attrs.setdefault("class", "input")
        self.fields["date_fin"].widget.attrs.setdefault("class", "input")


def _responsables_queryset():
    return User.objects.filter(
        role__in=[RoleUtilisateur.SCOLARITE, RoleUtilisateur.ENSEIGNANT],
        is_active=True,
    ).order_by("username")


class FormationForm(forms.ModelForm):
    class Meta:
        model = Formation
        fields = ["nom", "ues"]
        widgets = {
            "ues": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nom"].widget.attrs.setdefault("class", "input")
        self.fields["ues"].queryset = UE.objects.order_by("nom")


class UEForm(forms.ModelForm):
    class Meta:
        model = UE
        fields = ["nom", "responsables"]
        widgets = {
            "responsables": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsables"].queryset = _responsables_queryset()
        self.fields["nom"].widget.attrs.setdefault("class", "input")


class UPForm(forms.ModelForm):
    class Meta:
        model = UP
        fields = ["ue", "nom", "matiere", "responsables"]
        widgets = {
            "responsables": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsables"].queryset = _responsables_queryset()
        for field_name in ("ue", "nom", "matiere"):
            self.fields[field_name].widget.attrs.setdefault("class", "input")
