# Generated by Django 4.2.4 on 2023-09-14 15:38

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("LeadCapture", "0004_auto_20230812_1616"),
    ]

    operations = [
        migrations.CreateModel(
            name="PhoneCall",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("from_field", models.CharField(max_length=255)),
                ("datetime_field", models.DateTimeField()),
                ("duration_field", models.IntegerField()),
                ("receive_text_field", models.BooleanField()),
                ("voicemail_field", models.BooleanField()),
                (
                    "voicemail_link_field",
                    models.CharField(
                        blank=True, default=None, max_length=255, null=True
                    ),
                ),
                (
                    "lead",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="LeadCapture.lead",
                    ),
                ),
            ],
        ),
    ]