# Generated by Django 4.2.4 on 2023-09-21 01:16

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("Dashboard", "0003_alter_notifications_estimate_email_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="notifications",
            old_name="estimate_email",
            new_name="voicemail_email",
        ),
        migrations.RenameField(
            model_name="notifications",
            old_name="estimate_phone",
            new_name="voicemail_phone",
        ),
    ]
