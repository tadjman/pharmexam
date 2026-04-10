import random

from django.db import migrations


UE_COLOR_PALETTE = (
    "#2563EB",
    "#EAB308",
    "#7C3AED",
    "#A3E635",
    "#EC4899",
    "#111111",
    "#475569",
    "#F97316",
)


def randomize_ue_colors_from_palette(apps, schema_editor):
    UE = apps.get_model("academics", "UE")
    for ue in UE.objects.all():
        ue.couleur = random.choice(UE_COLOR_PALETTE)
        ue.save(update_fields=["couleur"])


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0012_reassign_ue_colors_fixed_cycle"),
    ]

    operations = [
        migrations.RunPython(randomize_ue_colors_from_palette, migrations.RunPython.noop),
    ]
