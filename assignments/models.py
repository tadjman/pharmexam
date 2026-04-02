import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from accounts.models import RoleUtilisateur
from rooms.models import AffectationSalle


class Surveillance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    affectation_salle = models.ForeignKey(
        AffectationSalle,
        on_delete=models.CASCADE,
        related_name="surveillances",
    )
    surveillant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="surveillances",
    )
    is_responsable_general = models.BooleanField(default=False)
    is_responsable_salle = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("affectation_salle", "surveillant")]

    @property
    def examen(self):
        return self.affectation_salle.examen

    @property
    def salle(self):
        return self.affectation_salle.salle

    def clean(self):
        if self.affectation_salle_id is None or self.surveillant_id is None:
            return

        errors = {}

        if self.surveillant.role not in {
            RoleUtilisateur.MEMBRE_POOL,
            RoleUtilisateur.ENSEIGNANT,
            RoleUtilisateur.SCOLARITE,
        }:
            errors["surveillant"] = (
                "Seuls les membres du pool, les enseignants et la scolarité "
                "peuvent être inscrits en surveillance."
            )

        count = Surveillance.objects.filter(affectation_salle=self.affectation_salle).exclude(pk=self.pk).count()
        if count >= self.affectation_salle.nb_surveillants_requis:
            errors["surveillant"] = (
                f"Le quota de surveillants est déjà atteint pour cette salle "
                f"({self.affectation_salle.nb_surveillants_requis} requis)."
            )

        if self.affectation_salle.is_registration_locked():
            errors["affectation_salle"] = (
                "Les inscriptions sont verrouillées pour cette salle sur la période définie."
            )

        already_on_exam = Surveillance.objects.filter(
            affectation_salle__examen=self.affectation_salle.examen,
            surveillant=self.surveillant,
        ).exclude(pk=self.pk)
        if already_on_exam.exists():
            errors["surveillant"] = "Ce surveillant est déjà inscrit sur une autre salle de cet examen."

        qs = Surveillance.objects.filter(surveillant=self.surveillant).exclude(pk=self.pk).select_related(
            "affectation_salle__examen"
        )
        for s in qs:
            e = s.affectation_salle.examen
            current_exam = self.affectation_salle.examen
            if (current_exam.start_dt < e.end_dt) and (e.start_dt < current_exam.end_dt):
                errors["surveillant"] = (
                    f"{self.surveillant.display_full_name} est déjà inscrit sur la salle "
                    f"'{s.affectation_salle.salle.nom}' de l'examen '{e.nom}' sur ce créneau."
                )
                break

        if self.is_responsable_general:
            if Surveillance.objects.filter(
                affectation_salle__examen=self.affectation_salle.examen,
                is_responsable_general=True,
            ).exclude(pk=self.pk).exists():
                errors["is_responsable_general"] = (
                    "Un responsable d'épreuve est déjà défini pour cet examen."
                )

        if self.is_responsable_salle:
            if Surveillance.objects.filter(
                affectation_salle=self.affectation_salle,
                is_responsable_salle=True,
            ).exclude(pk=self.pk).exists():
                errors["is_responsable_salle"] = "Un responsable de salle est déjà défini pour cette salle."

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.surveillant} surveille {self.salle} pour {self.examen}"


@receiver(post_save, sender=Surveillance)
@receiver(post_delete, sender=Surveillance)
def update_exam_status_after_surveillance_change(sender, instance, **kwargs):
    instance.affectation_salle.examen.update_statut(save=True)
