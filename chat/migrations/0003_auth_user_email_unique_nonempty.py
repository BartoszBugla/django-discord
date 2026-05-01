from collections import defaultdict

from django.db import migrations


def _dedupe_nonempty_emails(apps, schema_editor):
    User = apps.get_model("auth", "User")
    by_lower = defaultdict(list)
    for u in User.objects.all().iterator():
        raw = (u.email or "").strip()
        if not raw:
            continue
        by_lower[raw.lower()].append(u)

    for lower_email, users in by_lower.items():
        if len(users) < 2:
            continue
        for dup in sorted(users, key=lambda x: x.pk)[1:]:
            stem, _, domain = lower_email.partition("@")
            domain = domain or "invalid.local"
            new_local = f"{stem}+id{dup.pk}"[:200]
            new_email = f"{new_local}@{domain}"[:254]
            User.objects.filter(pk=dup.pk).update(email=new_email)

    for u in User.objects.all().iterator():
        raw = (u.email or "").strip()
        if not raw:
            continue
        low = raw.lower()
        if raw != low:
            User.objects.filter(pk=u.pk).update(email=low)


def _add_partial_unique_email_index(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "sqlite":
        schema_editor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS auth_user_email_unique_nonempty "
            "ON auth_user (email) WHERE email IS NOT NULL AND email != '';"
        )
    elif vendor == "postgresql":
        schema_editor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS auth_user_email_unique_nonempty "
            "ON auth_user (email) WHERE email IS NOT NULL AND email <> '';"
        )


def _remove_partial_unique_email_index(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "sqlite":
        schema_editor.execute("DROP INDEX IF EXISTS auth_user_email_unique_nonempty;")
    elif vendor == "postgresql":
        schema_editor.execute("DROP INDEX IF EXISTS auth_user_email_unique_nonempty;")


def forwards(apps, schema_editor):
    _dedupe_nonempty_emails(apps, schema_editor)
    _add_partial_unique_email_index(apps, schema_editor)


def backwards(apps, schema_editor):
    _remove_partial_unique_email_index(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("chat", "0002_profile_last_seen_at"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
