from collections import Counter
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
    "#6B8E23",
    "#38BDF8",
    "#FF2400",
    "#D6C6A5",
)


def rebalance_ue_colors_balanced_random(apps, schema_editor):
    UE = apps.get_model("academics", "UE")
    color_counts = Counter()
    for ue in UE.objects.order_by("formation_id", "code_ue", "nom", "pk"):
        min_count = min(color_counts.get(color, 0) for color in UE_COLOR_PALETTE)
        available_colors = [
            color for color in UE_COLOR_PALETTE if color_counts.get(color, 0) == min_count
        ]
        chosen_color = random.choice(available_colors)
        ue.couleur = chosen_color
        ue.save(update_fields=["couleur"])
        color_counts[chosen_color] += 1


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0013_randomize_ue_colors_from_palette"),
    ]

    operations = [
        migrations.RunPython(rebalance_ue_colors_balanced_random, migrations.RunPython.noop),
    ]
