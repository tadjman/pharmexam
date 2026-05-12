from django import forms
from django.db.models import Q

from academics.models import DEFAULT_UP_NAME, Formation, UE, UP
from accounts.models import RoleUtilisateur
from rooms.models import AffectationSalle, Salle

from .models import Examen, ExamenUPCoefficient, SessionExamen


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
            "ue",
            "date",
            "heure_debut",
            "heure_fin",
        ]
        widgets = {
            "date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date", "class": "input"},
            ),
            "heure_debut": forms.TimeInput(
                format="%H:%M",
                attrs={"type": "time", "class": "input"},
            ),
            "heure_fin": forms.TimeInput(
                format="%H:%M",
                attrs={"type": "time", "class": "input"},
            ),
        }

    def __init__(self, *args, **kwargs):
        active_year = kwargs.pop("active_year", None)
        super().__init__(*args, **kwargs)
        self.is_creation = self.instance._state.adding
        self.up_coefficient_groups = []
        self.selected_ue_id = ""
        self.has_selected_up_group = False
        self.default_up = UP.get_default_up()

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

        ues_qs = UE.objects.select_related("formation").order_by("nom")
        if selected_session is not None:
            used_ue_ids = Examen.objects.filter(session=selected_session).exclude(pk=self.instance.pk).values_list(
                "ue_id",
                flat=True,
            )
            ues_qs = ues_qs.filter(formation=selected_session.formation).exclude(pk__in=used_ue_ids)
        elif active_year is not None:
            ues_qs = ues_qs.filter(formation__annee_universitaire=active_year)
        self.fields["ue"].queryset = ues_qs.distinct().prefetch_related("ups")

        selected_ue_id = self.data.get("ue") or self.initial.get("ue")
        if not selected_ue_id and self.instance.pk:
            selected_ue_id = str(self.instance.ue_id)
        self.selected_ue_id = str(selected_ue_id) if selected_ue_id else ""

        existing_coefficients = {}
        if self.instance.pk:
            existing_coefficients = {
                coefficient.up_id: coefficient.coefficient
                for coefficient in self.instance.up_coefficients.select_related("up")
            }

        for ue in self.fields["ue"].queryset:
            entries = []
            for up in self._get_coefficient_ups_for_ue(ue):
                field_name = self._build_up_coefficient_field_name(ue.pk, up.pk)
                self.fields[field_name] = forms.IntegerField(
                    required=False,
                    min_value=0,
                    widget=forms.NumberInput(attrs={"class": "input", "step": 1, "inputmode": "numeric"}),
                )
                if self.instance.pk and self.instance.ue_id == ue.pk and up.pk in existing_coefficients:
                    self.initial[field_name] = existing_coefficients[up.pk]
                entries.append(
                    {
                        "up": up,
                        "field_name": field_name,
                        "field": self[field_name],
                    }
                )
            is_selected = str(ue.pk) == self.selected_ue_id
            if is_selected:
                self.has_selected_up_group = True
            self.up_coefficient_groups.append(
                {
                    "ue": ue,
                    "ue_id": str(ue.pk),
                    "entries": entries,
                    "is_selected": is_selected,
                }
            )

    @staticmethod
    def _build_up_coefficient_field_name(ue_id, up_id):
        return f"up_coefficient__{ue_id}__{up_id}"

    def _get_coefficient_ups_for_ue(self, ue):
        specific_ups = list(ue.ups.exclude(pk=self.default_up.pk).order_by("nom"))
        return specific_ups + [self.default_up]

    def save(self, commit=True):
        exam = super().save(commit=commit)
        if not commit:
            return exam

        selected_ue = exam.ue
        relevant_ups = self._get_coefficient_ups_for_ue(selected_ue)
        relevant_up_ids = {up.pk for up in relevant_ups}

        ExamenUPCoefficient.objects.filter(examen=exam).exclude(up_id__in=relevant_up_ids).delete()

        for up in relevant_ups:
            field_name = self._build_up_coefficient_field_name(selected_ue.pk, up.pk)
            coefficient = self.cleaned_data.get(field_name)
            if coefficient in (None, ""):
                ExamenUPCoefficient.objects.filter(examen=exam, up=up).delete()
                continue
            ExamenUPCoefficient.objects.update_or_create(
                examen=exam,
                up=up,
                defaults={"coefficient": coefficient},
            )
        return exam


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

        self.room_recommendations = {
            str(salle.pk): salle.recommended_watchers
            for salle in self.fields["salle"].queryset
            if salle.recommended_watchers is not None
        }

        selected_room_id = self.data.get("salle")
        if not selected_room_id and self.instance.pk and self.instance.salle_id:
            selected_room_id = str(self.instance.salle_id)

        recommended_watchers = self.room_recommendations.get(str(selected_room_id or ""))
        if recommended_watchers is not None:
            self.fields["nb_surveillants_requis"].widget.attrs["placeholder"] = (
                f"Conseillé : {recommended_watchers}"
            )

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.setdefault("class", "input")
        self.fields["email"].widget.attrs.setdefault(
            "placeholder",
            "nouvel.utilisateur@example.com",
        )


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
    up = forms.ModelChoiceField(
        queryset=UP.objects.exclude(nom=DEFAULT_UP_NAME).order_by("nom"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].widget.attrs.setdefault("class", "input")
        self.fields["last_name"].widget.attrs.setdefault("class", "input")
        self.fields["role"].widget.attrs.setdefault("class", "responsable-picker")
        self.fields["up"].widget.attrs.setdefault("class", "input")

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        up = cleaned_data.get("up")
        if role == RoleUtilisateur.ENSEIGNANT and up is None:
            self.add_error("up", "Sélectionnez l'UP d'appartenance pour cet enseignant.")
        return cleaned_data


class SurveillanceResponsibilityForm(forms.Form):
    is_responsable_general = forms.BooleanField(required=False)
    is_responsable_salle = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "input")
