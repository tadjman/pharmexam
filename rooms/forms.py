from django import forms
from django.core.exceptions import ValidationError

from .models import AffectationSalle, Salle


class SalleForm(forms.ModelForm):
    class Meta:
        model = Salle
        fields = ["nom", "capacite"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_creation = self.instance._state.adding
        for field in self.fields.values():
            if not getattr(field.widget, "attrs", None):
                field.widget.attrs = {}
            field.widget.attrs.setdefault("class", "input")


class AffectationSalleForm(forms.ModelForm):
    class Meta:
        model = AffectationSalle
        fields = ["salle", "temps_majore", "nb_surveillants_requis"]

    def __init__(self, *args, **kwargs):
        self.examen = kwargs.pop("examen")
        super().__init__(*args, **kwargs)
        self.fields["salle"].queryset = Salle.objects.order_by("nom")

        for field in self.fields.values():
            if not getattr(field.widget, "attrs", None):
                field.widget.attrs = {}
            field.widget.attrs.setdefault("class", "input")

    def clean(self):
        cleaned_data = super().clean()
        instance = self.instance

        # Injecte l'examen dans l'instance pour que les règles de conflit de créneau
        # soient validées correctement dans Model.clean().
        instance.examen = self.examen
        if self.errors:
            return cleaned_data
        nb_surveillants_requis = cleaned_data.get("nb_surveillants_requis")
        if nb_surveillants_requis is None:
            raise ValidationError("Renseigne le nombre de surveillants requis pour cette salle.")
        return cleaned_data
