from django.db import migrations
from django.utils.text import slugify


def build_username_base(first_name, last_name):
    normalized_first_name = slugify(" ".join((first_name or "").split()))
    normalized_last_name = slugify(" ".join((last_name or "").split()))
    if normalized_first_name and normalized_last_name:
        return f"{normalized_first_name}.{normalized_last_name}"
    return normalized_first_name or normalized_last_name or ""


def normalize_existing_usernames(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    users = list(User.objects.order_by("date_joined", "username", "pk"))
    rename_candidates = {
        user.pk
        for user in users
        if build_username_base(user.first_name, user.last_name) and "." not in (user.username or "")
    }

    used_usernames = {
        user.username
        for user in users
        if user.username and user.pk not in rename_candidates
    }

    for user in users:
        if user.pk not in rename_candidates:
            used_usernames.add(user.username)
            continue

        base = build_username_base(user.first_name, user.last_name)
        username = base
        suffix = 2
        while username in used_usernames:
            username = f"{base}{suffix}"
            suffix += 1

        if user.username != username:
            user.username = username
            user.save(update_fields=["username"])

        used_usernames.add(username)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(normalize_existing_usernames, migrations.RunPython.noop),
    ]
