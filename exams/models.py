from django.db import models

# Create your models here.
import uuid
from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from academics.models import AnneeUniversitaire, UP


class StatutExamen(models.TextChoices):
    INITIE = "INITIE", "Initié"
    INCOMPLET = "INCOMPLET", "Incomplet"
    COMPLET = "COMPLET", "Complet"
    TERMINE = "TERMINE", "Terminé"


class SessionExamen(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    annee_universitaire = models.ForeignKey(
        AnneeUniversitaire,
        on_delete=models.PROTECT,
        related_name="sessions",
    )

    nom = models.CharField(max_length=255)
    date_debut = models.DateField()
    date_fin = models.DateField()

    class Meta:
        unique_together = [("annee_universitaire", "nom")]
        ordering = ["-date_debut"]

    def __str__(self) -> str:
        return f"{self.annee_universitaire.nom} - {self.nom}"


class Examen(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    session = models.ForeignKey(
        SessionExamen,
        on_delete=models.PROTECT,
        related_name="examens",
    )

    up = models.ForeignKey(UP, on_delete=models.PROTECT, related_name="examens")

    nom = models.CharField(max_length=255)

    # Version "simple" comme ton cahier des charges
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

    # --- Helpers horaires (pratique pour conflits) ---
    @property
    def start_dt(self) -> datetime:
        # timezone aware
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
        # tiers-temps "classique" = + 1/3
        return int(self.duree_minutes * 4 / 3)

    def clean(self):
        # Pendant la validation ModelForm, certains champs peuvent être None.
        # On laisse d'abord les validations "required" remonter proprement.
        if self.heure_debut is None or self.heure_fin is None:
            return

        # heures cohérentes
        if self.heure_fin <= self.heure_debut:
            raise ValidationError("L'heure de fin doit être > à l'heure de début.")

        # tiers-temps cohérent
        if (
            self.nb_eleves is not None
            and self.nb_eleves_tiers_temps is not None
            and self.nb_eleves_tiers_temps > self.nb_eleves
        ):
            raise ValidationError("nb_eleves_tiers_temps ne peut pas dépasser nb_eleves.")

        # responsable doit être responsable de l'UE (ou UP) liée
        if self.up_id is None or self.responsable_id is None:
            return

        ue = self.up.ue
        user = self.responsable
        ok_ue = ue.responsables.filter(pk=user.pk).exists()
        ok_up = self.up.responsables.filter(pk=user.pk).exists()
        if not (ok_ue or ok_up):
            raise ValidationError("Le responsable doit appartenir aux responsables de l'UE ou de l'UP.")

    def is_termine(self) -> bool:
        return timezone.now() >= self.end_dt

    def compute_statut(self) -> str:
        if self.is_termine():
            return StatutExamen.TERMINE

        affectations = self.affectations_salles.select_related("salle")
        surveillants_count = self.surveillances.count()

        has_any_completion = affectations.exists() or surveillants_count > 0

        total_capacity = sum(a.capacite_effective for a in affectations)
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
