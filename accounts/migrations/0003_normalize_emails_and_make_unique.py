from django.db import migrations, models


def normalize_emails(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    seen = set()

    for user in User.objects.order_by("date_joined", "username", "pk"):
        email = " ".join((user.email or "").split()).lower()
        if not email:
            normalized_email = None
        elif email in seen:
            normalized_email = None
        else:
            normalized_email = email
            seen.add(email)

        if user.email != normalized_email:
            user.email = normalized_email
            user.save(update_fields=["email"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_normalize_usernames_to_first_dot_last"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.RunPython(normalize_emails, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(blank=True, max_length=254, null=True, unique=True),
        ),
    ]
