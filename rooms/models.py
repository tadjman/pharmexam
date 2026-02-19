from django.db import models

# Create your models here.
import uuid
from django.core.exceptions import ValidationError
from django.db import models

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

    def clean(self):
        # 1) capacité réservée cohérente
        if self.capacite_reservee is not None and self.capacite_reservee > self.salle.capacite_max:
            raise ValidationError("capacite_reservee ne peut pas dépasser capacite_max de la salle.")

        # 2) empêcher chevauchement : même salle sur même créneau
        # (simple, côté application — robuste en pratique si tu l'utilises dans un service transactionnel)
        qs = AffectationSalle.objects.filter(salle=self.salle).exclude(pk=self.pk).select_related("examen")
        for a in qs:
            e = a.examen
            if (self.examen.start_dt < e.end_dt) and (e.start_dt < self.examen.end_dt):
                raise ValidationError("Conflit: cette salle est déjà utilisée sur ce créneau.")

        # 3) une seule salle tiers-temps par examen (si tu veux cette règle)
        if self.is_tiers_temps:
            exists = AffectationSalle.objects.filter(examen=self.examen, is_tiers_temps=True).exclude(pk=self.pk).exists()
            if exists:
                raise ValidationError("Il ne peut y avoir qu'une seule salle tiers-temps par examen.")

    def __str__(self) -> str:
        tag = " (tiers-temps)" if self.is_tiers_temps else ""
        return f"{self.examen} -> {self.salle}{tag}"
