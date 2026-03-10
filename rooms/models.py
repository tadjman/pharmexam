import uuid
from django.core.exceptions import ValidationError
from django.db.models.signals import post_delete, post_save
from django.db import models
from django.dispatch import receiver

from exams.models import Examen


class Salle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    nom = models.CharField(max_length=255, unique=True)
    capacite_max = models.PositiveIntegerField()

    # Optionnel si tu as des règles d'ouverture/fermeture
    heure_verrouillage = models.TimeField(null=True, blank=True)
    heure_deverrouillage = models.TimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.nom} ({self.capacite_max})"


class AffectationSalle(models.Model):
    """
    Affecte une salle à un examen.
    - is_tiers_temps : identifie la salle dédiée tiers-temps (si besoin)
    - capacite_reservee : optionnel si tu veux répartir les candidats par salle
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    examen = models.ForeignKey(
        Examen,
        on_delete=models.CASCADE,
        related_name="affectations_salles",
    )
    salle = models.ForeignKey(
        Salle,
        on_delete=models.PROTECT,
        related_name="affectations",
    )

    is_tiers_temps = models.BooleanField(default=False)
    capacite_reservee = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = [("examen", "salle")]

    @property
    def capacite_effective(self) -> int:
        return self.capacite_reservee if self.capacite_reservee is not None else self.salle.capacite_max

    def clean(self):
        if self.examen_id is None or self.salle_id is None:
            return

        if self.capacite_reservee is not None and self.capacite_reservee <= 0:
            raise ValidationError(
                {"capacite_reservee": "La capacité réservée doit être strictement positive."}
            )
        if self.capacite_reservee is not None and self.capacite_reservee > self.salle.capacite_max:
            raise ValidationError(
                {
                    "capacite_reservee": (
                        f"La capacité réservée ne peut pas dépasser la capacité maximale de la salle "
                        f"({self.salle.capacite_max} places)."
                    )
                }
            )

        qs = AffectationSalle.objects.filter(salle=self.salle).exclude(pk=self.pk).select_related("examen")
        for a in qs:
            e = a.examen
            if (self.examen.start_dt < e.end_dt) and (e.start_dt < self.examen.end_dt):
                raise ValidationError(
                    {
                        "salle": (
                            f"La salle {self.salle.nom} est déjà affectée à l'examen "
                            f"'{e.nom}' sur ce créneau."
                        )
                    }
                )

        if self.is_tiers_temps:
            exists = AffectationSalle.objects.filter(examen=self.examen, is_tiers_temps=True).exclude(pk=self.pk).exists()
            if exists:
                raise ValidationError(
                    {"is_tiers_temps": "Une seule salle tiers-temps peut être définie par examen."}
                )

    def __str__(self) -> str:
        tag = " (tiers-temps)" if self.is_tiers_temps else ""
        return f"{self.examen} -> {self.salle}{tag}"


@receiver(post_save, sender=AffectationSalle)
@receiver(post_delete, sender=AffectationSalle)
def update_exam_status_after_room_change(sender, instance, **kwargs):
    instance.examen.update_statut(save=True)
