from django import forms
from django.forms import inlineformset_factory

from .models import DEFAULT_UP_NAME, AnneeUniversitaire, Formation, UE, UP


class AnneeUniversitaireForm(forms.ModelForm):
    class Meta:
        model = AnneeUniversitaire
        fields = ["date_debut", "date_fin", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_creation = self.instance._state.adding
        self.fields["date_debut"].widget.attrs.setdefault("class", "input")
        self.fields["date_fin"].widget.attrs.setdefault("class", "input")


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
        fields = ["nom"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nom"].widget.attrs.setdefault("class", "input")
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


def _formations_queryset():
    return Formation.objects.select_related("annee_universitaire").order_by(
        "-annee_universitaire__date_debut",
        "nom",
    )


def _ups_queryset():
    return UP.objects.exclude(nom=DEFAULT_UP_NAME).order_by("nom")


class UEForm(forms.ModelForm):
    class Meta:
        model = UE
        fields = ["formation", "code_ue", "nom", "ups"]
        widgets = {
            "ups": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_creation = self.instance._state.adding
        if self.is_creation:
            self.fields["formation"].queryset = _formations_queryset()
            self.fields["formation"].required = True
            self.fields["formation"].widget.attrs.setdefault("class", "input")
        else:
            self.fields.pop("formation")
        self.fields["ups"].queryset = _ups_queryset()
        self.fields["code_ue"].required = False
        self.fields["code_ue"].widget.attrs.setdefault("class", "input")
        self.fields["nom"].widget.attrs.setdefault("class", "input")

    def clean_code_ue(self):
        return (self.cleaned_data.get("code_ue") or "").strip().upper().replace(" ", "")


class UEInlineForm(forms.ModelForm):
    class Meta:
        model = UE
        fields = ["code_ue", "nom", "ups"]
        widgets = {
            "ups": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code_ue"].required = False
        self.fields["code_ue"].widget.attrs.setdefault("class", "input")
        self.fields["nom"].widget.attrs.setdefault("class", "input")
        self.fields["ups"].queryset = _ups_queryset()
        self.fields["ups"].required = False

    def clean_code_ue(self):
        return (self.cleaned_data.get("code_ue") or "").strip().upper().replace(" ", "")


FormationUEFormSet = inlineformset_factory(
    Formation,
    UE,
    form=UEInlineForm,
    fields=["code_ue", "nom", "ups"],
    extra=1,
    can_delete=False,
)


class UPForm(forms.ModelForm):
    class Meta:
        model = UP
        fields = ["nom"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_creation = self.instance._state.adding
        self.fields["nom"].widget.attrs.setdefault("class", "input")
