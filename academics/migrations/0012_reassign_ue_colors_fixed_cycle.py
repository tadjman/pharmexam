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


def reassign_ue_colors_fixed_cycle(apps, schema_editor):
    UE = apps.get_model("academics", "UE")
    queryset = UE.objects.order_by("formation_id", "code_ue", "nom", "pk")
    for index, ue in enumerate(queryset):
        ue.couleur = UE_COLOR_PALETTE[index % len(UE_COLOR_PALETTE)]
        ue.save(update_fields=["couleur"])


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0011_remove_ue_responsables"),
    ]

    operations = [
        migrations.RunPython(reassign_ue_colors_fixed_cycle, migrations.RunPython.noop),
    ]
