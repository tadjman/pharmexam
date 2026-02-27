from django import forms
from .models import Examen, SessionExamen
from accounts.models import RoleUtilisateur, User
from assignments.models import Surveillance
from rooms.models import AffectationSalle, Salle


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


class ExamCompletionRoomForm(forms.ModelForm):
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
        self.instance.examen = self.examen
        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.examen = self.examen
        if commit:
            obj.save()
        return obj


class ExamCompletionSurveillanceForm(forms.ModelForm):
    class Meta:
        model = Surveillance
        fields = ["surveillant"]

    def __init__(self, *args, **kwargs):
        self.examen = kwargs.pop("examen")
        super().__init__(*args, **kwargs)
        self.fields["surveillant"].queryset = User.objects.filter(
            role__in=[RoleUtilisateur.MEMBRE_POOL, RoleUtilisateur.ENSEIGNANT],
            is_active=True,
        ).order_by("username")
        for field in self.fields.values():
            if not getattr(field.widget, "attrs", None):
                field.widget.attrs = {}
            field.widget.attrs.setdefault("class", "input")

    def clean(self):
        cleaned_data = super().clean()
        self.instance.examen = self.examen
        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.examen = self.examen
        if commit:
            obj.save()
        return obj
