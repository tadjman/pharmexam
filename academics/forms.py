from django import forms

from accounts.models import RoleUtilisateur, User

from .models import AnneeUniversitaire, Formation, UE


class AnneeUniversitaireForm(forms.ModelForm):
    class Meta:
        model = AnneeUniversitaire
        fields = ["date_debut", "date_fin", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_creation = self.instance._state.adding
        self.fields["date_debut"].widget.attrs.setdefault("class", "input")
        self.fields["date_fin"].widget.attrs.setdefault("class", "input")


def _responsables_queryset():
    return User.objects.filter(
        role__in=[RoleUtilisateur.SCOLARITE, RoleUtilisateur.ENSEIGNANT],
        is_active=True,
    ).order_by("username")


class FormationForm(forms.ModelForm):
    FORMATION_YEAR_LABEL_CHOICES = (
        ("Année unique", "Année unique"),
        ("1ère année", "1ère année"),
        ("2ème année", "2ème année"),
        ("3ème année", "3ème année"),
        ("4ème année", "4ème année"),
        ("5ème année", "5ème année"),
    )

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
        self.is_creation = self.instance._state.adding
        if self.is_creation:
            self.fields["formation_year_label"] = forms.ChoiceField(
                choices=self.FORMATION_YEAR_LABEL_CHOICES,
                initial="Année unique",
            )
            self.fields["formation_year_label"].widget.attrs.setdefault("class", "input")

    def clean(self):
        cleaned_data = super().clean()
        if "formation_year_label" not in self.fields:
            return cleaned_data

        nom = (cleaned_data.get("nom") or "").strip()
        year_label = cleaned_data.get("formation_year_label")
        if not nom or not year_label:
            return cleaned_data

        for _, label in self.FORMATION_YEAR_LABEL_CHOICES:
            suffix = f" ({label})"
            if nom.endswith(suffix):
                nom = nom[: -len(suffix)].rstrip()
                break

        if year_label == "Année unique":
            cleaned_data["nom"] = nom
        else:
            cleaned_data["nom"] = f"{nom} ({year_label})"
        self.instance.nom = cleaned_data["nom"]
        return cleaned_data


class UEForm(forms.ModelForm):
    class Meta:
        model = UE
        fields = ["code_ue", "nom", "responsables"]
        widgets = {
            "responsables": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_creation = self.instance._state.adding
        self.fields["responsables"].queryset = _responsables_queryset()
        self.fields["code_ue"].required = False
        self.fields["code_ue"].widget.attrs.setdefault("class", "input")
        self.fields["nom"].widget.attrs.setdefault("class", "input")

    def clean_code_ue(self):
        return (self.cleaned_data.get("code_ue") or "").strip().upper().replace(" ", "")
