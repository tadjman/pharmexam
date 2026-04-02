import uuid
import re
from django.contrib.auth.models import AbstractUser
from django.db import models


class RoleUtilisateur(models.TextChoices):
    SCOLARITE = "SCOLARITE", "Scolarité"
    ENSEIGNANT = "ENSEIGNANT", "Enseignant"
    MEMBRE_POOL = "MEMBRE_POOL", "Membre du pool"


class User(AbstractUser):
    """
    User Django standard + role.
    On garde username pour rester simple.
    (Si tu veux login par email, on peut le faire ensuite.)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    role = models.CharField(
        max_length=20,
        choices=RoleUtilisateur.choices,
        default=RoleUtilisateur.MEMBRE_POOL,
    )

    # Optionnel (tu as déjà first_name/last_name dans AbstractUser)
    # email est déjà présent, mais pas unique par défaut
    email = models.EmailField(blank=True)

    @staticmethod
    def _normalize_spacing(value: str) -> str:
        return " ".join((value or "").split())

    @staticmethod
    def _format_first_name(value: str) -> str:
        value = User._normalize_spacing(value).lower()
        if not value:
            return ""
        return re.sub(
            r"(^|[\s'-])([^\W\d_])",
            lambda match: f"{match.group(1)}{match.group(2).upper()}",
            value,
            flags=re.UNICODE,
        )

    @staticmethod
    def _format_last_name(value: str) -> str:
        return User._normalize_spacing(value).upper()

    def is_admin(self) -> bool:
        return self.is_staff or self.is_superuser

    @property
    def display_first_name(self) -> str:
        return self._format_first_name(self.first_name)

    @property
    def display_last_name(self) -> str:
        return self._format_last_name(self.last_name)

    @property
    def display_full_name(self) -> str:
        full_name = " ".join(part for part in [self.display_first_name, self.display_last_name] if part).strip()
        return full_name or self.username

    @property
    def display_email(self) -> str:
        return self._normalize_spacing(self.email).lower()

    @property
    def display_contact(self) -> str:
        return self.display_email or self.username

    def save(self, *args, **kwargs):
        self.first_name = self._normalize_spacing(self.first_name)
        self.last_name = self._normalize_spacing(self.last_name)
        self.email = self.display_email
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.username} ({self.role})"
