from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0003_auth_user_email_unique_nonempty"),
    ]

    operations = [
        migrations.DeleteModel(name="BlockedUser"),
    ]
