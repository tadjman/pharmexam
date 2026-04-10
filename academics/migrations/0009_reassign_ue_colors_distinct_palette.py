from django.db import migrations


UE_COLOR_PALETTE = (
    "#2563EB",
    "#4F46E5",
    "#7C3AED",
    "#9333EA",
    "#A855F7",
    "#0284C7",
    "#0891B2",
    "#0EA5E9",
    "#C026D3",
    "#475569",
    "#334155",
    "#D97706",
    "#CA8A04",
    "#B45309",
    "#78716C",
    "#6B7280",
)


def rebalance_ue_colors_with_distinct_palette(apps, schema_editor):
    UE = apps.get_model("academics", "UE")
    for index, ue in enumerate(UE.objects.order_by("nom", "pk")):
        ue.couleur = UE_COLOR_PALETTE[index % len(UE_COLOR_PALETTE)]
        ue.save(update_fields=["couleur"])


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0008_ue_code_ue"),
    ]

    operations = [
        migrations.RunPython(rebalance_ue_colors_with_distinct_palette, migrations.RunPython.noop),
    ]
