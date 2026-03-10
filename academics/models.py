import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models



class AnneeUniversitaire(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=20, unique=True)  # ex: "2024/2025"
    date_debut = models.DateField()
    date_fin = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date_debut"]

    def clean(self):
        if self.date_debut and self.date_fin and self.date_fin <= self.date_debut:
            raise ValidationError(
                {"date_fin": "La date de fin doit être postérieure à la date de début."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        if self.is_active:
            AnneeUniversitaire.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)

    def __str__(self) -> str:
        return self.nom


class UE(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=255, unique=True)

    responsables = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="ues_responsable",
        blank=True,
    )

    def __str__(self) -> str:
        return self.nom


class UP(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ue = models.ForeignKey(UE, on_delete=models.PROTECT, related_name="ups")

    nom = models.CharField(max_length=255)
    matiere = models.CharField(max_length=255, blank=True)

    responsables = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="ups_responsable",
        blank=True,
    )

    class Meta:
        unique_together = [("ue", "nom")]

    def __str__(self) -> str:
        return f"{self.ue.nom} - {self.nom}"
