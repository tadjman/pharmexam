from django import forms

from accounts.models import RoleUtilisateur, User

from .models import Formation, UE, UP


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


class FormationFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Recherche")
    ue = forms.ModelChoiceField(
        queryset=UE.objects.order_by("nom"),
        required=False,
        label="UE",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["q"].widget.attrs.setdefault("class", "input")
        self.fields["q"].widget.attrs.setdefault("placeholder", "Nom de la formation")
        self.fields["ue"].widget.attrs.setdefault("class", "input")


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


class UEFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Recherche")
    responsable = forms.ModelChoiceField(
        queryset=_responsables_queryset(),
        required=False,
        label="Responsable",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["q"].widget.attrs.setdefault("class", "input")
        self.fields["q"].widget.attrs.setdefault("placeholder", "Nom de l'UE")
        self.fields["responsable"].widget.attrs.setdefault("class", "input")


class UPFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Recherche")
    ue = forms.ModelChoiceField(
        queryset=UE.objects.order_by("nom"),
        required=False,
        label="UE",
    )
    responsable = forms.ModelChoiceField(
        queryset=_responsables_queryset(),
        required=False,
        label="Responsable",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["q"].widget.attrs.setdefault("class", "input")
        self.fields["q"].widget.attrs.setdefault("placeholder", "Nom ou matière")
        self.fields["ue"].widget.attrs.setdefault("class", "input")
        self.fields["responsable"].widget.attrs.setdefault("class", "input")
