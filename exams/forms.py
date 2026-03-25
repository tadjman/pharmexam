from django import forms
from django.db.models import Q

from academics.models import Formation, UP
from accounts.models import RoleUtilisateur, User
from assignments.models import Surveillance
from rooms.models import AffectationSalle, Salle

from .models import Examen, SessionExamen


class SessionForm(forms.ModelForm):
    class Meta:
        model = SessionExamen
        fields = ["formation", "nom", "date_debut", "date_fin"]
        widgets = {
            "date_debut": forms.DateInput(attrs={"type": "date", "class": "input"}),
            "date_fin": forms.DateInput(attrs={"type": "date", "class": "input"}),
        }

    def __init__(self, *args, **kwargs):
        active_year = kwargs.pop("active_year", None)
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "input")

        if active_year is not None:
            self.fields["formation"].queryset = Formation.objects.filter(
                annee_universitaire=active_year
            ).order_by("nom")
        else:
            self.fields["formation"].queryset = Formation.objects.none()


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

        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "input")

        sessions_qs = SessionExamen.objects.none()
        if active_year is not None:
            sessions_qs = SessionExamen.objects.select_related("formation").filter(
                formation__annee_universitaire=active_year
            ).order_by("formation__nom", "-date_debut", "nom")
        self.fields["session"].queryset = sessions_qs

        self.fields["responsable"].queryset = User.objects.filter(
            role__in=[RoleUtilisateur.SCOLARITE, RoleUtilisateur.ENSEIGNANT],
            is_active=True,
        ).order_by("username")

        selected_session = None
        session_id = self.data.get("session") or self.initial.get("session")
        if not session_id and self.instance.pk:
            session_id = self.instance.session_id
        if session_id:
            selected_session = sessions_qs.filter(pk=session_id).first() or SessionExamen.objects.filter(pk=session_id).first()

        ups_qs = UP.objects.select_related("ue").order_by("ue__nom", "nom")
        if selected_session is not None:
            ups_qs = ups_qs.filter(ue__formations=selected_session.formation)
        elif active_year is not None:
            ups_qs = ups_qs.filter(ue__formations__annee_universitaire=active_year)
        self.fields["up"].queryset = ups_qs.distinct()


class ExamCompletionRoomForm(forms.ModelForm):
    class Meta:
        model = AffectationSalle
        fields = ["salle", "is_tiers_temps", "capacite_reservee"]

    def __init__(self, *args, **kwargs):
        self.examen = kwargs.pop("examen")
        super().__init__(*args, **kwargs)
        salles = Salle.objects.order_by("nom")
        if self.instance.pk:
            self.fields["salle"].queryset = salles.filter(
                Q(pk=self.instance.salle_id) | ~Q(affectations__examen=self.examen)
            ).distinct()
        else:
            self.fields["salle"].queryset = salles.exclude(affectations__examen=self.examen)
        for field in self.fields.values():
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
