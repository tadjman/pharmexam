from django.db import migrations


def purge_all_exams(apps, schema_editor):
    Examen = apps.get_model("exams", "Examen")
    Examen.objects.all().delete()


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("exams", "0005_alter_sessionexamen_options_and_more"),
    ]

    operations = [
        migrations.RunPython(purge_all_exams, migrations.RunPython.noop, atomic=True),
        migrations.AlterUniqueTogether(
            name="examen",
            unique_together={("session", "ue")},
        ),
    ]
