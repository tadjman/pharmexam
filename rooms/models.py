import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from exams.models import Examen


class Salle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    nom = models.CharField(max_length=255, unique=True)
    capacite = models.PositiveIntegerField(null=True, blank=True)
    heure_debut_verrouillage = models.TimeField(null=True, blank=True)
    heure_fin_verrouillage = models.TimeField(null=True, blank=True)

    def clean(self):
        errors = {}
        if (
            self.heure_debut_verrouillage is not None
            and self.heure_fin_verrouillage is not None
            and self.heure_fin_verrouillage <= self.heure_debut_verrouillage
        ):
            errors["heure_fin_verrouillage"] = (
                "L'heure de fin de verrouillage doit être postérieure à l'heure de début."
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return self.nom


class AffectationSalle(models.Model):
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
    temps_majore = models.BooleanField(default=False)
    nb_surveillants_requis = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = [("examen", "salle")]

    @property
    def surveillants_inscrits(self) -> int:
        return self.surveillances.count()

    @property
    def places_restantes(self) -> int:
        return max(0, self.nb_surveillants_requis - self.surveillances.count())

    @property
    def is_complete(self) -> bool:
        return self.surveillances.count() >= self.nb_surveillants_requis

    def get_lock_start_dt(self, start_dt=None):
        return start_dt or self.examen.start_dt

    def get_lock_end_dt(self, start_dt=None, end_dt=None, temps_majore=None):
        current_start = self.get_lock_start_dt(start_dt=start_dt)
        current_end = end_dt or self.examen.end_dt
        uses_temps_majore = self.temps_majore if temps_majore is None else temps_majore
        if not uses_temps_majore:
            return current_end

        exam_duration = max(timedelta(), current_end - current_start)
        return current_end + (exam_duration / 3)

    @property
    def lock_start_dt(self):
        return self.get_lock_start_dt()

    @property
    def lock_end_dt(self):
        return self.get_lock_end_dt()

    def is_registration_locked(self, at_time=None) -> bool:
        current = at_time or timezone.now()
        if timezone.is_naive(current):
            current = timezone.make_aware(current, timezone.get_current_timezone())
        return self.lock_start_dt <= current <= self.lock_end_dt

    def clean(self):
        if self.examen_id is None or self.salle_id is None:
            return

        current_lock_start = self.lock_start_dt
        current_lock_end = self.lock_end_dt
        qs = AffectationSalle.objects.filter(salle=self.salle).exclude(pk=self.pk).select_related("examen")
        for a in qs:
            if (current_lock_start < a.lock_end_dt) and (a.lock_start_dt < current_lock_end):
                raise ValidationError(
                    {
                        "salle": (
                            f"La salle {self.salle.nom} est déjà affectée à l'examen "
                            f"'{a.examen.nom}' sur son créneau de verrouillage."
                        ),
                    }
                )

        if self.nb_surveillants_requis is None:
            raise ValidationError(
                {"nb_surveillants_requis": "Renseigne le nombre de surveillants requis pour cette salle."}
            )
        if self.nb_surveillants_requis <= 0:
            raise ValidationError(
                {"nb_surveillants_requis": "Le nombre de surveillants requis doit être strictement positif."}
            )
        if self.pk and self.surveillances.count() > self.nb_surveillants_requis:
            raise ValidationError(
                {
                    "nb_surveillants_requis": (
                        "Impossible de fixer un quota inférieur au nombre de surveillants déjà inscrits."
                    )
                }
            )

    def __str__(self) -> str:
        tag = " (temps majoré)" if self.temps_majore else ""
        return f"{self.examen} -> {self.salle}{tag}"


@receiver(post_save, sender=AffectationSalle)
@receiver(post_delete, sender=AffectationSalle)
def update_exam_status_after_room_change(sender, instance, **kwargs):
    instance.examen.update_statut(save=True)
