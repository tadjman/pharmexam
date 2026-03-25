from datetime import timedelta

from django.db import migrations


def default_session_periods(year):
    start = year.date_debut
    end = year.date_fin
    total_days = max(1, (end - start).days + 1)
    first_block = total_days // 3
    second_block = (total_days * 2) // 3

    first_end = start + timedelta(days=max(0, first_block - 1))
    second_start = first_end + timedelta(days=1)
    second_end = start + timedelta(days=max(0, second_block - 1))
    third_start = second_end + timedelta(days=1)

    return [
        ("Semestre 1", start, min(first_end, end)),
        ("Semestre 2", min(second_start, end), min(second_end, end)),
        ("Rattrapages", min(third_start, end), end),
    ]


def forwards(apps, schema_editor):
    Formation = apps.get_model("academics", "Formation")
    SessionExamen = apps.get_model("exams", "SessionExamen")

    for formation in Formation.objects.select_related("annee_universitaire"):
        for nom, date_debut, date_fin in default_session_periods(formation.annee_universitaire):
            SessionExamen.objects.get_or_create(
                formation_id=formation.pk,
                nom=nom,
                defaults={
                    "date_debut": date_debut,
                    "date_fin": date_fin,
                },
            )


def backwards(apps, schema_editor):
    Formation = apps.get_model("academics", "Formation")
    SessionExamen = apps.get_model("exams", "SessionExamen")

    for formation in Formation.objects.all():
        SessionExamen.objects.filter(
            formation_id=formation.pk,
            nom__in=["Semestre 1", "Semestre 2", "Rattrapages"],
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0003_alter_ue_options_alter_up_options"),
        ("exams", "0002_sessionexamen_formation"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
