# Generated by Django 4.2.4 on 2023-09-27 14:46

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("LeadCapture", "0007_formquestion_deleted"),
    ]

    operations = [
        migrations.DeleteModel(
            name="PhoneCall",
        ),
    ]
