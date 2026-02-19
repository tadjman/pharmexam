from django.db import models

# Create your models here.
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from exams.models import Examen
from accounts.models import RoleUtilisateur


class Surveillance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    examen = models.ForeignKey(
        Examen,
        on_delete=models.CASCADE,
        related_name="surveillances",
    )
    surveillant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="surveillances",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("examen", "surveillant")]

    def clean(self):
        # 1) rôle autorisé
        if self.surveillant.role not in {RoleUtilisateur.MEMBRE_POOL, RoleUtilisateur.ENSEIGNANT}:
            raise ValidationError("Seuls les membres du pool (ou enseignants si autorisé) peuvent surveiller.")

        # 2) quota surveillants
        # (attention: si concurrence, faire ce check dans un service transactionnel)
        count = Surveillance.objects.filter(examen=self.examen).exclude(pk=self.pk).count()
        if count >= self.examen.nb_surveillants_requis:
            raise ValidationError("Quota de surveillants déjà atteint pour cet examen.")

        # 3) disponibilité: pas de chevauchement pour le surveillant
        qs = Surveillance.objects.filter(surveillant=self.surveillant).exclude(pk=self.pk).select_related("examen")
        for s in qs:
            e = s.examen
            if (self.examen.start_dt < e.end_dt) and (e.start_dt < self.examen.end_dt):
                raise ValidationError("Conflit: vous êtes déjà inscrit sur un examen sur ce créneau.")

    def __str__(self) -> str:
        return f"{self.surveillant} surveille {self.examen}"
