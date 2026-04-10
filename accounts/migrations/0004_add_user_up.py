import django.db.models.deletion
from django.db import migrations, models


def assign_default_up(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    UP = apps.get_model("academics", "UP")

    default_up, _ = UP.objects.get_or_create(nom="Autre")
    User.objects.filter(up__isnull=True).update(up=default_up)


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0010_reintroduce_up_and_scope_ue"),
        ("accounts", "0003_normalize_emails_and_make_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="up",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="users",
                to="academics.up",
            ),
        ),
        migrations.RunPython(assign_default_up, migrations.RunPython.noop),
    ]
