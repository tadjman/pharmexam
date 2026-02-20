from django import forms
from .models import Examen, SessionExamen


class ExamForm(forms.ModelForm):
    class Meta:
        model = Examen
        fields = [
            "session",
            "nom",
            "up",
            "responsable",
            "nb_eleves",
            "nb_eleves_tiers_temps",
            "nb_surveillants_requis",
            "date",
            "heure_debut",
            "heure_fin",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "input"}),
            "heure_debut": forms.TimeInput(attrs={"type": "time", "class": "input"}),
            "heure_fin": forms.TimeInput(attrs={"type": "time", "class": "input"}),
        }

    def __init__(self, *args, **kwargs):
        active_year = kwargs.pop("active_year", None)
        super().__init__(*args, **kwargs)

        # Style inputs (pour les champs auto-render)
        for name, field in self.fields.items():
            if not getattr(field.widget, "attrs", None):
                field.widget.attrs = {}
            field.widget.attrs.setdefault("class", "input")

        # Filtrer les sessions sur l'année active
        if active_year is not None:
            self.fields["session"].queryset = SessionExamen.objects.filter(annee_universitaire=active_year).order_by("-date_debut")