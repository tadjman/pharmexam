import uuid

import django.db.models.deletion
from django.db import migrations, models


DEFAULT_UP_NAME = "Autre"


def _build_unique_code(UE, used_codes, base_code):
    normalized = (base_code or "UE").strip().upper().replace(" ", "")
    if normalized and normalized not in used_codes and len(normalized) <= 20:
        used_codes.add(normalized)
        return normalized

    root = (normalized or "UE")[:17] or "UE"
    suffix = 2
    while True:
        candidate = f"{root}-{suffix}"
        if candidate not in used_codes:
            used_codes.add(candidate)
            return candidate
        suffix += 1


def reintroduce_up_and_scope_ues(apps, schema_editor):
    UE = apps.get_model("academics", "UE")
    UP = apps.get_model("academics", "UP")
    Examen = apps.get_model("exams", "Examen")

    UP.objects.get_or_create(nom=DEFAULT_UP_NAME)

    used_codes = set(
        UE.objects.exclude(code_ue__isnull=True).exclude(code_ue="").values_list("code_ue", flat=True)
    )

    for ue in UE.objects.all().order_by("nom", "pk"):
        formations = list(ue.formations.order_by("annee_universitaire__date_debut", "nom", "pk"))
        if not formations:
            continue

        primary_formation = formations[0]
        if ue.formation_id != primary_formation.pk:
            ue.formation_id = primary_formation.pk
            ue.save(update_fields=["formation"])

        if len(formations) == 1:
            continue

        responsable_ids = list(ue.responsables.values_list("pk", flat=True))
        up_ids = list(ue.ups.values_list("pk", flat=True))

        for index, formation in enumerate(formations[1:], start=2):
            clone = UE.objects.create(
                formation_id=formation.pk,
                code_ue=_build_unique_code(UE, used_codes, f"{ue.code_ue or 'UE'}-{index}"),
                nom=ue.nom,
                couleur=ue.couleur,
            )
            if responsable_ids:
                clone.responsables.set(responsable_ids)
            if up_ids:
                clone.ups.set(up_ids)
            Examen.objects.filter(ue_id=ue.pk, session__formation_id=formation.pk).update(ue_id=clone.pk)


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0009_reassign_ue_colors_distinct_palette"),
        ("exams", "0005_alter_sessionexamen_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="UP",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("nom", models.CharField(max_length=255, unique=True)),
            ],
            options={"ordering": ["nom"]},
        ),
        migrations.AddField(
            model_name="ue",
            name="formation",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ues",
                to="academics.formation",
            ),
        ),
        migrations.AddField(
            model_name="ue",
            name="ups",
            field=models.ManyToManyField(blank=True, related_name="ues", to="academics.up"),
        ),
        migrations.AlterField(
            model_name="ue",
            name="nom",
            field=models.CharField(max_length=255),
        ),
        migrations.RunPython(reintroduce_up_and_scope_ues, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="formation",
            name="ues",
        ),
    ]
