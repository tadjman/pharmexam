from django.db import models

# Create your models here.
import uuid
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

    def is_admin(self) -> bool:
        return self.is_staff or self.is_superuser

    def __str__(self) -> str:
        return f"{self.username} ({self.role})"
