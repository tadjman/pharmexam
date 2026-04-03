import random

from django.db import migrations, models


UE_COLOR_PALETTE = (
    "#2563EB",
    "#1D4ED8",
    "#3B82F6",
    "#4F46E5",
    "#6366F1",
    "#7C3AED",
    "#8B5CF6",
    "#9333EA",
    "#0EA5E9",
    "#0284C7",
    "#0891B2",
    "#475569",
    "#334155",
    "#D97706",
    "#B45309",
)


def populate_ue_colors(apps, schema_editor):
    UE = apps.get_model("academics", "UE")
    used_colors = set()
    for ue in UE.objects.order_by("nom"):
        if ue.couleur:
            used_colors.add(ue.couleur)
            continue
        available_colors = [color for color in UE_COLOR_PALETTE if color not in used_colors]
        ue.couleur = random.choice(available_colors or list(UE_COLOR_PALETTE))
        ue.save(update_fields=["couleur"])
        used_colors.add(ue.couleur)


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0004_create_default_sessions"),
    ]

    operations = [
        migrations.AddField(
            model_name="ue",
            name="couleur",
            field=models.CharField(blank=True, default="", max_length=7),
        ),
        migrations.RunPython(populate_ue_colors, migrations.RunPython.noop),
    ]
