from django import forms

from accounts.models import RoleUtilisateur, User
from exams.models import Examen, SessionExamen

from .models import Surveillance


class SurveillanceForm(forms.ModelForm):
    class Meta:
        model = Surveillance
        fields = ["examen", "surveillant"]

    def __init__(self, *args, **kwargs):
        active_year = kwargs.pop("active_year")
        request_user = kwargs.pop("request_user")
        super().__init__(*args, **kwargs)

        self.fields["examen"].queryset = Examen.objects.filter(
            session__annee_universitaire=active_year
        ).select_related("session").order_by("date", "heure_debut")

        allowed_roles = [RoleUtilisateur.MEMBRE_POOL, RoleUtilisateur.ENSEIGNANT]
        self.fields["surveillant"].queryset = User.objects.filter(
            role__in=allowed_roles,
            is_active=True,
        ).order_by("username")

        for field in self.fields.values():
            if not getattr(field.widget, "attrs", None):
                field.widget.attrs = {}
            field.widget.attrs.setdefault("class", "input")

        is_admin = (
            request_user.is_superuser
            or request_user.is_staff
            or getattr(request_user, "role", "") == RoleUtilisateur.SCOLARITE
        )

        if not is_admin:
            self.fields["surveillant"].queryset = User.objects.filter(pk=request_user.pk)
            self.fields["surveillant"].initial = request_user.pk
            self.fields["surveillant"].disabled = True


class SurveillanceFilterForm(forms.Form):
    session = forms.ModelChoiceField(queryset=SessionExamen.objects.none(), required=False)
    examen = forms.ModelChoiceField(queryset=Examen.objects.none(), required=False)
    surveillant = forms.ModelChoiceField(queryset=User.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        active_year = kwargs.pop("active_year")
        super().__init__(*args, **kwargs)

        sessions_qs = SessionExamen.objects.filter(annee_universitaire=active_year).order_by("-date_debut")
        examens_qs = Examen.objects.filter(session__annee_universitaire=active_year).select_related("session").order_by(
            "date", "heure_debut"
        )

        allowed_roles = [RoleUtilisateur.MEMBRE_POOL, RoleUtilisateur.ENSEIGNANT]
        surveillants_qs = User.objects.filter(role__in=allowed_roles, is_active=True).order_by("username")

        self.fields["session"].queryset = sessions_qs
        self.fields["examen"].queryset = examens_qs
        self.fields["surveillant"].queryset = surveillants_qs

        for field in self.fields.values():
            if not getattr(field.widget, "attrs", None):
                field.widget.attrs = {}
            field.widget.attrs.setdefault("class", "input")
