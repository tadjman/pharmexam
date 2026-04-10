import uuid
import re
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.text import slugify


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
    email = models.EmailField(blank=True, null=True, unique=True)
    up = models.ForeignKey(
        "academics.UP",
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )

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

    @classmethod
    def build_username_base(cls, first_name: str, last_name: str) -> str:
        normalized_first_name = slugify(cls._normalize_spacing(first_name))
        normalized_last_name = slugify(cls._normalize_spacing(last_name))
        if normalized_first_name and normalized_last_name:
            return f"{normalized_first_name}.{normalized_last_name}"
        return normalized_first_name or normalized_last_name or ""

    @classmethod
    def build_unique_username(cls, first_name: str, last_name: str, exclude_pk=None) -> str:
        base = cls.build_username_base(first_name, last_name) or "utilisateur"
        username = base
        suffix = 2
        queryset = cls.objects.all()
        if exclude_pk is not None:
            queryset = queryset.exclude(pk=exclude_pk)
        while queryset.filter(username=username).exists():
            username = f"{base}{suffix}"
            suffix += 1
        return username

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
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            kwargs["update_fields"] = update_fields

        self.first_name = self._normalize_spacing(self.first_name)
        self.last_name = self._normalize_spacing(self.last_name)
        normalized_email = self.display_email or None
        if self.email != normalized_email:
            self.email = normalized_email
            if update_fields is not None:
                update_fields.add("email")

        if self.first_name and self.last_name and (self._state.adding or "." not in (self.username or "")):
            self.username = self.build_unique_username(
                self.first_name,
                self.last_name,
                exclude_pk=self.pk,
            )
            if update_fields is not None:
                update_fields.add("username")

        if self.up_id is None:
            from academics.models import UP

            self.up = UP.get_default_up()
            if update_fields is not None:
                update_fields.add("up")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.username} ({self.role})"
