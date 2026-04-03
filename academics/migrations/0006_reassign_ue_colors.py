from django.db import migrations


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


def rebalance_ue_colors(apps, schema_editor):
    UE = apps.get_model("academics", "UE")
    for index, ue in enumerate(UE.objects.order_by("nom", "pk")):
        ue.couleur = UE_COLOR_PALETTE[index % len(UE_COLOR_PALETTE)]
        ue.save(update_fields=["couleur"])


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0005_ue_couleur"),
    ]

    operations = [
        migrations.RunPython(rebalance_ue_colors, migrations.RunPython.noop),
    ]
