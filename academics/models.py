from datetime import date, timedelta
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class AnneeUniversitaire(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=20, unique=True)
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

    class Meta:
        ordering = ["nom"]

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
        ordering = ["ue__nom", "nom"]

    def __str__(self) -> str:
        return f"{self.ue.nom} - {self.nom}"


class Formation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    annee_universitaire = models.ForeignKey(
        AnneeUniversitaire,
        on_delete=models.PROTECT,
        related_name="formations",
    )
    nom = models.CharField(max_length=255)
    ues = models.ManyToManyField(UE, related_name="formations", blank=True)

    class Meta:
        unique_together = [("annee_universitaire", "nom")]
        ordering = ["nom"]

    def _default_session_periods(self):
        year = self.annee_universitaire
        start = year.date_debut
        end = year.date_fin
        total_days = max(1, (end - start).days + 1)
        first_block = total_days // 3
        second_block = (total_days * 2) // 3

        first_end = start + timedelta(days=max(0, first_block - 1))
        second_start = first_end + timedelta(days=1)
        second_end = start + timedelta(days=max(0, second_block - 1))
        third_start = second_end + timedelta(days=1)

        return [
            ("Semestre 1", start, min(first_end, end)),
            ("Semestre 2", min(second_start, end), min(second_end, end)),
            ("Rattrapages", min(third_start, end), end),
        ]

    def create_default_sessions(self):
        from exams.models import SessionExamen

        for nom, date_debut, date_fin in self._default_session_periods():
            SessionExamen.objects.get_or_create(
                formation=self,
                nom=nom,
                defaults={
                    "date_debut": date_debut,
                    "date_fin": date_fin,
                },
            )

    def save(self, *args, **kwargs):
        is_creation = self._state.adding
        super().save(*args, **kwargs)
        if is_creation:
            self.create_default_sessions()

    def __str__(self) -> str:
        return f"{self.annee_universitaire.nom} - {self.nom}"
