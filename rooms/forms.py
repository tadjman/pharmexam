from django import forms
from django.core.exceptions import ValidationError

from .models import AffectationSalle, Salle


class SalleForm(forms.ModelForm):
    class Meta:
        model = Salle
        fields = ["nom", "capacite_max", "heure_verrouillage", "heure_deverrouillage"]
        widgets = {
            "heure_verrouillage": forms.TimeInput(attrs={"type": "time", "class": "input"}),
            "heure_deverrouillage": forms.TimeInput(attrs={"type": "time", "class": "input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not getattr(field.widget, "attrs", None):
                field.widget.attrs = {}
            field.widget.attrs.setdefault("class", "input")


class AffectationSalleForm(forms.ModelForm):
    class Meta:
        model = AffectationSalle
        fields = ["salle", "is_tiers_temps", "capacite_reservee"]

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
        if self.errors:
            return cleaned_data

        salle = cleaned_data.get("salle")
        capacite_reservee = cleaned_data.get("capacite_reservee")
        is_tiers_temps = cleaned_data.get("is_tiers_temps", False)
        instance = self.instance

        projected_tiers = self.examen.affectations_salles.exclude(pk=instance.pk).filter(is_tiers_temps=True).count()
        if is_tiers_temps:
            projected_tiers += 1

        if self.examen.nb_eleves_tiers_temps > 0 and projected_tiers == 0:
            raise ValidationError("Une salle tiers-temps est obligatoire pour cet examen.")

        # En mise à jour, on bloque une régression de capacité globale.
        if instance.pk and salle is not None:
            current_capacity = capacite_reservee if capacite_reservee is not None else salle.capacite_max
            other_capacity = sum(
                a.capacite_effective for a in self.examen.affectations_salles.exclude(pk=instance.pk).select_related("salle")
            )
            if other_capacity + current_capacity < self.examen.nb_eleves:
                raise ValidationError(
                    f"Capacité totale insuffisante après modification: {other_capacity + current_capacity} / {self.examen.nb_eleves}."
                )

        # Injecte l'examen dans l'instance pour que les règles de conflit de créneau
        # soient validées correctement dans Model.clean().
        instance.examen = self.examen
        return cleaned_data
