import uuid
from collections import Counter

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.dateparse import parse_date


UE_COLOR_PALETTE = (
    "#2563EB",
    "#1D4ED8",
    "#3B82F6",
    "#60A5FA",
    "#4F46E5",
    "#6366F1",
    "#7C3AED",
    "#8B5CF6",
    "#9333EA",
    "#A855F7",
    "#0EA5E9",
    "#0284C7",
    "#0891B2",
    "#475569",
    "#334155",
    "#D97706",
)


class AnneeUniversitaire(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=20, unique=True)
    date_debut = models.DateField()
    date_fin = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date_debut"]

    @property
    def generated_nom_base(self) -> str:
        if not self.date_debut or not self.date_fin:
            return ""
        date_debut = parse_date(self.date_debut) if isinstance(self.date_debut, str) else self.date_debut
        date_fin = parse_date(self.date_fin) if isinstance(self.date_fin, str) else self.date_fin
        if not date_debut or not date_fin:
            return ""
        return f"{date_debut.year}/{date_fin.year}"

    def generate_nom(self) -> str:
        base = self.generated_nom_base
        if not base:
            return self.nom

        siblings = AnneeUniversitaire.objects.exclude(pk=self.pk)
        if not siblings.filter(nom=base).exists():
            return base

        suffix = 2
        while siblings.filter(nom=f"{base} [{suffix}]").exists():
            suffix += 1
        return f"{base} [{suffix}]"

    def clean(self):
        if self.date_debut and self.date_fin and self.date_fin <= self.date_debut:
            raise ValidationError(
                {"date_fin": "La date de fin doit être postérieure à la date de début."}
            )

    def save(self, *args, **kwargs):
        if self.date_debut and self.date_fin:
            self.nom = self.generate_nom()
        self.full_clean()
        super().save(*args, **kwargs)
        if self.is_active:
            AnneeUniversitaire.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)

    def __str__(self) -> str:
        return self.nom


class UE(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code_ue = models.CharField(max_length=20, unique=True, null=True, blank=True)
    nom = models.CharField(max_length=255, unique=True)
    couleur = models.CharField(max_length=7, blank=True, default="")
    responsables = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="ues_responsable",
        blank=True,
    )

    class Meta:
        ordering = ["nom"]

    @property
    def display_label(self) -> str:
        if self.code_ue:
            return f"{self.code_ue} · {self.nom}"
        return self.nom

    def assign_code_ue(self):
        if self.code_ue:
            return self.code_ue

        used_codes = set(
            UE.objects.exclude(pk=self.pk)
            .exclude(code_ue__isnull=True)
            .exclude(code_ue="")
            .values_list("code_ue", flat=True)
        )
        index = 1
        while True:
            candidate = f"UE{index:03d}"
            if candidate not in used_codes:
                self.code_ue = candidate
                return self.code_ue
            index += 1

    def assign_couleur(self):
        if self.couleur:
            return self.couleur

        color_counts = Counter(
            UE.objects.exclude(pk=self.pk).exclude(couleur="").values_list("couleur", flat=True)
        )
        self.couleur = min(
            UE_COLOR_PALETTE,
            key=lambda color: (color_counts.get(color, 0), UE_COLOR_PALETTE.index(color)),
        )
        return self.couleur

    def save(self, *args, **kwargs):
        if self.code_ue:
            self.code_ue = self.code_ue.strip().upper().replace(" ", "")
        if not self.code_ue:
            self.assign_code_ue()
        if not self.couleur:
            self.assign_couleur()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.display_label


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

    def create_default_sessions(self):
        from exams.models import SessionExamen

        for nom in ["Semestre 1", "Semestre 2", "Rattrapages"]:
            SessionExamen.objects.get_or_create(
                formation=self,
                nom=nom,
            )

    def save(self, *args, **kwargs):
        is_creation = self._state.adding
        super().save(*args, **kwargs)
        if is_creation:
            self.create_default_sessions()

    def __str__(self) -> str:
        return f"{self.annee_universitaire.nom} - {self.nom}"
