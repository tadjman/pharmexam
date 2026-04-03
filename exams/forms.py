from django import forms
from django.db.models import Q

from academics.models import Formation, UE
from accounts.models import RoleUtilisateur
from rooms.models import AffectationSalle, Salle

from .models import Examen, SessionExamen


class SessionForm(forms.ModelForm):
    class Meta:
        model = SessionExamen
        fields = ["formation", "nom"]

    def __init__(self, *args, **kwargs):
        active_year = kwargs.pop("active_year", None)
        super().__init__(*args, **kwargs)
        self.is_creation = self.instance._state.adding

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
            "ue",
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
        self.is_creation = self.instance._state.adding

        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "input")

        sessions_qs = SessionExamen.objects.none()
        if active_year is not None:
            sessions_qs = SessionExamen.ordered_queryset(
                SessionExamen.objects.select_related("formation").filter(
                formation__annee_universitaire=active_year
                )
            )
        self.fields["session"].queryset = sessions_qs

        selected_session = None
        session_id = self.data.get("session") or self.initial.get("session")
        if not session_id and self.instance.pk:
            session_id = self.instance.session_id
        if session_id:
            selected_session = sessions_qs.filter(pk=session_id).first() or SessionExamen.objects.filter(pk=session_id).first()

        ues_qs = UE.objects.order_by("nom")
        if selected_session is not None:
            ues_qs = ues_qs.filter(formations=selected_session.formation)
        elif active_year is not None:
            ues_qs = ues_qs.filter(formations__annee_universitaire=active_year)
        self.fields["ue"].queryset = ues_qs.distinct()


class ExamCompletionRoomForm(forms.ModelForm):
    class Meta:
        model = AffectationSalle
        fields = ["salle", "temps_majore", "nb_surveillants_requis"]

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


class SelfRoomRegistrationForm(forms.Form):
    is_responsable_general = forms.BooleanField(required=False)
    is_responsable_salle = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        general_available = kwargs.pop("general_available", True)
        room_available = kwargs.pop("room_available", True)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "input")
        if not general_available:
            self.fields["is_responsable_general"].disabled = True
        if not room_available:
            self.fields["is_responsable_salle"].disabled = True


class AdminRoomRegistrationForm(SelfRoomRegistrationForm):
    email = forms.EmailField()

    field_order = [
        "email",
        "is_responsable_general",
        "is_responsable_salle",
    ]


class AdminNewUserRoleChoiceForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField(widget=forms.HiddenInput())
    is_responsable_general = forms.BooleanField(required=False, widget=forms.HiddenInput())
    is_responsable_salle = forms.BooleanField(required=False, widget=forms.HiddenInput())
    role = forms.ChoiceField(
        choices=RoleUtilisateur.choices,
        widget=forms.RadioSelect,
        initial=RoleUtilisateur.MEMBRE_POOL,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].widget.attrs.setdefault("class", "input")
        self.fields["last_name"].widget.attrs.setdefault("class", "input")
        self.fields["role"].widget.attrs.setdefault("class", "responsable-picker")


class SurveillanceResponsibilityForm(forms.Form):
    is_responsable_general = forms.BooleanField(required=False)
    is_responsable_salle = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "input")
