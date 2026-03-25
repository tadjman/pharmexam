import uuid
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from academics.models import Formation, UP


class StatutExamen(models.TextChoices):
    INITIE = "INITIE", "Initié"
    INCOMPLET = "INCOMPLET", "Incomplet"
    COMPLET = "COMPLET", "Complet"
    TERMINE = "TERMINE", "Terminé"


class SessionExamen(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    formation = models.ForeignKey(
        Formation,
        on_delete=models.PROTECT,
        related_name="sessions",
    )
    nom = models.CharField(max_length=255)
    date_debut = models.DateField()
    date_fin = models.DateField()

    class Meta:
        unique_together = [("formation", "nom")]
        ordering = ["formation__nom", "-date_debut", "nom"]

    def clean(self):
        errors = {}

        if self.date_debut and self.date_fin and self.date_fin < self.date_debut:
            errors["date_fin"] = "La date de fin doit être postérieure ou égale à la date de début."

        if self.formation_id and self.date_debut and self.date_fin:
            year = self.formation.annee_universitaire
            if self.date_debut < year.date_debut:
                errors["date_debut"] = "La session doit commencer dans les bornes de l'année universitaire."
            if self.date_fin > year.date_fin:
                errors["date_fin"] = "La session doit se terminer dans les bornes de l'année universitaire."

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.formation.nom} - {self.nom}"


class Examen(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        SessionExamen,
        on_delete=models.PROTECT,
        related_name="examens",
    )
    up = models.ForeignKey(UP, on_delete=models.PROTECT, related_name="examens")
    nom = models.CharField(max_length=255)
    date = models.DateField()
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    nb_eleves = models.PositiveIntegerField()
    nb_eleves_tiers_temps = models.PositiveIntegerField(default=0)
    nb_surveillants_requis = models.PositiveIntegerField(default=1)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="examens_responsable",
    )
    statut = models.CharField(
        max_length=12,
        choices=StatutExamen.choices,
        default=StatutExamen.INITIE,
    )

    class Meta:
        ordering = ["date", "heure_debut"]

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
    def duree_tiers_temps_minutes(self) -> int:
        return int(self.duree_minutes * 4 / 3)

    def clean(self):
        errors = {}

        if self.heure_debut is not None and self.heure_fin is not None and self.heure_fin <= self.heure_debut:
            errors["heure_fin"] = "L'heure de fin doit être postérieure à l'heure de début."

        if (
            self.nb_eleves is not None
            and self.nb_eleves_tiers_temps is not None
            and self.nb_eleves_tiers_temps > self.nb_eleves
        ):
            errors["nb_eleves_tiers_temps"] = (
                "Le nombre d'élèves tiers-temps ne peut pas dépasser le nombre total d'élèves."
            )

        if self.session_id and self.date:
            if self.date < self.session.date_debut or self.date > self.session.date_fin:
                errors["date"] = "La date de l'examen doit se situer dans la période de la session choisie."

        if self.session_id and self.up_id:
            if not self.session.formation.ues.filter(pk=self.up.ue_id).exists():
                errors["up"] = "L'UP choisie doit appartenir à une UE rattachée à la formation de la session."

        if self.up_id and self.responsable_id:
            ue = self.up.ue
            user = self.responsable
            ok_ue = ue.responsables.filter(pk=user.pk).exists()
            ok_up = self.up.responsables.filter(pk=user.pk).exists()
            if not (ok_ue or ok_up):
                errors["responsable"] = "Le responsable sélectionné doit être rattaché à l'UE ou à l'UP choisie."

        if errors:
            raise ValidationError(errors)

    def is_termine(self) -> bool:
        return timezone.now() >= self.end_dt

    def compute_statut(self) -> str:
        if self.is_termine():
            return StatutExamen.TERMINE

        affectations = self.affectations_salles.select_related("salle")
        surveillants_count = self.surveillances.count()
        has_any_completion = affectations.exists() or surveillants_count > 0

        total_capacity = sum(affectation.capacite_effective for affectation in affectations)
        tiers_required = self.nb_eleves_tiers_temps > 0
        tiers_ok = (not tiers_required) or affectations.filter(is_tiers_temps=True).exists()
        rooms_ok = affectations.exists() and total_capacity >= self.nb_eleves and tiers_ok
        surveillants_ok = surveillants_count >= self.nb_surveillants_requis

        if rooms_ok and surveillants_ok:
            return StatutExamen.COMPLET
        if has_any_completion:
            return StatutExamen.INCOMPLET
        return StatutExamen.INITIE

    def update_statut(self, save: bool = True) -> str:
        new_statut = self.compute_statut()
        if save and self.pk and self.statut != new_statut:
            Examen.objects.filter(pk=self.pk).update(statut=new_statut)
            self.statut = new_statut
        return new_statut

    def __str__(self) -> str:
        return f"{self.nom} ({self.date} {self.heure_debut}-{self.heure_fin})"
