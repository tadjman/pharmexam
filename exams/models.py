import uuid
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from academics.models import Formation, UE


class StatutExamen(models.TextChoices):
    INITIE = "INITIE", "Initié"
    INCOMPLET = "INCOMPLET", "Incomplet"
    COMPLET = "COMPLET", "Complet"
    TERMINE = "TERMINE", "Terminé"


SESSION_NAME_ORDER = {
    "Semestre 1": 1,
    "Semestre 2": 2,
    "Rattrapages": 3,
}


def build_session_order_expression(field_name: str = "nom"):
    return Case(
        *[
            When(**{field_name: session_name}, then=Value(order))
            for session_name, order in SESSION_NAME_ORDER.items()
        ],
        default=Value(99),
        output_field=IntegerField(),
    )


class SessionExamen(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    formation = models.ForeignKey(
        Formation,
        on_delete=models.PROTECT,
        related_name="sessions",
    )
    nom = models.CharField(max_length=255)

    class Meta:
        unique_together = [("formation", "nom")]
        ordering = ["formation__nom", "nom"]

    @classmethod
    def ordered_queryset(cls, queryset=None):
        if queryset is None:
            queryset = cls.objects.all()
        return queryset.annotate(
            sort_order=build_session_order_expression()
        ).order_by("formation__nom", "sort_order", "nom")

    def __str__(self) -> str:
        return f"{self.formation.nom} - {self.nom}"


class Examen(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        SessionExamen,
        on_delete=models.PROTECT,
        related_name="examens",
    )
    ue = models.ForeignKey(UE, on_delete=models.PROTECT, related_name="examens")
    nom = models.CharField(max_length=255)
    date = models.DateField()
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    statut = models.CharField(
        max_length=12,
        choices=StatutExamen.choices,
        default=StatutExamen.INITIE,
    )

    class Meta:
        ordering = ["date", "heure_debut"]
        unique_together = [("session", "ue")]

    @property
    def accent_color(self) -> str:
        return self.ue.couleur or "#4F46E5"

    @property
    def start_dt(self) -> datetime:
        naive = datetime.combine(self.date, self.heure_debut)
        return timezone.make_aware(naive, timezone.get_current_timezone())

    @property
    def end_dt(self) -> datetime:
        naive = datetime.combine(self.date, self.heure_fin)
        return timezone.make_aware(naive, timezone.get_current_timezone())

    @property
    def duree_minutes(self) -> int:
        delta = self.end_dt - self.start_dt
        return max(0, int(delta.total_seconds() // 60))

    @property
    def surveillants_requis_total(self) -> int:
        return sum(
            affectation.nb_surveillants_requis
            for affectation in self.affectations_salles.all()
        )

    @property
    def surveillants_inscrits_total(self) -> int:
        return sum(
            affectation.surveillances.count()
            for affectation in self.affectations_salles.all()
        )

    @property
    def surveillances(self):
        from assignments.models import Surveillance

        return Surveillance.objects.filter(affectation_salle__examen=self)

    def clean(self):
        errors = {}

        if self.heure_debut is not None and self.heure_fin is not None and self.heure_fin <= self.heure_debut:
            errors["heure_fin"] = "L'heure de fin doit être postérieure à l'heure de début."

        if self.session_id and self.date:
            year = self.session.formation.annee_universitaire
            if self.date < year.date_debut or self.date > year.date_fin:
                errors["date"] = "La date de l'examen doit se situer dans l'année universitaire de la session choisie."

        if self.session_id and self.ue_id:
            if not self.session.formation.ues.filter(pk=self.ue_id).exists():
                errors["ue"] = "L'UE choisie doit être rattachée à la formation de la session."
            elif (
                Examen.objects.filter(session=self.session, ue=self.ue)
                .exclude(pk=self.pk)
                .exists()
            ):
                errors["ue"] = "Un examen existe déjà pour cette UE dans la session sélectionnée."

        if (
            self.pk
            and self.date is not None
            and self.heure_debut is not None
            and self.heure_fin is not None
        ):
            from rooms.models import AffectationSalle

            current_start = self.start_dt
            current_end = self.end_dt
            affectations = self.affectations_salles.select_related("salle")
            for affectation in affectations:
                current_lock_start = affectation.get_lock_start_dt(start_dt=current_start)
                current_lock_end = affectation.get_lock_end_dt(start_dt=current_start, end_dt=current_end)
                conflicting_affectations = AffectationSalle.objects.filter(salle=affectation.salle).exclude(
                    pk=affectation.pk
                ).select_related("examen")
                for other in conflicting_affectations:
                    if (current_lock_start < other.lock_end_dt) and (other.lock_start_dt < current_lock_end):
                        errors["date"] = (
                            f"L'examen ne peut pas être déplacé sur ce créneau : la salle "
                            f"{affectation.salle.nom} est déjà verrouillée pour l'examen "
                            f"'{other.examen.nom}'."
                        )
                        break
                if "date" in errors:
                    break

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.ue_id:
            self.nom = self.ue.nom
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                update_fields = set(update_fields)
                update_fields.add("nom")
                kwargs["update_fields"] = update_fields
        super().save(*args, **kwargs)

    def is_termine(self) -> bool:
        return timezone.now() >= self.end_dt

    def compute_statut(self) -> str:
        affectations = list(self.affectations_salles.prefetch_related("surveillances"))
        if not affectations:
            return StatutExamen.INITIE

        room_completion = [
            affectation.surveillances.count() >= affectation.nb_surveillants_requis
            for affectation in affectations
        ]
        if room_completion and all(room_completion):
            if self.is_termine():
                return StatutExamen.TERMINE
            return StatutExamen.COMPLET
        return StatutExamen.INCOMPLET

    def update_statut(self, save: bool = True) -> str:
        new_statut = self.compute_statut()
        if save and self.pk and self.statut != new_statut:
            Examen.objects.filter(pk=self.pk).update(statut=new_statut)
            self.statut = new_statut
        return new_statut

    def __str__(self) -> str:
        return f"{self.nom} ({self.date} {self.heure_debut}-{self.heure_fin})"
